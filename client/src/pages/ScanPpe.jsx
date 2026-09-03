import { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, Check, Keyboard, QrCode, ScanLine, ShieldAlert } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import GateFlow, { GatePageHeader } from '../components/GateFlow';
import { readGateSession, resolvePpeItem, writeGateSession } from '../services/gateCheck';

export default function ScanPpe() {
  const navigate = useNavigate();
  const initial = readGateSession();
  const [session, setSession] = useState(initial);
  const [scanned, setScanned] = useState(initial.scannedItems || []);
  const [manualCode, setManualCode] = useState('');
  const [resolving, setResolving] = useState(false);
  const [message, setMessage] = useState('Scan the QR label on each assigned item.');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!initial.worker || !initial.biometric?.verified) navigate('/biometric', { replace: true });
  }, [initial.biometric?.verified, initial.worker, navigate]);

  const scanCode = useCallback(async (rawCode) => {
    const code = rawCode.trim();
    if (!code || resolving || !session.worker) return;
    setResolving(true);
    setError('');
    try {
      const item = await resolvePpeItem(session.worker.employee_code, code);
      setScanned((current) => {
        if (current.some((entry) => entry.ppe_id === item.ppe_id)) {
          setMessage(`${item.name} was already scanned.`);
          return current;
        }
        const next = [...current, { ...item, item_id: code }];
        writeGateSession({ scannedItems: next });
        setMessage(`${item.name} verified · ${code}`);
        return next;
      });
      setManualCode('');
    } catch (caught) {
      setError(caught.message || 'This code does not match assigned PPE.');
    } finally {
      window.setTimeout(() => setResolving(false), 700);
    }
  }, [resolving, session.worker]);

  const required = session.requiredItems || [];
  const complete = required.length > 0 && required.every((item) => scanned.some((entry) => entry.ppe_id === item.ppe_id));

  return (
    <GateFlow step={2}>
      <GatePageHeader eyebrow="Step 2 · Equipment" title="Scan assigned PPE" description={`${session.worker?.name || 'Worker'}, scan each equipment QR code once. The code is resolved to its PPE type and checked against your assignment.`} />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(330px,0.8fr)]">
        <QrScanner onDetect={scanCode} />
        <aside className="panel flex flex-col p-5 sm:p-6">
          <div className="flex items-center justify-between">
            <span className="label-op">Scan progress</span>
            <span className="mono text-xs text-safety">{scanned.length}/{required.length}</span>
          </div>
          <div className="my-5 space-y-2">
            {required.map((item) => {
              const match = scanned.find((entry) => entry.ppe_id === item.ppe_id);
              return (
                <div key={item.ppe_id} className={`flex items-center gap-3 rounded-lg border p-3 transition ${match ? 'border-safety/40 bg-safetySubtle' : 'border-border bg-input'}`}>
                  <div className={`grid h-9 w-9 shrink-0 place-items-center rounded-md ${match ? 'bg-safety text-onSafety' : 'bg-elevated text-textMuted'}`}>{match ? <Check size={17} /> : <QrCode size={17} />}</div>
                  <div className="min-w-0 flex-1"><div className="text-sm font-semibold">{item.name}</div><div className="truncate mono text-[0.65rem] text-textMuted">{match?.item_id || item.item_id}</div></div>
                  <span className={`text-[0.62rem] font-bold uppercase ${match ? 'text-safety' : 'text-textMuted'}`}>{match ? 'Scanned' : 'Pending'}</span>
                </div>
              );
            })}
          </div>

          <form className="mt-auto" onSubmit={(event) => { event.preventDefault(); void scanCode(manualCode); }}>
            <label className="filter-label" htmlFor="manual-ppe-code">Manual code fallback</label>
            <div className="flex gap-2">
              <div className="filter-control-shell flex-1"><Keyboard size={15} className="filter-control-icon" /><input id="manual-ppe-code" className="filter-control" value={manualCode} onChange={(event) => setManualCode(event.target.value)} placeholder="Enter item ID" /></div>
              <button disabled={!manualCode.trim() || resolving} className="rounded-md bg-safety px-4 text-xs font-bold text-onSafety disabled:opacity-40">ADD</button>
            </div>
          </form>
          <div className={`mt-3 text-xs ${error ? 'text-danger' : 'text-textSecondary'}`}>{error || message}</div>
          <button disabled={!complete} onClick={() => { setSession(writeGateSession({ scannedItems: scanned })); navigate('/compliance-check'); }} className="mt-5 flex w-full items-center justify-center gap-2 rounded-md bg-safety py-3 text-xs font-bold uppercase tracking-wide text-onSafety shadow-glowSm disabled:cursor-not-allowed disabled:opacity-35">
            <ShieldAlert size={15} /> Continue to compliance check
          </button>
        </aside>
      </div>
    </GateFlow>
  );
}

function QrScanner({ onDetect }) {
  const videoRef = useRef(null);
  const callbackRef = useRef(onDetect);
  const [state, setState] = useState('starting');
  const [hint, setHint] = useState('Starting camera…');
  useEffect(() => { callbackRef.current = onDetect; }, [onDetect]);

  useEffect(() => {
    let stream;
    let animation;
    let stopped = false;
    let lastScan = 0;
    async function start() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
        if (stopped) return stream.getTracks().forEach((track) => track.stop());
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        if (!('BarcodeDetector' in window)) {
          setState('unsupported');
          setHint('Automatic QR detection is unavailable in this browser. Use the code field beside the camera.');
          return;
        }
        const detector = new window.BarcodeDetector({ formats: ['qr_code'] });
        setState('ready');
        setHint('Place one QR code inside the frame.');
        async function detect(time) {
          if (stopped) return;
          if (time - lastScan > 250 && videoRef.current?.readyState >= 2) {
            lastScan = time;
            try {
              const codes = await detector.detect(videoRef.current);
              if (codes[0]?.rawValue) callbackRef.current(codes[0].rawValue);
            } catch { /* A dropped camera frame is safe to ignore. */ }
          }
          animation = requestAnimationFrame(detect);
        }
        animation = requestAnimationFrame(detect);
      } catch (caught) {
        setState('error');
        setHint(caught.message || 'Camera permission was denied. Use manual entry.');
      }
    }
    void start();
    return () => { stopped = true; cancelAnimationFrame(animation); stream?.getTracks().forEach((track) => track.stop()); };
  }, []);

  return (
    <div className="panel relative min-h-[480px] overflow-hidden bg-black">
      <video ref={videoRef} muted playsInline className="absolute inset-0 h-full w-full object-cover" />
      <div className="pointer-events-none absolute inset-0 grid place-items-center bg-black/20"><div className="relative h-60 w-60 rounded-2xl border-2 border-safety shadow-glow"><ScanLine size={28} className="absolute -right-4 -top-4 rounded-full bg-safety p-1.5 text-onSafety" /></div></div>
      <div className="absolute bottom-4 left-4 right-4 flex items-center gap-2 rounded-lg border border-white/15 bg-black/75 p-3 text-xs text-white"><Camera size={15} className={state === 'ready' ? 'text-safety' : 'text-warning'} />{hint}</div>
    </div>
  );
}
