import { useNavigate } from 'react-router-dom';
import { Mountain, ScanFace, Nfc, ShieldCheck, WifiOff, FileCheck2 } from 'lucide-react';
import CaveBackdrop from '../components/CaveBackdrop';
import ThemeToggle from '../components/ThemeToggle';

const FEATURES = [
  { icon: ScanFace, label: 'AI VISION' },
  { icon: Nfc, label: 'RFID / NFC' },
  { icon: ShieldCheck, label: 'REAL-TIME VERIFICATION' },
  { icon: WifiOff, label: 'OFFLINE-FIRST' },
  { icon: FileCheck2, label: 'AUDIT READY' },
];

export default function Home() {
  const navigate = useNavigate();
  return (
    <div className="relative min-h-screen overflow-hidden flex flex-col">
      <CaveBackdrop />

      <header className="relative z-10 max-w-[1440px] w-full mx-auto px-6 lg:px-10 pt-8 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Mountain size={22} className="text-safety" strokeWidth={2.4} />
          <div>
            <div className="font-extrabold tracking-tight leading-none">SURAKSHA</div>
            <div className="label-op !text-[0.58rem] !text-textMuted leading-none mt-0.5">MINE SAFETY INTELLIGENCE</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <button
            onClick={() => navigate('/login')}
            className="label-op !text-xs border border-border px-3.5 py-2 rounded-md hover:border-safety hover:text-safety transition-colors focus-ring"
          >
            SECURE ACCESS
          </button>
        </div>
      </header>

      <div className="relative z-10 flex-1 max-w-[1440px] w-full mx-auto px-6 lg:px-10 flex flex-col justify-center items-start py-16">
        <div className="label-op text-safety mb-4 flex items-center gap-2">
          <span className="status-dot bg-safety animate-pulseGlow" /> SYSTEM ONLINE — 5 MINES CONNECTED
        </div>
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.05] max-w-3xl">
          EVERY WORKER.<br />EVERY GATE.<br />EVERY TIME.
        </h1>
        <p className="text-textSecondary mt-6 max-w-lg text-sm sm:text-base leading-relaxed">
          Smart PPE compliance monitoring for safer underground mining operations —
          AI vision and RFID verification at every gate, online or off.
        </p>

        <div className="flex flex-wrap gap-3 mt-8">
          <button
            onClick={() => navigate('/dashboard')}
            className="px-6 py-3 rounded-md bg-safety text-onSafety font-bold text-sm tracking-wide shadow-glow hover:brightness-110 transition focus-ring"
          >
            ENTER COMMAND CENTER
          </button>
          <button
            onClick={() => navigate('/live')}
            className="px-6 py-3 rounded-md border border-border text-text font-bold text-sm tracking-wide hover:border-safety hover:text-safety transition focus-ring"
          >
            SEE LIVE MONITORING
          </button>
        </div>
      </div>

      <div className="relative z-10 max-w-[1440px] w-full mx-auto px-6 lg:px-10 pb-8">
        <div className="flex flex-wrap items-center gap-x-8 gap-y-3 border-t border-border/70 pt-6">
          {FEATURES.map(({ icon: Icon, label }) => (
            <div key={label} className="flex items-center gap-2 text-textSecondary">
              <Icon size={14} className="text-safety" />
              <span className="label-op !text-[0.62rem]">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
