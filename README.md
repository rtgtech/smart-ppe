# SURAKSHA Smart PPE

SURAKSHA is a mine-safety monitoring application with a React dashboard and a
FastAPI backend. The entry page streams camera frames to the server and displays
the annotated JPEG frames returned by the face and PPE models. Entry scan state
is kept only in server memory; it is never written to the database.

## Project structure

```text
smart-ppe/
|-- client/                         React + Vite frontend
|-- server/                         FastAPI API and vision inference server
|-- data/suraksha.db                Local SQLite database (created automatically)
|-- best.pt                         YOLO PPE model
`-- stream_test/server/
    |-- models/                     SCRFD ONNX and EdgeFace PyTorch models
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
stream_test/server/models/scrfd_10g_bnkps.onnx
stream_test/server/models/edgeface_s_gamma_05.pt
```

The bundled face models are pinned deployment assets. Their SHA-256 digests are
`5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91`
(SCRFD) and
`dc59abda2e8580399fd115a1eeb07e1f21156196db604b884407bcf0f17efb07`
(EdgeFace). See [`server/THIRD_PARTY_NOTICES.md`](server/THIRD_PARTY_NOTICES.md)
before deploying them. Face embeddings in `faces.json` are biometric data and
should not be committed.

Face templates are model-specific. Profiles enrolled with the former SFace
stack remain visible but are excluded from matching until they are re-enrolled
with EdgeFace. The health response reports the compatible, total, and
re-enrollment-required profile counts.

## First-time setup

### 1. Set up the server

The server uses the virtual environment inside `server/.venv`.

```powershell
cd D:\smart-ppe\server

# Only run this if server/.venv does not already exist.
py -3.11 -m venv .venv

.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# Create local backend configuration, then replace the API-key placeholder.
Copy-Item .env.example .env
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
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --env-file .env
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

Select **Start entry scan** and allow camera permission. Raw camera video is
not displayed; the page renders only frames annotated by the server.

The entry workflow first confirms the worker's face on `/entry/biometric`.
After identity is locked, the same camera and tracking session advances to
`/entry/compliance`, where fresh frames verify Helmet, Vest, and both Boots in
their expected body regions before issuing the gate verdict.
Identity advances on the first valid recognized frame; PPE requires three consistent observations. The result is discarded
on **Process next worker** and unfinished sessions expire after ten minutes.

## Configuration

The following optional environment variables can be set before starting the
server:

| Variable | Default | Purpose |
| --- | --- | --- |
| `YOLO_MODEL_PATH` | `best.pt` in the repository root | PPE model path for Helmet, Vest, and Boots |
| `YOLO_POSE_MODEL` | `yolo11n-pose.pt` | Pose checkpoint path or Ultralytics model name; a model name downloads on first run |
| `YOLO_DEVICE` | Automatic | Inference device, such as `cpu` or `0` for the first CUDA GPU |
| `YOLO_IMAGE_SIZE` | `640` | YOLO inference image size |
| `YOLO_POSE_CONFIDENCE` | `0.35` | Minimum pose/keypoint confidence used for anatomical ROIs |
| `PPE_REGION_OVERLAP` | `0.50` | Minimum PPE-box coverage inside its expected body region |
| `MAX_FRAME_BYTES` | `5000000` | Maximum uploaded or streamed JPEG size |
| `FACE_DETECTOR_PATH` | `scrfd_10g_bnkps.onnx` under `stream_test/server/models` | Landmark-capable SCRFD detector path |
| `FACE_RECOGNIZER_PATH` | `edgeface_s_gamma_05.pt` under `stream_test/server/models` | EdgeFace-S gamma=0.5 checkpoint path |
| `FACE_REGISTRY_PATH` | `stream_test/server/data/faces.json` | Enrolled face-template registry |
| `FACE_SIMILARITY_THRESHOLD` | `0.40` | Minimum EdgeFace cosine similarity; calibrate against site data |
| `FACE_DETECTION_THRESHOLD` | `0.50` | Minimum SCRFD face confidence |
| `FACE_NMS_THRESHOLD` | `0.40` | SCRFD non-maximum-suppression IoU threshold |
| `FACE_DETECTION_SIZE` | `640` | Square SCRFD input size; must be a multiple of 32 |
| `FACE_DEVICE` | `YOLO_DEVICE`, then automatic | EdgeFace PyTorch device and preferred SCRFD provider |
| `EDGE_DEVICE_SERIAL` | `AI-CAM-G01` | Local AI camera and gate identity |
| `SURAKSHA_ROLE` | `edge` | Run as `edge` or `central` |
| `CENTRAL_SYNC_URL` | Empty | Central API base URL for the durable outbox |
| `SYNC_API_TOKEN` | Empty | Shared deployment secret for central ingestion |
| `ASSISTANT_API_TOKEN` | Empty | Required `X-Assistant-Token` for the read-only assistant query API |
| `GOOGLE_API_KEY` | Empty | Enables Gemini Live voice sessions; kept on the backend only |
| `GEMINI_LIVE_MODEL` | `gemini-3.1-flash-live-preview` | Gemini Live model used for spoken conversations |
| `ENTRY_IDENTITY_TIMEOUT_SECONDS` | `10` | Identity evidence deadline |
| `ENTRY_EVIDENCE_TIMEOUT_SECONDS` | `15` | PPE evidence deadline |

The client connects to the event-specific entry WebSocket on port 8000 by
default. To use another server, create `client/.env` containing:

```dotenv
VITE_ENTRY_WS_URL=ws://127.0.0.1:8000/api/v1/entry/attempts
VITE_VOICE_WS_URL=ws://127.0.0.1:8000/api/v1/voice/ws
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
- `POST /api/v1/entry/attempts` - create an in-memory entry session
- `GET /api/v1/entry/attempts/{session_id}` - read the transient session
- `DELETE /api/v1/entry/attempts/{session_id}` - discard the transient session
- `WS /api/v1/entry/attempts/{session_id}/stream` - stream annotated face and PPE frames
- `WS /api/v1/voice/ws` - stream microphone and Gemini Live audio for the voice agent

Each WebSocket `frame_meta` message includes the transient entry state, faces,
PPE detections, person-level results, image quality, and inference timings. The
server sends the corresponding annotated JPEG as the next WebSocket message.

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

Make sure their profile exists in `faces.json` and that `/health` does not count
it under `face_profiles_reenrollment_required`. Re-enroll under lighting and
camera conditions similar to the live gate. Change `FACE_SIMILARITY_THRESHOLD`
only after measuring both false accepts and false rejects on representative
site data.

### Inference is slow

- Set `YOLO_DEVICE=0` when a compatible CUDA-enabled PyTorch installation and
  NVIDIA GPU are available.
- Set `FACE_DEVICE=0` for EdgeFace GPU inference. SCRFD also uses CUDA when an
  ONNX Runtime build exposing `CUDAExecutionProvider` is installed; otherwise
  its health field reports `CPUExecutionProvider`.
- Reduce `YOLO_IMAGE_SIZE`.
- Reduce the client frame rate in `AnnotatedVisionFeed.jsx` if necessary.

## Local data

The SQLite database is stored at `data/suraksha.db` and is initialized with
sample records on first server startup. Deleting it resets local application
data. The face registry is separate and is not recreated from the database.
