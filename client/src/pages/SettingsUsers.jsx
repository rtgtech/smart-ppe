import { useNavigate } from 'react-router-dom';
import { ArrowLeft, UserPlus } from 'lucide-react';
import { PageHeader, Badge, Button } from '../components/ui';
import { USERS } from '../data/mockData';

export default function SettingsUsers() {
  const navigate = useNavigate();
  return (
    <div className="animate-fadeUp">
      <button onClick={() => navigate('/settings')} className="flex items-center gap-1.5 text-xs text-textSecondary hover:text-text mb-4 focus-ring">
        <ArrowLeft size={13} /> Back to Settings
      </button>
      <PageHeader
        eyebrow="ACCESS CONTROL"
        title="User Management"
        subtitle="Roles and login activity across mine administration."
        right={<Button><UserPlus size={13} /> ADD USER</Button>}
      />

      <div className="panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                {['User', 'Role', 'Mine', 'Last Login', 'Status'].map((h) => (
                  <th key={h} className="label-op text-left px-4 py-3 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {USERS.map((u, i) => (
                <tr key={i} className="border-b border-border/50 last:border-0 hover:bg-elevated/50">
                  <td className="px-4 py-3 font-semibold whitespace-nowrap">{u.name}</td>
                  <td className="px-4 py-3 text-textSecondary whitespace-nowrap">{u.role}</td>
                  <td className="px-4 py-3 text-textSecondary whitespace-nowrap">{u.mine}</td>
                  <td className="px-4 py-3 mono text-textSecondary whitespace-nowrap">{u.lastLogin}</td>
                  <td className="px-4 py-3"><Badge tone={u.status === 'ACTIVE' ? 'safety' : 'default'}>{u.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
