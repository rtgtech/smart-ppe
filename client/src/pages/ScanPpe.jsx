import { Check, QrCode, ScanLine, ShieldAlert } from 'lucide-react';
import { useEntry } from '../components/entry-context';

const ITEMS = ['Helmet', 'Reflective Vest', 'Safety Boots'];

export default function ScanPpe() {
  const { entry, connection, error } = useEntry();
  const evidence = entry?.evidence || {};
  return (
    <aside className="panel flex flex-col p-5 sm:p-6">
      <div className="flex items-center justify-between"><span className="label-op">Equipment · 2 of 3</span><span className={`text-[0.65rem] font-bold uppercase ${connection === 'online' ? 'text-safety' : 'text-danger'}`}>{connection}</span></div>
      <div className="mt-3 text-sm font-bold">{entry?.worker?.name || 'Recognizing worker…'}</div>
      <p className="mt-1 text-xs leading-relaxed text-textSecondary">Keep all PPE worn and show each assignment QR to the same camera until it reaches 3/5 frames.</p>
      <div className="my-5 space-y-3">
        {ITEMS.map((name) => {
          const visual = evidence.visual?.[name];
          const qr = evidence.qr?.[name];
          const done = visual?.state === 'CONFIRMED' && qr?.state === 'CONFIRMED';
          return (
            <div key={name} className={`rounded-lg border p-3 ${done ? 'border-safety/40 bg-safetySubtle' : 'border-border bg-input'}`}>
              <div className="flex items-center gap-3"><div className={`grid h-9 w-9 place-items-center rounded-md ${done ? 'bg-safety text-onSafety' : 'bg-elevated text-textMuted'}`}>{done ? <Check size={17} /> : <ShieldAlert size={17} />}</div><div className="flex-1"><div className="text-sm font-semibold">{name}</div><div className="mt-1 flex gap-3 text-[0.62rem] font-bold uppercase"><span className={visual?.state === 'CONFIRMED' ? 'text-safety' : 'text-textMuted'}>Visual {visual?.positive_frames || 0}/5</span><span className={qr?.state === 'CONFIRMED' ? 'text-safety' : 'text-textMuted'}>QR {qr?.max_frames || 0}/3</span></div></div><QrCode size={17} className={qr?.state === 'CONFIRMED' ? 'text-safety' : 'text-textMuted'} /></div>
            </div>
          );
        })}
      </div>
      <div className="mt-auto flex items-start gap-2 rounded-md border border-border bg-input p-3 text-xs leading-relaxed text-textSecondary"><ScanLine size={16} className="mt-0.5 shrink-0 text-safety" />QR decoding runs inside the same OpenCV frame pipeline. No second scanner or manual entry is accepted.</div>
      {error && <div className="mt-3 text-xs text-danger">{error}</div>}
    </aside>
  );
}
