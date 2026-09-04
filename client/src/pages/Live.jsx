import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ScanFace, RotateCcw, User, BellRing, Check, X, Square } from 'lucide-react';
import { PageHeader, Badge, StatusDot } from '../components/ui';
import AnnotatedVisionFeed from '../components/AnnotatedVisionFeed';

const PPE_LABELS = {
  glove: 'Gloves',
  goggles: 'Goggles',
  helmet: 'Helmet',
  mask: 'Mask',
  shoes: 'Shoes',
};

export default function Live() {
  const navigate = useNavigate();
  const [scanning, setScanning] = useState(false);
  const [visionConnection, setVisionConnection] = useState('offline');
  const [liveMeta, setLiveMeta] = useState(null);
  const [currentTime, setCurrentTime] = useState(() => new Date().toLocaleTimeString('en-GB'));

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString('en-GB'));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const handleFrameMeta = useCallback((meta) => {
    setLiveMeta(meta);
  }, []);

  function startVerification() {
    window.open('/#/entry/biometric', '_blank', 'noopener,noreferrer');
  }

  function reset() {
    setScanning(false);
    setLiveMeta(null);
  }

  // Derive worker info from live websocket metadata or idle fallback
  const worker = liveMeta?.worker || {
    name: scanning ? 'Scanning…' : 'Awaiting Scan',
    workerId: scanning ? 'LOCATING…' : '—',
    id: '—',
    ppeScore: null,
    risk: 'LOW',
    department: '—',
    recognized: false,
  };

  const ppe = liveMeta?.ppe || {};
  const missing = liveMeta?.missing || [];
  const aiConfidence = liveMeta?.aiConfidence ?? 0;
  const decision = liveMeta?.decision || (scanning ? 'ANALYZING…' : 'IDLE');
  const isDecided = scanning && liveMeta && (decision === 'ENTRY ALLOWED' || decision === 'ENTRY DENIED');
  const isAllowed = decision === 'ENTRY ALLOWED';

  const workerNavId = worker.id !== '—' && worker.id !== 'UNKNOWN' && worker.id !== 'LOCATING…' ? worker.id : null;

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
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-[65%_35%] gap-5">
        {/* LEFT — camera panel */}
        <div className="panel overflow-hidden relative" style={{ minHeight: 420 }}>
          <AnnotatedVisionFeed
            active={scanning}
            onConnectionChange={setVisionConnection}
            onFrameMeta={handleFrameMeta}
          />
        </div>

        {/* RIGHT — verification result */}
        <div className="panel p-5 flex flex-col">
          <div className="label-op mb-4">Verification Result</div>

          <div className="flex items-center gap-3 mb-5">
            <div className={`w-11 h-11 rounded-full border flex items-center justify-center transition-colors ${worker.recognized ? 'bg-safety/10 border-safety/40 text-safety' : 'bg-elevated border-border text-textSecondary'
              }`}>
              <User size={18} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm truncate">{worker.name}</span>
                {worker.recognized && (
                  <span className="mono text-[0.65rem] px-1.5 py-0.5 rounded bg-safety/10 text-safety border border-safety/30">
                    VERIFIED
                  </span>
                )}
              </div>
              <div className="mono text-xs text-textMuted flex items-center gap-2 mt-0.5">
                <span>{worker.workerId || worker.id || '—'}</span>
                {worker.department && worker.department !== '—' && (
                  <>
                    <span>·</span>
                    <span className="truncate">{worker.department}</span>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="space-y-1.5 mb-5">
            {Object.entries(PPE_LABELS).map(([key, label]) => {
              const hasData = liveMeta && key in ppe;
              const ok = ppe[key];
              return (
                <div
                  key={key}
                  className={`flex items-center justify-between py-2 px-3 rounded border transition-all duration-200 ${hasData ? 'opacity-100' : 'opacity-40'
                    } ${hasData && !ok ? 'border-danger/40 bg-danger/5' : hasData && ok ? 'border-safety/30 bg-safetySubtle/30' : 'border-border/60'}`}
                >
                  <span className="text-xs text-textSecondary">{label}</span>
                  {hasData ? (
                    ok ? (
                      <span className="text-xs font-bold text-safety flex items-center gap-1">
                        <Check size={12} /> VERIFIED
                      </span>
                    ) : (
                      <span className="text-xs font-bold text-danger flex items-center gap-1">
                        <X size={12} /> MISSING
                      </span>
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
            <span className={`mono font-bold ${aiConfidence > 70 ? 'text-safety' : aiConfidence > 40 ? 'text-warning' : 'text-textMuted'}`}>
              {liveMeta ? `${aiConfidence}%` : '—'}
            </span>
          </div>

          {isDecided && (
            <div className="mb-4 animate-fadeUp">
              {isAllowed ? (
                <>
                  <div className="text-2xl font-extrabold text-safety tracking-tight">ENTRY ALLOWED</div>
                  <div className="text-xs text-textSecondary mt-1">
                    ALL MANDATORY PPE VERIFIED — <span className="text-text font-semibold">Worker cleared for shift</span>
                  </div>
                </>
              ) : (
                <>
                  <div className="text-2xl font-extrabold text-danger tracking-tight">ENTRY DENIED</div>
                  <div className="text-xs text-textSecondary mt-1">
                    MANDATORY PPE MISSING — <span className="text-text font-semibold">{missing.join(', ') || 'Unregistered Personnel'}</span>
                  </div>
                </>
              )}
            </div>
          )}

          <div className="mt-auto space-y-2">
            {!scanning ? (
              <button
                onClick={startVerification}
                className="w-full py-2.5 rounded-md bg-safety text-onSafety font-bold text-xs uppercase tracking-wide shadow-glowSm hover:brightness-110 transition focus-ring flex items-center justify-center gap-2"
              >
                <ScanFace size={14} /> OPEN GATE ENTRY
              </button>
            ) : (
              <div className="space-y-2">
                {isDecided && (
                  <button
                    onClick={() => setLiveMeta(null)}
                    className={`w-full py-2.5 rounded-md text-xs uppercase tracking-wide flex items-center justify-center gap-2 font-bold transition focus-ring shadow-glowSm ${isAllowed ? 'bg-safety text-onSafety hover:brightness-110' : 'bg-elevated border border-border text-text hover:border-safety/40'
                      }`}
                  >
                    <RotateCcw size={14} /> SCAN NEXT WORKER
                  </button>
                )}
                <button
                  onClick={reset}
                  className="w-full py-2.5 rounded-md border border-danger/60 bg-danger/10 hover:bg-danger/20 text-danger font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 transition focus-ring"
                >
                  <Square size={13} className="fill-current" /> STOP VERIFICATION
                </button>
              </div>
            )}

            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => workerNavId && navigate(`/workers/${workerNavId}`)}
                disabled={!workerNavId}
                className={`py-2 rounded-md border border-border text-xs font-semibold transition focus-ring ${workerNavId ? 'text-textSecondary hover:text-text hover:border-safety/50' : 'opacity-50 text-textMuted cursor-not-allowed'
                  }`}
              >
                VIEW WORKER
              </button>
              <button
                onClick={() => navigate('/alerts')}
                className="py-2 rounded-md border border-danger/40 text-xs font-semibold text-danger hover:bg-danger/10 transition focus-ring flex items-center justify-center gap-1.5"
              >
                <BellRing size={12} /> ALERT SUPERVISOR
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-4 panel px-4 py-2.5 flex items-center gap-6 mono text-[0.68rem] text-textMuted">
        <span>{currentTime}</span>
        <span>GATE-02</span>
        <span>CAM-002</span>
        <span>AI VISION</span>
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
