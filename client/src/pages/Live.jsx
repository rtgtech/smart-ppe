import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ScanFace, Nfc, RotateCcw, User, BellRing } from 'lucide-react';
import { PageHeader, Badge, StatusDot } from '../components/ui';
import AnnotatedVisionFeed from '../components/AnnotatedVisionFeed';
import { VERIFICATION_RESULT } from '../data/mockData';

const PPE_LABELS = {
  helmet: 'Helmet',
  capLamp: 'Cap Lamp',
  safetyBoots: 'Safety Boots',
  reflectiveVest: 'Reflective Vest',
  gasDetector: 'Gas Detector',
  selfRescuer: 'Self-Rescuer',
};

// step-by-step reveal sequence (key -> delay ms from start)
const SEQUENCE = [
  { key: 'idle', label: '' },
  { key: 'scan', label: 'SCANNING…' },
  { key: 'face', label: 'FACE DETECTED ✓' },
  { key: 'identity', label: 'IDENTITY VERIFIED ✓' },
  { key: 'rfid', label: 'RFID VERIFIED ✓' },
  { key: 'checkingPpe', label: 'CHECKING PPE…' },
  { key: 'helmet', label: 'HELMET ✓' },
  { key: 'capLamp', label: 'CAP LAMP ✓' },
  { key: 'safetyBoots', label: 'SAFETY BOOTS ✕' },
  { key: 'reflectiveVest', label: 'REFLECTIVE VEST ✓' },
  { key: 'gasDetector', label: 'GAS DETECTOR ✓' },
  { key: 'selfRescuer', label: 'SELF-RESCUER ✓' },
  { key: 'compliance', label: 'COMPLIANCE CHECK…' },
  { key: 'decision', label: 'ENTRY DENIED' },
];

export default function Live() {
  const navigate = useNavigate();
  const [stepIndex, setStepIndex] = useState(0); // 0 = idle
  const [running, setRunning] = useState(false);
  const [revealedPpe, setRevealedPpe] = useState({});
  const [visionConnection, setVisionConnection] = useState('offline');
  const timeouts = useRef([]);

  function clearTimers() {
    timeouts.current.forEach(clearTimeout);
    timeouts.current = [];
  }

  function startVerification() {
    clearTimers();
    setRevealedPpe({});
    setRunning(true);
    setStepIndex(1);

    const stepDelay = 190; // ~2.5s total across 13 steps
    SEQUENCE.forEach((step, i) => {
      if (i === 0) return;
      const t = setTimeout(() => {
        setStepIndex(i);
        if (PPE_LABELS[step.key]) {
          setRevealedPpe((prev) => ({ ...prev, [step.key]: true }));
        }
        if (i === SEQUENCE.length - 1) setRunning(false);
      }, stepDelay * i);
      timeouts.current.push(t);
    });
  }

  function reset() {
    clearTimers();
    setRunning(false);
    setStepIndex(0);
    setRevealedPpe({});
  }

  const currentLabel = SEQUENCE[stepIndex]?.label || '';
  const decided = stepIndex === SEQUENCE.length - 1;
  const scanning = running || stepIndex > 0;

  return (
    <div className="animate-fadeUp">
      <PageHeader
        eyebrow="GATE 02 · SHAFT ENTRY"
        title="Live PPE Verification"
        right={
          <div className="flex items-center gap-3">
            <Badge tone={visionConnection === 'error' ? 'danger' : 'safety'}>
              <StatusDot status={visionConnection === 'online' ? 'ONLINE' : 'OFFLINE'} />
              CAMERA {visionConnection === 'online' ? 'ONLINE' : visionConnection === 'connecting' ? 'CONNECTING' : 'OFFLINE'}
            </Badge>
            <Badge tone="safety"><StatusDot status="ONLINE" /> RFID ONLINE</Badge>
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-[65%_35%] gap-5">
        {/* LEFT — camera panel */}
        <div className="panel overflow-hidden relative" style={{ minHeight: 420 }}>
          <AnnotatedVisionFeed active={scanning} onConnectionChange={setVisionConnection} />
        </div>

        {/* RIGHT — verification result */}
        <div className="panel p-5 flex flex-col">
          <div className="label-op mb-4">Verification Result</div>

          <div className="flex items-center gap-3 mb-5">
            <div className="w-11 h-11 rounded-full bg-elevated border border-border flex items-center justify-center">
              <User size={18} className="text-textSecondary" />
            </div>
            <div>
              <div className="font-bold text-sm">{VERIFICATION_RESULT.worker}</div>
              <div className="mono text-xs text-textMuted">{VERIFICATION_RESULT.workerId}</div>
            </div>
          </div>

          <div className="space-y-1.5 mb-5">
            {Object.entries(PPE_LABELS).map(([key, label]) => {
              const shown = revealedPpe[key];
              const ok = VERIFICATION_RESULT.ppe[key];
              return (
                <div
                  key={key}
                  className={`flex items-center justify-between py-2 px-3 rounded border transition-all duration-300 ${
                    shown ? 'opacity-100 translate-y-0' : 'opacity-30'
                  } ${shown && !ok ? 'border-danger/40 bg-danger/5' : 'border-border/60'}`}
                >
                  <span className="text-xs text-textSecondary">{label}</span>
                  {shown ? (
                    ok ? (
                      <span className="text-xs font-bold text-safety">✓ VERIFIED</span>
                    ) : (
                      <span className="text-xs font-bold text-danger">✕ MISSING</span>
                    )
                  ) : (
                    <span className="text-xs text-textMuted">—</span>
                  )}
                </div>
              );
            })}
          </div>

          <div className="flex items-center justify-between panel-elevated px-3 py-2.5 mb-4">
            <span className="label-op">AI Confidence</span>
            <span className="mono font-bold text-safety">{VERIFICATION_RESULT.aiConfidence}%</span>
          </div>

          {decided && (
            <div className="mb-4 animate-fadeUp">
              <div className="text-2xl font-extrabold text-danger tracking-tight">ENTRY DENIED</div>
              <div className="text-xs text-textSecondary mt-1">
                MANDATORY PPE MISSING — <span className="text-text font-semibold">Safety Boots</span>
              </div>
            </div>
          )}

          <div className="mt-auto space-y-2">
            {!scanning || decided ? (
              <button
                onClick={startVerification}
                className="w-full py-2.5 rounded-md bg-safety text-onSafety font-bold text-xs uppercase tracking-wide shadow-glowSm hover:brightness-110 transition focus-ring flex items-center justify-center gap-2"
              >
                <ScanFace size={14} /> {decided ? 'RETRY SCAN' : 'START VERIFICATION'}
              </button>
            ) : (
              <button disabled className="w-full py-2.5 rounded-md border border-border text-textSecondary text-xs uppercase tracking-wide flex items-center justify-center gap-2">
                <Nfc size={14} className="animate-pulseGlow" /> {currentLabel || 'PROCESSING…'}
              </button>
            )}
            <div className="grid grid-cols-2 gap-2">
              <button onClick={() => navigate(`/workers/${VERIFICATION_RESULT.workerId}`)} className="py-2 rounded-md border border-border text-xs font-semibold text-textSecondary hover:text-text hover:border-safety/50 transition focus-ring">
                VIEW WORKER
              </button>
              <button onClick={() => navigate('/alerts')} className="py-2 rounded-md border border-danger/40 text-xs font-semibold text-danger hover:bg-danger/10 transition focus-ring flex items-center justify-center gap-1.5">
                <BellRing size={12} /> ALERT SUPERVISOR
              </button>
            </div>
            {scanning && (
              <button onClick={reset} className="w-full py-1.5 text-[0.68rem] text-textMuted hover:text-textSecondary flex items-center justify-center gap-1.5 focus-ring">
                <RotateCcw size={11} /> reset demo
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="mt-4 panel px-4 py-2.5 flex items-center gap-6 mono text-[0.68rem] text-textMuted">
        <span>10:32:14</span>
        <span>GATE-02</span>
        <span>CAM-002</span>
        <span>RFID-8F31A9</span>
      </div>
    </div>
  );
}

export function CameraFeed({ stepIndex, scanning }) {
  const label = SEQUENCE[stepIndex]?.label;
  return (
    <div className="relative w-full h-full min-h-[420px] bg-[#05100b]">
      <svg viewBox="0 0 900 640" preserveAspectRatio="xMidYMid slice" className="absolute inset-0 w-full h-full">
        <defs>
          <radialGradient id="feedGlow" cx="50%" cy="35%" r="75%">
            <stop offset="0%" stopColor="#0d2e1c" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#020604" stopOpacity="1" />
          </radialGradient>
        </defs>
        <rect width="900" height="640" fill="#030706" />
        {[820, 660, 520, 400, 300].map((r, i) => (
          <ellipse key={i} cx="450" cy="640" rx={r} ry={r * 0.62} fill="none" stroke="#182420" strokeWidth="2" opacity={0.7 - i * 0.1} />
        ))}
        <ellipse cx="450" cy="300" rx="900" ry="600" fill="url(#feedGlow)" />
        {/* worker silhouette */}
        <g opacity="0.9">
          <ellipse cx="450" cy="330" rx="34" ry="42" fill="#12201a" />
          <rect x="400" y="365" width="100" height="180" rx="18" fill="#0e1a15" />
          <rect x="392" y="380" width="26" height="130" rx="10" fill="#0e1a15" />
          <rect x="482" y="380" width="26" height="130" rx="10" fill="#0e1a15" />
        </g>
        {/* AI bounding box */}
        {scanning && (
          <rect x="378" y="290" width="150" height="270" rx="6" fill="none" stroke="#19E875" strokeWidth="2" strokeDasharray="6 4" opacity="0.85" />
        )}
      </svg>

      {scanning && (
        <div className="absolute inset-x-0 top-0 h-full overflow-hidden pointer-events-none">
          <div className="w-full h-16 bg-gradient-to-b from-safety/0 via-safety/15 to-safety/0 animate-scan" />
        </div>
      )}

      <div className="absolute top-4 left-4 flex flex-col gap-1.5">
        <div className="mono text-[0.65rem] px-2 py-1 rounded bg-black/50 border border-border text-safety">FACE DETECTED</div>
        <div className="mono text-[0.65rem] px-2 py-1 rounded bg-black/50 border border-white/20 text-white">RAMESH KUMAR</div>
        <div className="mono text-[0.65rem] px-2 py-1 rounded bg-black/50 border border-white/20 text-[#89938F]">WK10234</div>
        <div className="mono text-[0.65rem] px-2 py-1 rounded bg-black/50 border border-border text-safety">RFID VERIFIED</div>
      </div>

      {label && (
        <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between">
          <div className="mono text-xs px-3 py-1.5 rounded bg-black/60 border border-safety/40 text-safety animate-fadeUp">
            {label}
          </div>
          <div className="mono text-[0.65rem] text-textMuted">CAM-002 · 1280×720 · 30fps</div>
        </div>
      )}
    </div>
  );
}
