import { useCallback, useEffect, useRef, useState } from 'react';
import { ScanFace, ShieldCheck, UserRoundCheck } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import AnnotatedVisionFeed from '../components/AnnotatedVisionFeed';
import GateFlow, { GatePageHeader } from '../components/GateFlow';
import { getGateContext, resetGateSession, writeGateSession } from '../services/gateCheck';

const HOLD_MS = 1200;
const MISSED_FRAME_GRACE_MS = 650;

export default function Biometric() {
  const navigate = useNavigate();
  const candidateRef = useRef({ personId: '', since: 0, lastSeen: 0 });
  const resolvingRef = useRef(false);
  const [connection, setConnection] = useState('offline');
  const [candidate, setCandidate] = useState(null);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('Position your face inside the camera frame.');
  const [error, setError] = useState('');

  useEffect(() => { resetGateSession(); }, []);

  const handleFrame = useCallback((meta) => {
    const recognized = (meta.faces || []).filter((face) => face.recognized);
    const now = performance.now();
    if (recognized.length !== 1) {
      if (candidateRef.current.personId && now - candidateRef.current.lastSeen <= MISSED_FRAME_GRACE_MS) {
        setStatus('Face found. Keep looking at the camera…');
        return;
      }
      candidateRef.current = { personId: '', since: 0, lastSeen: 0 };
      resolvingRef.current = false;
      setCandidate(null);
      setProgress(0);
      setStatus(recognized.length > 1 ? 'Only one worker may enter the frame.' : 'Looking for an enrolled face…');
      return;
    }

    const face = recognized[0];
    const changedPerson = candidateRef.current.personId !== face.person_id;
    const recognitionExpired = now - candidateRef.current.lastSeen > MISSED_FRAME_GRACE_MS;
    if (changedPerson || recognitionExpired) {
      candidateRef.current = { personId: face.person_id, since: now, lastSeen: now };
      resolvingRef.current = false;
      setCandidate(face);
      setProgress(0);
      setError('');
      setStatus('Face found. Hold still for verification.');
      return;
    }

    candidateRef.current.lastSeen = now;
    const elapsed = now - candidateRef.current.since;
    setCandidate(face);
    setProgress(Math.min(100, Math.round(elapsed * 100 / HOLD_MS)));
    if (elapsed < HOLD_MS || resolvingRef.current) return;

    resolvingRef.current = true;
    setStatus('Identity verified. Loading assigned equipment…');
    getGateContext(face.person_id)
      .then((context) => {
        if (candidateRef.current.personId !== face.person_id) return;
        writeGateSession({
          worker: context.worker,
          gate: context.gate,
          requiredItems: context.required_items,
          biometric: { verified: true, similarity: face.similarity, verifiedAt: new Date().toISOString() },
          scannedItems: [],
        });
        navigate('/scan-ppe', { replace: true });
      })
      .catch((caught) => {
        const message = caught.message || 'The recognized face is not linked to an active worker.';
        setStatus(`Face recognized as ${face.name}, but entry cannot continue.`);
        setError(`${message} Create or activate worker ${face.person_id}, then enroll that worker again if necessary.`);
      });
  }, [navigate]);

  return (
    <GateFlow step={1}>
      <GatePageHeader eyebrow="Step 1 · Biometric" title="Verify your identity" description="Look directly at the camera. Recognition must remain stable before equipment scanning begins." />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.7fr)_minmax(300px,0.8fr)]">
        <div className="panel relative min-h-[480px] overflow-hidden">
          <AnnotatedVisionFeed active onConnectionChange={setConnection} onFrameMeta={handleFrame} />
          <div className="pointer-events-none absolute inset-0 grid place-items-center">
            <div className={`h-64 w-48 rounded-[45%] border-2 transition-colors ${candidate ? 'border-safety shadow-glow' : 'border-white/35'}`} />
          </div>
        </div>

        <aside className="panel flex flex-col p-5 sm:p-6">
          <div className="flex items-center justify-between">
            <span className="label-op">Identity status</span>
            <span className={`status-dot ${connection === 'online' ? 'bg-safety animate-pulseGlow' : 'bg-danger'}`} />
          </div>
          <div className="my-8 flex flex-col items-center text-center">
            <div className={`grid h-20 w-20 place-items-center rounded-full border ${candidate ? 'border-safety bg-safetySubtle text-safety' : 'border-border bg-elevated text-textMuted'}`}>
              {candidate ? <UserRoundCheck size={34} /> : <ScanFace size={34} />}
            </div>
            <div className="mt-4 text-lg font-bold">{candidate?.name || 'Waiting for worker'}</div>
            <div className="mt-1 mono text-xs text-textMuted">{candidate?.person_id || 'NO IDENTITY'}</div>
            {candidate?.similarity != null && <div className="mt-2 text-xs text-safety">Match confidence {(candidate.similarity * 100).toFixed(1)}%</div>}
          </div>
          <div className="mt-auto">
            <div className="mb-2 flex justify-between text-xs text-textSecondary"><span>{status}</span><span className="mono">{progress}%</span></div>
            <div className="h-2 overflow-hidden rounded-full bg-elevated"><div className="h-full bg-safety transition-[width] duration-150" style={{ width: `${progress}%` }} /></div>
            {error && <div className="mt-4 rounded-md border border-dangerBorder bg-dangerSubtle p-3 text-xs text-danger">{error}</div>}
            <div className="mt-5 flex items-start gap-2 text-xs leading-relaxed text-textMuted"><ShieldCheck size={14} className="mt-0.5 shrink-0 text-safety" />Biometric frames are processed locally by the configured vision service.</div>
          </div>
        </aside>
      </div>
    </GateFlow>
  );
}
