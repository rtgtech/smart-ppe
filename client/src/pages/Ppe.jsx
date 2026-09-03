import { useEffect, useState } from 'react';
import { LineChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { PageHeader, StatCard, SectionHeader } from '../components/ui';
import { FilterBar } from '../components/DataFilters';
import { DEFAULT_FILTERS } from '../data/filters';
import { listGates } from '../services/gates';
import { getPpeSummary, getPpeTrend, getCommonViolations } from '../services/ppe';
import { getDashboard } from '../services/dashboard';

export default function Ppe() {
  const [items, setItems] = useState([]);
  const [trend, setTrend] = useState([]);
  const [violations, setViolations] = useState([]);
  const [kpi, setKpi] = useState({});
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [gates, setGates] = useState([]);
  useEffect(() => { listGates().then(setGates).catch(() => {}); }, []);
  useEffect(() => {
    Promise.all([getPpeSummary(filters), getPpeTrend(filters), getCommonViolations(filters), getDashboard(filters)]).then(([nextItems, nextTrend, nextViolations, dashboard]) => {
      setItems(nextItems); setTrend(nextTrend); setViolations(nextViolations); setKpi(dashboard.kpi || {});
    });
  }, [filters]);
  return (
    <div className="animate-fadeUp">
      <PageHeader eyebrow="MINE-WIDE" title="PPE Compliance" subtitle="Mine-wide PPE verification across every gate and shift." />
      <FilterBar filters={filters} setFilters={setFilters} gates={gates} />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <StatCard label="Overall" value={kpi.ppeCompliance == null ? '—' : `${kpi.ppeCompliance}%`} tone="safety" />
        <StatCard label="Verified Today" value={kpi.todaysEntries ?? '—'} />
        <StatCard label="Violations" value={kpi.violations ?? '—'} tone="warning" />
        <StatCard label="AI Confidence" value="—" tone="info" />
      </div>

      <div className="mb-6">
        <SectionHeader title="PPE Items" subtitle="Compliance rate per equipment category" />
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
          {items.map((p) => (
            <div key={p.key} className="panel p-4 rock-texture">
              <div className="label-op mb-2">{p.label}</div>
              <div className="text-xl font-bold mono mb-1">{p.compliance == null ? '—' : `${p.compliance}%`}</div>
              <div className={`flex items-center gap-1 text-[0.68rem] ${p.trend == null || p.trend >= 0 ? 'text-safety' : 'text-danger'}`}>
                {p.trend == null ? null : p.trend >= 0 ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                {p.trend == null ? 'No detections' : `${Math.abs(p.trend)}% · `}{p.trend == null ? '' : `${p.violations} violations`}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <div className="xl:col-span-2 panel p-5">
          <SectionHeader title="30-Day PPE Compliance" />
          <div style={{ height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend}>
                <CartesianGrid stroke="rgb(var(--color-grid))" vertical={false} />
                <XAxis dataKey="day" hide />
                <YAxis domain={[85, 100]} tick={{ fill: 'rgb(var(--color-text-muted))', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: 'rgb(var(--color-elevated))', border: '1px solid rgb(var(--color-border))', color: 'rgb(var(--color-text))', fontSize: 12 }} />
                <Line type="monotone" dataKey="compliance" stroke="rgb(var(--color-safety))" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel p-5">
          <SectionHeader title="Most Common Violations" />
          <div className="space-y-3.5">
            {violations.map((v) => (
              <div key={v.label}>
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-textSecondary">{v.label}</span>
                  <span className="mono font-semibold">{v.pct}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-elevated overflow-hidden">
                  <div className="h-full bg-warning rounded-full" style={{ width: `${v.pct * 3}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
