import { Check, Mountain } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const STEPS = [
  { number: 1, label: 'Identity', path: '/entry/biometric' },
  { number: 2, label: 'Equipment', path: '/entry/scan-ppe' },
  { number: 3, label: 'Compliance', path: '/entry/compliance' },
];

export default function GateFlow({ step, children }) {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-bg rock-texture">
      <header className="border-b border-border bg-bgDeep/95">
        <div className="mx-auto flex h-16 max-w-[1320px] items-center justify-between px-4 sm:px-7">
          <button className="flex items-center gap-2 rounded focus-ring" onClick={() => navigate('/')}>
            <Mountain size={20} className="text-safety" />
            <span className="text-sm font-extrabold tracking-tight">SURAKSHA</span>
            <span className="hidden border-l border-border pl-3 label-op sm:inline">Gate entry</span>
          </button>
          <div className="flex items-center gap-1 sm:gap-3" aria-label={`Step ${step} of 3`}>
            {STEPS.map((item, index) => (
              <div key={item.number} className="flex items-center gap-1 sm:gap-3">
                {index > 0 && <span className={`h-px w-3 sm:w-8 ${step >= item.number ? 'bg-safety' : 'bg-border'}`} />}
                <div className={`flex items-center gap-2 ${step >= item.number ? 'text-safety' : 'text-textMuted'}`}>
                  <span className={`grid h-7 w-7 place-items-center rounded-full border text-[0.65rem] font-bold ${step >= item.number ? 'border-safety bg-safetySubtle' : 'border-border'}`}>
                    {step > item.number ? <Check size={13} /> : item.number}
                  </span>
                  <span className="hidden text-[0.65rem] font-bold uppercase tracking-wider md:inline">{item.label}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1320px] px-4 py-7 sm:px-7 sm:py-10">{children}</main>
    </div>
  );
}

export function GatePageHeader({ eyebrow, title, description }) {
  return (
    <div className="mb-7 max-w-2xl">
      <div className="mb-2 label-op !text-safety">{eyebrow}</div>
      <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{title}</h1>
      <p className="mt-2 text-sm leading-relaxed text-textSecondary">{description}</p>
    </div>
  );
}
