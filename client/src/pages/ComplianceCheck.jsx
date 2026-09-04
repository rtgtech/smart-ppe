import { AlertTriangle, Check, ShieldCheck, ShieldX } from 'lucide-react';
import { useEntry } from '../components/entry-context';

export default function ComplianceCheck() {
  const { entry, nextWorker } = useEntry();
  const verdict = entry?.verdict;
  const allowed = verdict === 'ALLOWED';
  const denied = verdict === 'DENIED';
  const tone = allowed ? 'border-safety/45 bg-safetySubtle text-safety' : denied ? 'border-dangerBorder bg-dangerSubtle text-danger' : 'border-warning/40 bg-warningSubtle text-warning';
  const Icon = allowed ? ShieldCheck : denied ? ShieldX : AlertTriangle;
  return (
    <aside className="panel flex flex-col p-5 sm:p-6">
      <div className="label-op">Verdict · 3 of 3</div>
      <div className={`my-6 rounded-lg border p-5 ${tone}`}>
        <div className="flex items-center gap-3"><Icon size={34} /><div><div className="text-2xl font-extrabold">{verdict || 'HOLD'}</div><div className="mt-1 text-xs text-textSecondary">Barrier {entry?.interventions?.barrier || 'LOCKED'} · {entry?.interventions?.indicator || 'AMBER'}</div></div></div>
      </div>
      {entry?.worker && <div className="rounded-md border border-border bg-input p-3"><div className="text-sm font-bold">{entry.worker.name}</div><div className="mono text-[0.65rem] text-textMuted">{entry.worker.employee_code} · {entry.gate?.name}</div></div>}
      <div className="mt-4"><div className="label-op mb-2">Decision evidence</div><div className="space-y-1.5">{(entry?.reasons?.length ? entry.reasons : ['ALL_REQUIRED_EVIDENCE_CONFIRMED']).map((reason) => <div key={reason} className="rounded border border-border bg-input px-3 py-2 mono text-[0.65rem] text-textSecondary">{reason.replaceAll('_', ' ')}</div>)}</div></div>
      <div className="mt-4 grid grid-cols-2 gap-2 text-center"><Metric label="Identity" value={entry?.identity_confidence} /><Metric label="Evidence" value={entry?.evidence_confidence} /></div>
      <button onClick={nextWorker} className="mt-auto flex w-full items-center justify-center gap-2 rounded-md bg-safety py-3 text-xs font-bold uppercase tracking-wide text-onSafety"><Check size={15} /> Process next worker</button>
    </aside>
  );
}

function Metric({ label, value }) {
  return <div className="rounded-md border border-border bg-input p-3"><div className="mono text-lg font-bold">{value == null ? '—' : `${value.toFixed(1)}%`}</div><div className="label-op mt-1">{label}</div></div>;
}
