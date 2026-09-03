import { BarChart, Bar, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { BrainCircuit, ArrowRight } from 'lucide-react';
import { PageHeader, SectionHeader, Badge } from '../components/ui';
import { SHIFT_COMPARISON, GATE_VIOLATIONS, WORKERS, MOST_COMMON_VIOLATIONS } from '../data/mockData';

const HIGH_RISK = WORKERS.filter((w) => w.risk === 'HIGH');

export default function Insights() {
  return (
    <div className="animate-fadeUp">
      <PageHeader eyebrow="ANALYTICS" title="Safety Insights" subtitle="Turning compliance data into preventive action." />

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 mb-5">
        <div className="panel p-5">
          <SectionHeader title="Shift Comparison" subtitle="Compliance rate by shift" />
          <div style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={SHIFT_COMPARISON}>
                <CartesianGrid stroke="rgb(var(--color-grid))" vertical={false} />
                <XAxis dataKey="shift" tick={{ fill: 'rgb(var(--color-text-secondary))', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis domain={[80, 100]} tick={{ fill: 'rgb(var(--color-text-muted))', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: 'rgb(var(--color-elevated))', border: '1px solid rgb(var(--color-border))', color: 'rgb(var(--color-text))', fontSize: 12 }} />
                <Bar dataKey="compliance" fill="rgb(var(--color-safety))" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel p-5">
          <SectionHeader title="Gate Violations" subtitle="Denials logged per online gate (30 days)" />
          <div style={{ height: 200 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={GATE_VIOLATIONS}>
                <CartesianGrid stroke="rgb(var(--color-grid))" vertical={false} />
                <XAxis dataKey="gate" tick={{ fill: 'rgb(var(--color-text-secondary))', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'rgb(var(--color-text-muted))', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: 'rgb(var(--color-elevated))', border: '1px solid rgb(var(--color-border))', color: 'rgb(var(--color-text))', fontSize: 12 }} />
                <Bar dataKey="denials" fill="rgb(var(--color-warning))" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 mb-5">
        <div className="panel p-5">
          <SectionHeader title="High-Risk Workers" subtitle={`${HIGH_RISK.length} workers flagged for repeated violations`} />
          <div className="space-y-2">
            {HIGH_RISK.map((w) => (
              <div key={w.id} className="flex items-center justify-between py-2 border-b border-border/60 last:border-0">
                <div>
                  <div className="text-xs font-semibold">{w.name}</div>
                  <div className="mono text-[0.65rem] text-textMuted">{w.id} · {w.department}</div>
                </div>
                <Badge tone="danger">{w.violations} violations</Badge>
              </div>
            ))}
          </div>
        </div>

        <div className="panel p-5">
          <SectionHeader title="Most Missed PPE" />
          <div className="space-y-3">
            {MOST_COMMON_VIOLATIONS.map((v) => (
              <div key={v.label} className="flex items-center justify-between">
                <span className="text-xs text-textSecondary">{v.label}</span>
                <span className="mono text-xs font-semibold">{v.pct}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="panel-elevated p-6 border-safety/30 rock-texture">
        <div className="flex items-center gap-2 mb-4">
          <BrainCircuit size={18} className="text-safety" />
          <span className="label-op !text-safety">Safety Intelligence</span>
        </div>
        <ul className="space-y-2.5 mb-5">
          <Insight text="Gas detector compliance has decreased 4.2% during Shift B over the last 14 days." />
          <Insight text="12 workers have repeated PPE violations." />
          <Insight text="Gate 02 records the highest number of entry denials." />
        </ul>
        <div className="flex items-start gap-2 panel px-4 py-3">
          <ArrowRight size={14} className="text-safety mt-0.5 shrink-0" />
          <div>
            <div className="label-op !text-safety mb-1">Recommended Action</div>
            <div className="text-sm">Conduct a targeted PPE inspection for Shift B before underground deployment.</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Insight({ text }) {
  return (
    <li className="flex items-start gap-2 text-sm text-textSecondary">
      <span className="status-dot bg-safety mt-1.5 shrink-0" />
      {text}
    </li>
  );
}
