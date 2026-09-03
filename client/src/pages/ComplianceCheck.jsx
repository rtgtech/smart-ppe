import { useCallback, useEffect, useRef, useState } from 'react';
import { Check, LoaderCircle, RotateCcw, ScanFace, ShieldCheck, ShieldX, User } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import AnnotatedVisionFeed from '../components/AnnotatedVisionFeed';
import GateFlow, { GatePageHeader } from '../components/GateFlow';
import ppeCatalog from '../assets/ppe/ppe-catalog-strip.png';
import { completeGateCheck, readGateSession, resetGateSession } from '../services/gateCheck';

const SAMPLE_MS = 1100;
const REQUIRED_RATIO = 0.6;

export default function ComplianceCheck() {
  const navigate = useNavigate();
  const [session] = useState(() => readGateSession());
  const sessionRef = useRef(session);
  const samplesRef = useRef([]);
  const samplingRef = useRef(false);
  const timerRef = useRef(null);
  const [connection, setConnection] = useState('offline');
  const [live, setLive] = useState({ face: false, faceConfidence: 0, detections: {} });
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const allScanned = session.requiredItems?.every((item) => session.scannedItems?.some((scan) => scan.ppe_id === item.ppe_id));
    if (!session.worker || !session.biometric?.verified || !allScanned) navigate('/biometric', { replace: true });
    return () => window.clearInterval(timerRef.current);
  }, [navigate, session]);

  const handleFrame = useCallback((meta) => {
    const workerCode = sessionRef.current.worker?.employee_code;
    const matchedFaces = (meta.faces || []).filter((face) => face.recognized && face.person_id === workerCode);
    const faceBox = matchedFaces[0]?.bbox;
    const faceCenter = faceBox ? [(faceBox[0] + faceBox[2]) / 2, (faceBox[1] + faceBox[3]) / 2] : null;
    const workerBox = faceCenter ? (meta.detections || [])
      .filter((detection) => detection.label.toLowerCase() === 'person')
      .map((detection) => detection.bbox)
      .find((box) => faceCenter[0] >= box[0] && faceCenter[0] <= box[2] && faceCenter[1] >= box[1] && faceCenter[1] <= box[3]) : null;
    const bestByLabel = {};
    for (const detection of meta.detections || []) {
      const label = detection.label.toLowerCase();
      const center = [(detection.bbox[0] + detection.bbox[2]) / 2, (detection.bbox[1] + detection.bbox[3]) / 2];
      const belongsToWorker = workerBox && center[0] >= workerBox[0] && center[0] <= workerBox[2] && center[1] >= workerBox[1] && center[1] <= workerBox[3];
      if (!belongsToWorker) continue;
      if (!bestByLabel[label] || detection.confidence > bestByLabel[label].confidence) bestByLabel[label] = detection;
    }
    const frame = {
      face: matchedFaces.length === 1,
      faceConfidence: matchedFaces[0]?.similarity || 0,
      detections: bestByLabel,
    };
    setLive(frame);
    if (samplingRef.current) samplesRef.current.push(frame);
  }, []);

  const finishCheck = useCallback(async () => {
    samplingRef.current = false;
    window.clearInterval(timerRef.current);
    setProgress(100);
    const samples = samplesRef.current;
    if (!samples.length) {
      setError('No inference frames were received. Check the camera and vision server.');
      setProcessing(false);
      return;
    }

    const requiredItems = sessionRef.current.requiredItems || [];
    const faceSamples = samples.filter((sample) => sample.face);
    const faceVerified = faceSamples.length / samples.length >= REQUIRED_RATIO;
    const detections = [];
    for (const item of requiredItems) {
      const appearances = samples.map((sample) => sample.detections[item.vision_label]).filter(Boolean);
      if (appearances.length / samples.length >= REQUIRED_RATIO) {
        detections.push(appearances.reduce((best, itemDetection) => itemDetection.confidence > best.confidence ? itemDetection : best));
      }
    }

    try {
      const response = await completeGateCheck({
        employee_code: sessionRef.current.worker.employee_code,
        gate_id: sessionRef.current.gate.gate_id,
        face_verified: faceVerified,
        face_confidence: faceSamples.length ? Math.max(...faceSamples.map((sample) => sample.faceConfidence)) : 0,
        scanned_items: sessionRef.current.scannedItems.map((item) => ({ item_id: item.item_id, ppe_id: item.ppe_id })),
        detections,
      });
      setResult(response);
    } catch (caught) {
      setError(caught.message || 'The gate result could not be recorded.');
    } finally {
      setProcessing(false);
    }
  }, []);

  function beginCheck() {
    if (connection !== 'online' || processing) return;
    samplesRef.current = [];
    samplingRef.current = true;
    setResult(null);
    setError('');
    setProgress(0);
    setProcessing(true);
    const started = performance.now();
    timerRef.current = window.setInterval(() => {
      const elapsed = performance.now() - started;
      setProgress(Math.min(99, Math.round(elapsed * 100 / SAMPLE_MS)));
      if (elapsed >= SAMPLE_MS) void finishCheck();
    }, 50);
  }

  function nextWorker() {
    resetGateSession();
    navigate('/biometric', { replace: true });
  }

  return (
    <GateFlow step={3}>
      <GatePageHeader eyebrow="Step 3 · Compliance" title="Final live safety check" description="Keep your face, helmet, reflective vest, and boots visible. The decision uses a continuous one-second sample instead of a single frame." />
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3">
        <div className="flex items-center gap-3"><div className="grid h-10 w-10 place-items-center rounded-full border border-border bg-elevated"><User size={17} className="text-safety" /></div><div><div className="text-sm font-bold">{session.worker?.name}</div><div className="mono text-[0.68rem] text-textMuted">{session.worker?.employee_code} · {session.worker?.department}</div></div></div>
        <div className="text-right"><div className="label-op">Checkpoint</div><div className="mt-1 text-xs font-semibold">{session.gate?.name} · {session.gate?.location}</div></div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(390px,0.9fr)]">
        <div className="panel relative min-h-[560px] overflow-hidden"><AnnotatedVisionFeed active onConnectionChange={setConnection} onFrameMeta={handleFrame} />{processing && <div className="pointer-events-none absolute inset-x-0 top-0 h-1 bg-elevated"><div className="h-full bg-safety transition-[width] duration-75" style={{ width: `${progress}%` }} /></div>}</div>

        <aside className="panel flex flex-col p-4 sm:p-5">
          <div className="mb-3 flex items-center justify-between"><span className="label-op">Live verification</span><span className={`text-[0.65rem] font-bold uppercase ${connection === 'online' ? 'text-safety' : 'text-danger'}`}>{connection}</span></div>
          <VerificationRow name="Identity match" id={session.worker?.employee_code} verified={live.face} confidence={live.faceConfidence} face />
          <div className="my-3 h-px bg-border" />
          <div className="space-y-2.5">
            {(session.requiredItems || []).map((item) => {
              const detection = live.detections[item.vision_label];
              const scan = session.scannedItems?.find((entry) => entry.ppe_id === item.ppe_id);
              return <VerificationRow key={item.ppe_id} name={item.name} id={scan?.item_id || item.item_id} verified={Boolean(detection)} confidence={detection?.confidence || 0} imagePosition={thumbnailPosition(item.name)} />;
            })}
          </div>

          {result && (
            <div className={`mt-5 rounded-lg border p-4 animate-fadeUp ${result.allowed ? 'border-safety/45 bg-safetySubtle' : 'border-dangerBorder bg-dangerSubtle'}`}>
              <div className="flex items-center gap-3">{result.allowed ? <ShieldCheck size={28} className="text-safety" /> : <ShieldX size={28} className="text-danger" />}<div><div className={`text-xl font-extrabold ${result.allowed ? 'text-safety' : 'text-danger'}`}>{result.verdict}</div><div className="mt-1 text-xs text-textSecondary">{result.allowed ? 'Attendance and compliance recorded.' : `Missing: ${result.missing.join(', ')}`}</div></div></div>
            </div>
          )}
          {error && <div className="mt-4 rounded-md border border-dangerBorder bg-dangerSubtle p-3 text-xs text-danger">{error}</div>}

          <div className="mt-auto pt-5">
            {result?.allowed ? (
              <button onClick={nextWorker} className="flex w-full items-center justify-center gap-2 rounded-md bg-safety py-3 text-xs font-bold uppercase tracking-wide text-onSafety"><Check size={15} /> Process next worker</button>
            ) : (
              <button disabled={connection !== 'online' || processing} onClick={beginCheck} className="flex w-full items-center justify-center gap-2 rounded-md bg-safety py-3 text-xs font-bold uppercase tracking-wide text-onSafety shadow-glowSm disabled:opacity-40">
                {processing ? <LoaderCircle size={15} className="animate-spin" /> : result ? <RotateCcw size={15} /> : <ScanFace size={15} />}
                {processing ? `Analyzing ${progress}%` : result ? 'Run check again' : 'Begin 1-second check'}
              </button>
            )}
            <div className="mt-3 text-center text-[0.65rem] text-textMuted">A decision is persisted only after the full sampling window completes.</div>
          </div>
        </aside>
      </div>
    </GateFlow>
  );
}

function VerificationRow({ name, id, verified, confidence, face = false, imagePosition }) {
  return (
    <div className={`flex items-center gap-3 rounded-lg border p-2.5 transition-colors ${verified ? 'border-safety/40 bg-safetySubtle' : 'border-border bg-input'}`}>
      {face ? <div className="grid h-14 w-14 shrink-0 place-items-center rounded-md bg-elevated"><User size={20} className="text-textSecondary" /></div> : <div className="h-14 w-14 shrink-0 rounded-md bg-cover bg-no-repeat" style={{ backgroundImage: `url(${ppeCatalog})`, backgroundSize: '300% 100%', backgroundPosition: imagePosition }} role="img" aria-label={`${name} stock reference`} />}
      <div className="min-w-0 flex-1"><div className="text-sm font-semibold">{name}</div><div className="truncate mono text-[0.64rem] text-textMuted">{id}</div><div className={`mt-1 text-[0.62rem] font-bold uppercase ${verified ? 'text-safety' : 'text-textMuted'}`}>{verified ? `Visible · ${(confidence * 100).toFixed(0)}%` : 'Not visible'}</div></div>
      <div className={`grid h-7 w-7 place-items-center rounded-full border ${verified ? 'border-safety bg-safety text-onSafety' : 'border-border text-textMuted'}`}>{verified ? <Check size={14} /> : <span className="h-1.5 w-1.5 rounded-full bg-current" />}</div>
    </div>
  );
}

function thumbnailPosition(name) {
  if (name === 'Helmet') return 'left center';
  if (name === 'Reflective Vest') return 'center center';
  return 'right center';
}
