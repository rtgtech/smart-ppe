import { PageHeader, StatCard, SectionHeader, Badge } from '../components/ui';
import { KPI, ZONES, ATTENDANCE_ROWS } from '../data/mockData';

export default function Attendance() {
  return (
    <div className="animate-fadeUp">
      <PageHeader eyebrow="REAL-TIME" title="Workforce Presence" subtitle="Underground occupancy and gate throughput." />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <StatCard label="Entered Today" value={KPI.todaysEntries.toLocaleString()} />
        <StatCard label="Exited Today" value="514" />
        <StatCard label="Currently Underground" value={KPI.workersUnderground} tone="safety" />
        <StatCard label="Missing Exit Scans" value="17" tone="warning" />
      </div>

      <div className="panel p-5 mb-6">
        <SectionHeader title="Underground Workforce" subtitle="Live headcount by mine zone" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {ZONES.map((z) => (
            <div key={z.zone} className="panel-elevated p-4 text-center rock-texture">
              <div className="label-op mb-2">{z.zone}</div>
              <div className="text-2xl font-bold mono text-safety">{z.count}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="panel overflow-hidden">
        <div className="p-5 pb-0"><SectionHeader title="Worker Presence" /></div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                {['Worker', 'Entry', 'Exit', 'PPE', 'Location', 'Status'].map((h) => (
                  <th key={h} className="label-op text-left px-4 py-3 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ATTENDANCE_ROWS.map((r) => (
                <tr key={r.workerId} className="border-b border-border/50 last:border-0 hover:bg-elevated/50">
                  <td className="px-4 py-3 whitespace-nowrap">
                    <div className="font-semibold">{r.worker}</div>
                    <div className="mono text-[0.68rem] text-textMuted">{r.workerId}</div>
                  </td>
                  <td className="px-4 py-3 mono">{r.entry}</td>
                  <td className="px-4 py-3 mono text-textSecondary">{r.exit}</td>
                  <td className="px-4 py-3"><Badge tone={r.ppe === 'VERIFIED' ? 'safety' : 'warning'}>{r.ppe}</Badge></td>
                  <td className="px-4 py-3 text-textSecondary">{r.location}</td>
                  <td className="px-4 py-3"><Badge tone={r.status === 'UNDERGROUND' ? 'info' : 'default'}>{r.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
