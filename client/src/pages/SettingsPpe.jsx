import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { PageHeader } from '../components/ui';
import { getMandatoryPpeConfig } from '../services/ppe';

export default function SettingsPpe() {
  const navigate = useNavigate();
  const [config, setConfig] = useState([]);
  useEffect(() => { getMandatoryPpeConfig().then(setConfig).catch(() => setConfig([])); }, []);

  return (
    <div className="animate-fadeUp">
      <button onClick={() => navigate('/settings')} className="flex items-center gap-1.5 text-xs text-textSecondary hover:text-text mb-4 focus-ring">
        <ArrowLeft size={13} /> Back to Settings
      </button>
      <PageHeader eyebrow="GATE ENTRY RULES" title="Mandatory PPE" subtitle="Helmet, Vest, and Boots are enforced at every gate." />

      <div className="panel divide-y divide-border/60 overflow-hidden">
        {config.map((item) => (
          <div key={item.key} className="flex items-center justify-between px-5 py-4">
            <span className="text-sm font-medium">{item.label}</span>
            <span className="rounded-md border border-safety bg-safetySubtle px-3 py-1.5 text-[0.65rem] font-bold uppercase tracking-wide text-safety">Required</span>
          </div>
        ))}
      </div>
    </div>
  );
}
