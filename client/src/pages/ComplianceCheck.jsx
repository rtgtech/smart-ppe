import { AlertTriangle, Check, Footprints, HardHat, LoaderCircle, ShieldCheck, ShieldX, Shirt } from 'lucide-react';
import { useEntry } from '../components/entry-context';

const ITEMS = [
  { name: 'Helmet', icon: HardHat },
  { name: 'Vest', icon: Shirt },
  { name: 'Boots', icon: Footprints },
];

export default function ComplianceCheck() {
  const { entry, nextWorker } = useEntry();
  const verdict = entry?.verdict;
  const allowed = verdict === 'ALLOWED';
  const denied = verdict === 'DENIED';
  const active = entry?.lifecycle === 'ACTIVE';
  const evidence = entry?.evidence || {};
  const tone = allowed ? 'border-safety/45 bg-safetySubtle text-safety' : denied ? 'border-dangerBorder bg-dangerSubtle text-danger' : 'border-warning/40 bg-warningSubtle text-warning';
  const Icon = allowed ? ShieldCheck : denied ? ShieldX : AlertTriangle;

  return (
    <aside className="panel flex flex-col p-5 sm:p-6">
      <div className="label-op">PPE compliance · 2 of 2</div>
      {entry?.worker && (
        <div className="mt-5 rounded-md border border-border bg-input p-3">
          <div className="text-sm font-bold">{entry.worker.name}</div>
          <div className="mono text-[0.65rem] text-textMuted">{entry.worker.employee_code} · {entry.gate?.name}</div>
        </div>
      )}

      {active ? (
        <div className="my-6 rounded-lg border border-warning/40 bg-warningSubtle p-4 text-warning">
          <div className="flex items-center gap-3">
            <LoaderCircle className="animate-spin" size={26} />
            <div>
              <div className="font-bold">Checking correctly worn PPE</div>
              <div className="mt-1 text-xs text-textSecondary">Keep your head, torso, and both feet visible.</div>
            </div>
          </div>
        </div>
      ) : (
        <div className={`my-6 rounded-lg border p-5 ${tone}`}>
          <div className="flex items-center gap-3">
            <Icon size={34} />
            <div>
              <div className="text-2xl font-extrabold">{verdict || 'HOLD'}</div>
              <div className="mt-1 text-xs text-textSecondary">Barrier {entry?.interventions?.barrier || 'LOCKED'} · {entry?.interventions?.indicator || 'AMBER'}</div>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-3 gap-2">
        {ITEMS.map(({ name, icon: ItemIcon }) => {
          const state = evidence.visual?.[name]?.state;
          const confirmed = state === 'CONFIRMED';
          const missing = state === 'MISSING';
          return (
            <div key={name} className={`rounded-lg border p-2.5 text-center ${confirmed ? 'border-safety/50 bg-safetySubtle text-safety' : missing ? 'border-dangerBorder bg-dangerSubtle text-danger' : 'border-border bg-input text-textMuted'}`}>
              <ItemIcon className="mx-auto mb-1" size={18} />
              <div className="text-xs font-bold">{name}</div>
              <div className="mt-0.5 font-mono text-[0.58rem] uppercase tracking-wider">
                {confirmed ? 'Correctly worn' : missing ? 'Not worn' : 'Scanning'}
              </div>
            </div>
          );
        })}
      </div>

      {!active && (
        <div className="mt-4">
          <div className="label-op mb-2">Decision evidence</div>
          <div className="space-y-1.5">
            {(entry?.reasons?.length ? entry.reasons : ['ALL_REQUIRED_EVIDENCE_CONFIRMED']).map((reason) => (
              <div key={reason} className="rounded border border-border bg-input px-3 py-2 mono text-[0.65rem] text-textSecondary">{reason.replaceAll('_', ' ')}</div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-4 grid grid-cols-2 gap-2 text-center">
        <Metric label="Identity" value={entry?.identity_confidence} />
        <Metric label="Evidence" value={entry?.evidence_confidence} />
      </div>
      {!active && (
        <button onClick={nextWorker} className="mt-auto flex w-full items-center justify-center gap-2 rounded-md bg-safety py-3 text-xs font-bold uppercase tracking-wide text-onSafety">
          <Check size={15} /> Process next worker
        </button>
      )}
    </aside>
  );
}

function Metric({ label, value }) {
  return <div className="rounded-md border border-border bg-input p-3"><div className="mono text-lg font-bold">{value == null ? '—' : `${value.toFixed(1)}%`}</div><div className="label-op mt-1">{label}</div></div>;
}
