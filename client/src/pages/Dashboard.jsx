import { useNavigate } from 'react-router-dom';
import { LineChart, Line, ResponsiveContainer, YAxis, Tooltip } from 'recharts';
import { Users, LogIn, ShieldCheck, AlertTriangle, XCircle, Flame } from 'lucide-react';
import { PageHeader, StatCard, SectionHeader, Badge, StatusDot } from '../components/ui';
import { KPI, GATES, RECENT_EVENTS, PPE_TREND_30D } from '../data/mockData';

const SYSTEM_HEALTH = [
  { label: 'AI CAMERA', status: 'ONLINE' },
  { label: 'RFID', status: 'ONLINE' },
  { label: 'EDGE', status: 'ONLINE' },
  { label: 'DATABASE', status: 'ONLINE' },
  { label: 'NOTIFICATIONS', status: 'ONLINE' },
];

export default function Dashboard() {
  const navigate = useNavigate();
  return (
    <div className="animate-fadeUp">
      <PageHeader eyebrow="CENTRAL COAL MINE · SHIFT A" title="Command Center" subtitle="Real-time overview of workforce safety and PPE compliance." />

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 mb-8">
        <StatCard label="Workers Underground" value={KPI.workersUnderground} icon={Users} />
        <StatCard label="Today's Entries" value={KPI.todaysEntries.toLocaleString()} icon={LogIn} />
        <StatCard label="PPE Compliance" value={`${KPI.ppeCompliance}%`} tone="safety" icon={ShieldCheck} />
        <StatCard label="Violations" value={KPI.violations} tone="warning" icon={AlertTriangle} />
        <StatCard label="Entry Denied" value={KPI.entryDenied} tone="danger" icon={XCircle} />
        <StatCard label="High-Risk Workers" value={KPI.highRiskWorkers} tone="danger" icon={Flame} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5 mb-6">
        <div className="xl:col-span-2 panel p-5">
          <SectionHeader title="Live Gate Status" subtitle="Real-time throughput across all shaft entries" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {GATES.map((g) => (
              <button
                key={g.id}
                onClick={() => navigate('/live')}
                className="text-left panel-elevated p-4 hover:border-safety/50 transition-colors rock-texture relative overflow-hidden"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-sm">{g.name}</span>
                  <Badge tone={g.status === 'ONLINE' ? 'safety' : 'warning'}>
                    <StatusDot status={g.status} /> {g.status}
                  </Badge>
                </div>
                <div className="label-op mb-1">{g.label}</div>
                {g.status === 'ONLINE' ? (
                  <div className="text-xl font-bold mono">{g.workers} <span className="text-xs font-normal text-textSecondary">workers</span></div>
                ) : (
                  <div className="text-xs text-textMuted mono">— under scheduled maintenance —</div>
                )}
              </button>
            ))}
          </div>
        </div>

        <div className="panel p-5">
          <SectionHeader title="System Health" />
          <div className="space-y-2.5">
            {SYSTEM_HEALTH.map((s) => (
              <div key={s.label} className="flex items-center justify-between py-1.5 border-b border-border/60 last:border-0">
                <span className="text-xs text-textSecondary">{s.label}</span>
                <span className="flex items-center gap-1.5 text-xs font-semibold text-safety">
                  <StatusDot status={s.status} /> {s.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <div className="xl:col-span-2 panel p-5">
          <SectionHeader title="PPE Compliance" subtitle="30-day trend, mine-wide" action={<button onClick={() => navigate('/ppe')} className="label-op text-safety">VIEW ALL →</button>} />
          <div style={{ height: 180 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={PPE_TREND_30D}>
                <YAxis domain={[85, 100]} hide />
                <Tooltip contentStyle={{ background: 'rgb(var(--color-elevated))', border: '1px solid rgb(var(--color-border))', color: 'rgb(var(--color-text))', fontSize: 12 }} />
                <Line type="monotone" dataKey="compliance" stroke="rgb(var(--color-safety))" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel p-5">
          <SectionHeader title="Recent Safety Events" action={<button onClick={() => navigate('/alerts')} className="label-op text-safety">ALL →</button>} />
          <div className="space-y-3">
            {RECENT_EVENTS.slice(0, 3).map((e, i) => (
              <button
                key={i}
                onClick={() => navigate(`/workers/${e.workerId}`)}
                className="w-full text-left flex items-start gap-3 pb-3 border-b border-border/60 last:border-0 last:pb-0"
              >
                <span className="mono text-[0.68rem] text-textMuted mt-0.5">{e.time}</span>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold truncate">{e.worker}</div>
                  <div className="text-[0.7rem] text-textSecondary">{e.issue} · {e.gate}</div>
                </div>
                <Badge tone={e.severity === 'critical' ? 'danger' : 'warning'}>{e.decision}</Badge>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
