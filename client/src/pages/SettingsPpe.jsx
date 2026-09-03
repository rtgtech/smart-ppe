import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { PageHeader } from '../components/ui';
import { MANDATORY_PPE } from '../data/mockData';

const STATES = ['REQUIRED', 'OPTIONAL', 'DISABLED'];

export default function SettingsPpe() {
  const navigate = useNavigate();
  const [config, setConfig] = useState(MANDATORY_PPE);

  function setState(key, state) {
    setConfig((prev) => prev.map((p) => (p.key === key ? { ...p, state } : p)));
  }

  return (
    <div className="animate-fadeUp">
      <button onClick={() => navigate('/settings')} className="flex items-center gap-1.5 text-xs text-textSecondary hover:text-text mb-4 focus-ring">
        <ArrowLeft size={13} /> Back to Settings
      </button>
      <PageHeader eyebrow="GATE ENTRY RULES" title="Mandatory PPE" subtitle="Configure which equipment this mine requires at every gate." />

      <div className="panel divide-y divide-border/60 overflow-hidden">
        {config.map((item) => (
          <div key={item.key} className="flex items-center justify-between px-5 py-4">
            <span className="text-sm font-medium">{item.label}</span>
            <div className="flex gap-1.5">
              {STATES.map((s) => (
                <button
                  key={s}
                  onClick={() => setState(item.key, s)}
                  className={`px-3 py-1.5 rounded-md border text-[0.65rem] font-bold uppercase tracking-wide transition-colors focus-ring ${
                    item.state === s
                      ? s === 'REQUIRED'
                        ? 'border-safety text-safety bg-safetySubtle'
                        : s === 'OPTIONAL'
                        ? 'border-warning text-warning bg-warningSubtle'
                        : 'border-textMuted text-textMuted bg-elevated'
                      : 'border-border text-textSecondary hover:text-text'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
