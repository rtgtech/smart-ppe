import { ScanFace, ShieldCheck, UserRoundCheck } from 'lucide-react';
import { useEntry } from '../components/entry-context';

export default function Biometric() {
  const { entry, connection, error, start } = useEntry();
  const identity = entry?.evidence?.identity;
  const confirmed = identity?.state === 'CONFIRMED';
  return (
    <aside className="panel flex flex-col p-6">
      <div className="flex justify-between"><span className="label-op">Biometric · 1 of 2</span><span className={`status-dot ${connection === 'online' ? 'bg-safety' : 'bg-danger'}`} /></div>
      <div className="my-8 text-center">
        <div className={`mx-auto grid h-20 w-20 place-items-center rounded-full border ${confirmed ? 'border-safety text-safety' : 'border-border text-textMuted'}`}>{confirmed ? <UserRoundCheck size={36} /> : <ScanFace size={36} />}</div>
        <h2 className="mt-4 text-lg font-bold">{entry?.worker?.name || 'Look at the camera'}</h2>
        <p className="mt-1 text-xs text-textMuted">{identity?.state?.replaceAll('_', ' ') || 'Ready to scan'}</p>
        {identity && <p className="mt-3 font-mono text-xs text-safety">Match {identity.supporting_frames}/{identity.required_frames}</p>}
        {identity?.confidence != null && <p className="mt-1 text-xs">Match confidence {identity.confidence.toFixed(1)}%</p>}
      </div>
      <p className="rounded-md border border-border bg-input p-3 text-xs leading-relaxed text-textSecondary">Keep one face centered and well lit. PPE detection begins immediately after recognition.</p>
      {error && <p className="mt-3 rounded-md border border-dangerBorder bg-dangerSubtle p-3 text-xs text-danger">{error}</p>}
      {!entry && <button onClick={start} className="mt-auto flex w-full items-center justify-center gap-2 rounded-md bg-safety py-3 text-xs font-bold uppercase text-onSafety"><ShieldCheck size={15} /> Start scan</button>}
    </aside>
  );
}
