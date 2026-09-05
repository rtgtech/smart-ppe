import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mountain, Bell, User } from 'lucide-react';
import CaveNav from './CaveNav';
import MobileNav from './MobileNav';
import ThemeToggle from './ThemeToggle';
import VoiceControl from './VoiceControl';
import { useVoiceAgent } from '../hooks/useVoiceAgent';

function useClock() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return time;
}

export default function AppShell({ children }) {
  const navigate = useNavigate();
  const time = useClock();
  const voice = useVoiceAgent();
  const { beginPushToTalk, endPushToTalk } = voice;
  const controlHeld = useRef(false);
  const hh = String(time.getHours()).padStart(2, '0');
  const mm = String(time.getMinutes()).padStart(2, '0');
  const ss = String(time.getSeconds()).padStart(2, '0');

  useEffect(() => {
    const stopPushSession = () => {
      if (!controlHeld.current) return;
      controlHeld.current = false;
      endPushToTalk();
    };
    const onKeyDown = (event) => {
      if (event.code === 'ControlLeft') {
        if (!event.repeat && !controlHeld.current) {
          controlHeld.current = true;
          beginPushToTalk();
        }
        return;
      }
      if (controlHeld.current) stopPushSession();
    };
    const onKeyUp = (event) => {
      if (event.code === 'ControlLeft') stopPushSession();
    };
    const onVisibilityChange = () => {
      if (document.hidden) stopPushSession();
    };

    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    window.addEventListener('blur', stopPushSession);
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
      window.removeEventListener('blur', stopPushSession);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [beginPushToTalk, endPushToTalk]);

  return (
    <div className="min-h-screen bg-bg relative">
      {/* top status bar */}
      <header className="border-b border-border bg-bgDeep">
        <div className="max-w-[1440px] mx-auto px-5 lg:px-8 h-14 flex items-center justify-between">
          <button onClick={() => navigate('/dashboard')} className="flex items-center gap-2 focus-ring rounded">
            <Mountain size={18} className="text-safety" strokeWidth={2.4} />
            <span className="font-extrabold tracking-tight text-sm">SURAKSHA</span>
            <span className="hidden md:inline label-op border-l border-border pl-2 ml-1">CENTRAL COAL MINE</span>
            <span className="hidden md:inline label-op text-safety">SHIFT A</span>
          </button>

          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-1.5">
              <span className="status-dot bg-safety animate-pulseGlow" />
              <span className="label-op text-safety">LIVE</span>
            </div>
            <span className="mono text-xs text-textSecondary hidden sm:inline">{hh}:{mm}:{ss}</span>
            <ThemeToggle />
            <button className="p-1.5 text-textSecondary hover:text-text focus-ring rounded" onClick={() => navigate('/alerts')}>
              <Bell size={16} />
            </button>
            <button
              onClick={() => navigate('/settings/users')}
              className="flex items-center gap-2 pl-2 border-l border-border focus-ring rounded"
            >
              <div className="w-7 h-7 rounded-full bg-elevated border border-border flex items-center justify-center">
                <User size={13} className="text-textSecondary" />
              </div>
              <span className="hidden md:inline text-xs text-textSecondary">Safety Officer</span>
            </button>
          </div>
        </div>
      </header>

      {/* cave navigation */}
      <div className="max-w-[1440px] mx-auto px-5 lg:px-8">
        <CaveNav />
      </div>

      {/* content */}
      <main className="max-w-[1440px] mx-auto px-5 lg:px-8 pb-24 lg:pb-12 -mt-2 lg:mt-0">
        <div className="lg:hidden mb-4">
          <MobileTabs />
        </div>
        {children}
      </main>

      <MobileNav />
      <VoiceControl
        status={voice.status}
        mode={voice.mode}
        error={voice.error}
        transcript={voice.transcript}
        onToggle={voice.toggleSession}
        onDismissError={voice.clearError}
      />
    </div>
  );
}

function MobileTabs() {
  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-1 -mx-1 px-1">
      {['OVERVIEW', 'LIVE', 'WORKERS', 'PPE', 'ALERTS'].map((k) => (
        <span key={k} className="label-op whitespace-nowrap px-2 py-1 border border-border rounded">{k}</span>
      ))}
    </div>
  );
}
