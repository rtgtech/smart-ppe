import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { PageHeader } from '../components/ui';
import { getMandatoryPpeConfig } from '../services/ppe';
import { apiRequest } from '../services/api';

// The current database stores only is_mandatory, so disabled is not a persisted state.
const STATES = ['REQUIRED', 'OPTIONAL'];

export default function SettingsPpe() {
  const navigate = useNavigate();
  const [config, setConfig] = useState([]);
  useEffect(() => { getMandatoryPpeConfig().then(setConfig).catch(() => setConfig([])); }, []);

  function setState(key, state) {
    const item = config.find((p) => p.key === key);
    if (!item) return;
    const isMandatory = state === 'REQUIRED';
    apiRequest(`/ppe/items/${item.ppe_id}`, { method: 'PATCH', body: JSON.stringify({ is_mandatory: isMandatory }) })
      .then(() => setConfig((prev) => prev.map((p) => (p.key === key ? { ...p, state } : p))))
      .catch(() => {});
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
                      : 'border-warning text-warning bg-warningSubtle'
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
