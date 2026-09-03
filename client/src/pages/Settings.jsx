import { useNavigate } from 'react-router-dom';
import { Building2, DoorOpen, HardHat, Clock, BellRing, Bell, Users, ChevronRight } from 'lucide-react';
import { PageHeader } from '../components/ui';

const SECTIONS = [
  { key: 'MINE DETAILS', icon: Building2, desc: 'Mine name, location and registration details.', path: null },
  { key: 'GATE CONFIGURATION', icon: DoorOpen, desc: 'Configure gates, cameras and RFID readers.', path: null },
  { key: 'MANDATORY PPE', icon: HardHat, desc: 'Set which PPE items are required at entry.', path: '/settings/ppe' },
  { key: 'SHIFT CONFIGURATION', icon: Clock, desc: 'Define shift windows and supervisor assignments.', path: null },
  { key: 'ALERT RULES', icon: BellRing, desc: 'Thresholds for warnings, denials and escalation.', path: null },
  { key: 'NOTIFICATIONS', icon: Bell, desc: 'Delivery channels for officers and supervisors.', path: null },
  { key: 'USER MANAGEMENT', icon: Users, desc: 'Roles, access control and login activity.', path: '/settings/users' },
];

export default function Settings() {
  const navigate = useNavigate();
  return (
    <div className="animate-fadeUp">
      <PageHeader eyebrow="ADMINISTRATION" title="Settings" subtitle="Configure the mine, gates, PPE rules and access control." />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {SECTIONS.map((s) => (
          <button
            key={s.key}
            onClick={() => s.path && navigate(s.path)}
            className="panel p-5 flex items-center gap-4 text-left hover:border-safety/40 transition-colors rock-texture disabled:opacity-60"
          >
            <div className="w-10 h-10 rounded-md bg-elevated border border-border flex items-center justify-center shrink-0">
              <s.icon size={16} className="text-safety" />
            </div>
            <div className="flex-1">
              <div className="label-op !text-text !text-xs mb-1">{s.key}</div>
              <div className="text-[0.7rem] text-textSecondary">{s.desc}</div>
            </div>
            <ChevronRight size={14} className="text-textMuted shrink-0" />
          </button>
        ))}
      </div>
    </div>
  );
}
