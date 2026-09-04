# SURAKSHA Smart PPE

SURAKSHA is a mine-safety monitoring application with a React dashboard and a
FastAPI backend. The live verification page captures camera frames in the
browser, sends them to the server over WebSocket, and displays only the returned
video annotated with YOLO PPE detections and local face identification.

## Project structure

```text
smart-ppe/
|-- client/                         React + Vite frontend
|-- server/                         FastAPI API and vision inference server
|-- data/suraksha.db                Local SQLite database (created automatically)
|-- best.pt                         YOLO PPE model
`-- stream_test/server/
    |-- models/                     YuNet and SFace ONNX models
    `-- data/faces.json             Local enrolled-face registry
```

## Requirements

- Windows with PowerShell
- Python 3.11
- Node.js 20.19 or newer (or Node.js 22.12 or newer)
- A browser with camera access

Camera access works on `localhost` during development. A deployed application
must use HTTPS and a secure `wss://` WebSocket endpoint.

## Required model files

Verify that these files exist before starting the server:

```text
best.pt
stream_test/server/models/face_detection_yunet_2023mar.onnx
stream_test/server/models/face_recognition_sface_2021dec.onnx
```

The model files and `faces.json` are ignored by Git. Keep a separate local copy
when cloning or moving the project. Face embeddings in `faces.json` are
biometric data and should not be committed.

## First-time setup

### 1. Set up the server

The server uses the virtual environment inside `server/.venv`.

```powershell
cd D:\smart-ppe\server

# Only run this if server/.venv does not already exist.
py -3.11 -m venv .venv

.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell prevents activation, the environment can be used without
activating it:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Set up the client

```powershell
cd D:\smart-ppe\client
npm ci
```

Use `npm install` instead if intentionally updating dependencies.

## Run the project

Open two PowerShell terminals.

### Terminal 1: FastAPI server

```powershell
cd D:\smart-ppe\server
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Wait until model loading completes and Uvicorn reports that the application has
started. The health endpoint should return `vision.status` as `ok`:

```text
http://127.0.0.1:8000/health
```

Interactive API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

### Terminal 2: React client

```powershell
cd D:\smart-ppe\client
npm run dev
```

Open the URL printed by Vite, normally:

```text
http://localhost:5173
```

The gate entry workflow starts at:

```text
http://localhost:5173/#/entry/biometric
```

Select **Start Verification** and allow camera permission. Raw camera video is
not displayed; the page renders only frames annotated by the server.

The entry workflow first confirms the worker's face on `/entry/biometric`.
After identity is locked, the same camera and tracking session advances to
`/entry/compliance`, where fresh frames verify Helmet, Vest, and both Boots in
their expected anatomical regions before issuing the gate verdict.

## Configuration

The following optional environment variables can be set before starting the
server:

| Variable | Default | Purpose |
| --- | --- | --- |
| `YOLO_MODEL_PATH` | `best.pt` in the repository root | PPE model path |
| `YOLO_POSE_MODEL` | `yolo11n-pose.pt` | Pose checkpoint path or Ultralytics model name; a model name downloads on first run |
| `YOLO_DEVICE` | Automatic | Inference device, such as `cpu` or `0` for the first CUDA GPU |
| `YOLO_IMAGE_SIZE` | `640` | YOLO inference image size |
| `YOLO_POSE_CONFIDENCE` | `0.35` | Minimum pose/keypoint confidence used for anatomical ROIs |
| `PPE_REGION_OVERLAP` | `0.50` | Minimum PPE-box coverage inside its expected body region |
| `MAX_FRAME_BYTES` | `5000000` | Maximum uploaded or streamed JPEG size |
| `FACE_DETECTOR_PATH` | YuNet model under `stream_test/server/models` | Face detector path |
| `FACE_RECOGNIZER_PATH` | SFace model under `stream_test/server/models` | Face recognizer path |
| `FACE_REGISTRY_PATH` | `stream_test/server/data/faces.json` | Enrolled face-template registry |
| `FACE_SIMILARITY_THRESHOLD` | `0.363` | Minimum face-match similarity |
| `EDGE_DEVICE_SERIAL` | `AI-CAM-G01` | Local AI camera and gate identity |
| `SURAKSHA_ROLE` | `edge` | Run as `edge` or `central` |
| `CENTRAL_SYNC_URL` | Empty | Central API base URL for the durable outbox |
| `SYNC_API_TOKEN` | Empty | Shared deployment secret for central ingestion |
| `ENTRY_IDENTITY_TIMEOUT_SECONDS` | `10` | Identity evidence deadline |
| `ENTRY_EVIDENCE_TIMEOUT_SECONDS` | `15` | PPE and QR evidence deadline |

The client connects to the event-specific entry WebSocket on port 8000 by
default. To use another server, create `client/.env` containing:

```dotenv
VITE_ENTRY_WS_URL=ws://127.0.0.1:8000/api/v1/entry/attempts
```

Restart Vite after changing client environment variables. Use `wss://` when the
client is served over HTTPS.

## Important endpoints

- `GET /health` - API and model status
- `GET /api/v1/workers` - worker list
- `GET /api/faces` - registered face profiles without embeddings
- `POST /api/faces` - register a face using exactly five JPEG images
- `PUT /api/faces/{person_id}` - replace an enrolled face template
- `DELETE /api/faces/{person_id}` - delete a face profile
- `POST /api/v1/entry/attempts` - create or resume an idempotent entry attempt
- `WS /api/v1/entry/attempts/{event_id}/stream` - integrated face, PPE, and QR pipeline
- `POST /api/v1/entry/sync/events` - idempotent central synchronization receiver

Each WebSocket `frame_meta` message includes a `persons` array with stable
`track_id`, Helmet/Vest/Boots `YES`/`NO`/`UNKNOWN` states and confidences,
an overall `COMPLIANT`/`VIOLATION`/`UNKNOWN` status, anatomical ROIs, and the
PPE detections associated with that person. Existing entry, detection, face,
and inference-timing fields remain available.

## Build and validation

YOLO dataset preparation and release validation are documented in
[`docs/yolo-training.md`](docs/yolo-training.md).

Build the frontend for production:

```powershell
cd D:\smart-ppe\client
npm run build
```

Run the frontend linter:

```powershell
npm run lint
```

Check the server environment:

```powershell
cd D:\smart-ppe\server
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q app
```

## Troubleshooting

### The camera remains offline

- Confirm the FastAPI server is running on port `8000`.
- Open `/health` and verify that `vision.status` is `ok`.
- Allow camera permission in the browser.
- Use `localhost` or HTTPS; browsers block camera access on insecure remote URLs.
- Check `VITE_ENTRY_WS_URL` if the edge server is using a different host or port.

### The server reports a missing model

Verify all three model paths listed under **Required model files**, or override
their locations using the corresponding environment variables.

The pose checkpoint defaults to `yolo11n-pose.pt` and is downloaded by
Ultralytics on first startup. For an offline edge installation, download the
checkpoint during provisioning and set `YOLO_POSE_MODEL` to its local path.

### A known person is shown as Unknown

Make sure their profile exists in `faces.json`. Re-enroll under lighting and
camera conditions similar to the live gate. Change
`FACE_SIMILARITY_THRESHOLD` only after testing false matches and rejections.

### Inference is slow

- Set `YOLO_DEVICE=0` when a compatible CUDA-enabled PyTorch installation and
  NVIDIA GPU are available.
- Reduce `YOLO_IMAGE_SIZE`.
- Reduce the client frame rate in `AnnotatedVisionFeed.jsx` if necessary.

## Local data

The SQLite database is stored at `data/suraksha.db` and is initialized with
sample records on first server startup. Deleting it resets local application
data. The face registry is separate and is not recreated from the database.
