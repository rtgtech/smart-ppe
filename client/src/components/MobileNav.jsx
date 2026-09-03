import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import { NAV_ITEMS } from './CaveNav';

export default function MobileNav() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const primary = NAV_ITEMS.slice(0, 4);

  return (
    <>
      <div className="lg:hidden fixed bottom-0 left-0 right-0 z-40 border-t border-border bg-bgDeep/95 backdrop-blur">
        <div className="flex items-stretch">
          {primary.map(({ key, path, icon: Icon }) => {
            const active = location.pathname === path;
            return (
              <button
                key={key}
                onClick={() => navigate(path)}
                className={`flex-1 flex flex-col items-center gap-1 py-2.5 focus-ring ${active ? 'text-safety' : 'text-textSecondary'}`}
              >
                <Icon size={18} strokeWidth={2} />
                <span className="text-[0.58rem] tracking-wide">{key}</span>
              </button>
            );
          })}
          <button
            onClick={() => setOpen(true)}
            className="flex-1 flex flex-col items-center gap-1 py-2.5 text-textSecondary focus-ring"
          >
            <Menu size={18} />
            <span className="text-[0.58rem] tracking-wide">MORE</span>
          </button>
        </div>
      </div>

      {open && (
        <div className="lg:hidden fixed inset-0 z-50 bg-bg/95 backdrop-blur animate-fadeUp">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border">
            <span className="text-sm font-bold tracking-wide">NAVIGATE</span>
            <button onClick={() => setOpen(false)} className="p-2 text-textSecondary focus-ring">
              <X size={20} />
            </button>
          </div>
          <div className="grid grid-cols-2 gap-3 p-5">
            {NAV_ITEMS.map(({ key, path, icon: Icon }) => {
              const active = location.pathname === path;
              return (
                <button
                  key={key}
                  onClick={() => { navigate(path); setOpen(false); }}
                  className={`flex items-center gap-2 px-4 py-3.5 rounded-lg border focus-ring ${active ? 'border-safety text-text bg-elevated' : 'border-border text-textSecondary'
                    }`}
                >
                  <Icon size={16} />
                  <span className="label-op !text-xs">{key}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}
