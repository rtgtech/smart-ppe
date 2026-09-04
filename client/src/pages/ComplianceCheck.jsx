import { Check, Footprints, Glasses, Hand, HardHat, LoaderCircle, Shield, ShieldCheck, ShieldX } from 'lucide-react';
import { useEntry } from '../components/entry-context';

const ITEMS = [['Gloves', Hand], ['Goggles', Glasses], ['Helmet', HardHat], ['Mask', Shield], ['Shoes', Footprints]];

export default function ComplianceCheck() {
  const { entry, nextWorker } = useEntry();
  const active = entry?.lifecycle === 'ACTIVE';
  const allowed = entry?.verdict === 'ALLOWED';
  const visual = entry?.evidence?.visual || {};
  return (
    <aside className="panel flex flex-col p-6">
      <span className="label-op">PPE compliance · 2 of 2</span>
      <div className="mt-5 rounded-md border border-border bg-input p-3"><p className="font-bold">{entry?.worker?.name || 'Worker'}</p><p className="font-mono text-[11px] text-textMuted">{entry?.worker?.employee_code}</p></div>
      {active ? <div className="my-5 flex items-center gap-3 rounded-lg border border-warning/40 bg-warningSubtle p-4 text-warning"><LoaderCircle className="animate-spin" /><div><p className="font-bold">Checking worn PPE</p><p className="text-xs text-textSecondary">Keep your full body, hands, and feet visible.</p></div></div> : <div className={`my-5 flex items-center gap-3 rounded-lg border p-4 ${allowed ? 'border-safety text-safety' : 'border-dangerBorder text-danger'}`}>{allowed ? <ShieldCheck size={34} /> : <ShieldX size={34} />}<div><p className="text-2xl font-extrabold">{entry?.verdict}</p><p className="text-xs text-textSecondary">Barrier {entry?.interventions?.barrier}</p></div></div>}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">{ITEMS.map(([name, Icon]) => { const state = visual[name]?.state; return <div key={name} className={`rounded-lg border p-2 text-center ${state === 'CONFIRMED' ? 'border-safety text-safety' : state === 'MISSING' ? 'border-dangerBorder text-danger' : 'border-border text-textMuted'}`}><Icon className="mx-auto" size={18} /><p className="mt-1 text-xs font-bold">{name}</p><p className="mt-1 font-mono text-[9px]">{state || 'SCANNING'}</p></div>; })}</div>
      {!active && <div className="mt-4 space-y-2">{(entry?.reasons?.length ? entry.reasons : ['ALL_REQUIRED_PPE_CONFIRMED']).map((reason) => <p key={reason} className="rounded border border-border bg-input px-3 py-2 font-mono text-[10px] text-textSecondary">{reason.replaceAll('_', ' ')}</p>)}</div>}
      {!active && <button onClick={nextWorker} className="mt-auto flex w-full items-center justify-center gap-2 rounded-md bg-safety py-3 text-xs font-bold uppercase text-onSafety"><Check size={15} /> Process next worker</button>}
    </aside>
  );
}
