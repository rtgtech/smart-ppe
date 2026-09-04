import { ScanFace, ShieldCheck, UserRoundCheck } from 'lucide-react';
import { useEntry } from '../components/entry-context';

export default function Biometric() {
  const { entry, connection, error, start } = useEntry();
  const identity = entry?.evidence?.identity;
  const confirmed = identity?.state === 'CONFIRMED';
  return (
    <aside className="panel flex flex-col p-5 sm:p-6">
      <div className="flex items-center justify-between"><span className="label-op">Identity · 1 of 3</span><span className={`status-dot ${connection === 'online' ? 'bg-safety animate-pulseGlow' : 'bg-danger'}`} /></div>
      <div className="my-8 flex flex-col items-center text-center">
        <div className={`grid h-20 w-20 place-items-center rounded-full border ${confirmed ? 'border-safety bg-safetySubtle text-safety' : 'border-border bg-elevated text-textMuted'}`}>{confirmed ? <UserRoundCheck size={34} /> : <ScanFace size={34} />}</div>
        <div className="mt-4 text-lg font-bold">{entry?.worker?.name || 'Waiting for one worker'}</div>
        <div className="mt-1 mono text-xs text-textMuted">{entry?.worker?.employee_code || 'NO STABLE IDENTITY'}</div>
        {identity?.confidence != null && <div className="mt-2 text-xs text-safety">Match confidence {identity.confidence.toFixed(1)}%</div>}
      </div>
      <div className="mt-auto space-y-4">
        <div className="rounded-md border border-border bg-input p-3 text-xs leading-relaxed text-textSecondary">Only one worker may be in frame. Keep the full body visible while identity is confirmed in three of five frames.</div>
        {error && <div className="rounded-md border border-dangerBorder bg-dangerSubtle p-3 text-xs text-danger">{error}</div>}
        {!entry && <button onClick={start} className="flex w-full items-center justify-center gap-2 rounded-md bg-safety py-3 text-xs font-bold uppercase text-onSafety"><ShieldCheck size={15} /> Start scan</button>}
      </div>
    </aside>
  );
}
