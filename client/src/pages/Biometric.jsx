import { ScanFace, ShieldCheck, UserRoundCheck } from 'lucide-react';
import { useEntry } from '../components/entry-context';

export default function Biometric() {
  const { entry, connection, error, start } = useEntry();
  const identity = entry?.evidence?.identity;
  const confirmed = identity?.state === 'CONFIRMED';

  return (
    <aside className="panel flex flex-col p-5 sm:p-6">
      <div className="flex items-center justify-between">
        <span className="label-op">Verification · 1 of 2</span>
        <span className={`status-dot ${connection === 'online' ? 'bg-safety animate-pulseGlow' : 'bg-danger'}`} />
      </div>

      <div className="my-5 flex flex-col items-center text-center">
        <div className={`grid h-16 w-16 place-items-center rounded-full border ${confirmed ? 'border-safety bg-safetySubtle text-safety' : 'border-border bg-elevated text-textMuted'}`}>
          {confirmed ? <UserRoundCheck size={30} /> : <ScanFace size={30} />}
        </div>
        <div className="mt-3 text-base font-bold">{entry?.worker?.name || 'Waiting for worker…'}</div>
        <div className="mt-0.5 mono text-xs text-textMuted">{entry?.worker?.employee_code || 'STAND IN FRAME'}</div>
        {identity?.confidence != null && <div className="mt-1.5 text-xs text-safety font-medium">Identity Match {identity.confidence.toFixed(1)}%</div>}
      </div>

      <div className="mt-auto space-y-3">
        <div className="rounded-md border border-border bg-input p-3 text-xs leading-relaxed text-textSecondary">
          Face the camera and remain still. After your identity is confirmed, the next step will verify that your PPE is correctly worn.
        </div>
        {error && <div className="rounded-md border border-dangerBorder bg-dangerSubtle p-3 text-xs text-danger">{error}</div>}
        {!entry && (
          <button onClick={start} className="flex w-full items-center justify-center gap-2 rounded-md bg-safety py-3 text-xs font-bold uppercase text-onSafety shadow-glow">
            <ShieldCheck size={15} /> Start scan
          </button>
        )}
      </div>
    </aside>
  );
}
