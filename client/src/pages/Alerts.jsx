import { useState, useMemo, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, CheckCircle2, ArrowUpCircle } from 'lucide-react';
import { PageHeader, StatCard, Badge } from '../components/ui';
import { listAlerts, updateAlert } from '../services/alerts';
import { listGates } from '../services/gates';
import { FilterBar } from '../components/DataFilters';
import { DEFAULT_FILTERS } from '../data/filters';

const FILTERS = ['ALL', 'CRITICAL', 'WARNING', 'RESOLVED'];

export default function Alerts() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState('ALL');
  const [alerts, setAlerts] = useState([]);
  const [error, setError] = useState('');
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [gates, setGates] = useState([]);

  useEffect(() => { listGates().then(setGates).catch(() => {}); }, []);
  useEffect(() => { listAlerts(filters).then(setAlerts).catch((err) => setError(err.message)); }, [filters]);

  const rows = useMemo(() => {
    return alerts.filter((a) => (
      filter === 'ALL' || (filter === 'RESOLVED' ? a.status === 'RESOLVED' : a.severity === filter)
    ));
  }, [filter, alerts]);

  async function setStatus(alert, status) {
    try {
      const updated = await updateAlert(alert.alert_id, { status });
      setAlerts((prev) => prev.map((item) => item.alert_id === updated.alert_id ? updated : item));
    } catch (err) {
      setError(err.message || 'Unable to update alert.');
    }
  }

  const critical = alerts.filter((a) => a.severity === 'CRITICAL').length;
  const warnings = alerts.filter((a) => a.severity === 'WARNING').length;
  const resolved = alerts.filter((a) => a.status === 'RESOLVED').length;

  return (
    <div className="animate-fadeUp">
      <PageHeader eyebrow="LIVE" title="Safety Alerts" subtitle="Every violation and device event, routed to the right officer." />
      {error && <div className="panel border-danger/40 text-danger text-xs px-4 py-3 mb-4">{error}</div>}
      <FilterBar filters={filters} setFilters={setFilters} gates={gates} />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard label="Critical" value={critical} tone="danger" />
        <StatCard label="Warnings" value={warnings} tone="warning" />
        <StatCard label="Resolved" value={resolved} tone="safety" />
        <StatCard label="Delivery Success" value="98.7%" tone="info" />
      </div>

      <div className="flex flex-wrap gap-2 mb-5">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`label-op !text-[0.62rem] px-3 py-2 rounded-md border transition-colors ${filter === f ? 'border-safety text-safety bg-safetySubtle' : 'border-border text-textSecondary hover:text-text'
              }`}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {rows.map((a) => (
          <div key={a.id} className={`panel p-4 flex flex-col sm:flex-row sm:items-center gap-4 animate-slideIn ${a.severity === 'CRITICAL' && a.status === 'OPEN' ? 'border-danger/40' : ''}`}>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                <Badge tone={a.severity === 'CRITICAL' ? 'danger' : a.severity === 'WARNING' ? 'warning' : 'safety'}>
                  {a.severity}
                </Badge>
                <span className="text-sm font-semibold">{a.title}</span>
                <span className="mono text-[0.65rem] text-textMuted">{a.id}</span>
              </div>
              <div className="text-xs text-textSecondary">
                {a.worker !== '—' && !a.detail.startsWith(`${a.worker} `) && <span className="text-text font-medium">{a.worker}</span>}
                {a.worker !== '—' && !a.detail.startsWith(`${a.worker} `) && ' · '}
                {a.detail} · {a.gate} · <span className="mono">{a.time}</span>
              </div>
              <div className="text-[0.68rem] text-textMuted mt-1">Assigned: {a.officer} · Status: {a.status}</div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={() => setStatus(a, 'RESOLVED')}
                className="px-3 py-1.5 rounded-md border border-border text-[0.68rem] font-semibold text-textSecondary hover:text-safety hover:border-safety/50 flex items-center gap-1.5 focus-ring"
              >
                <CheckCircle2 size={12} /> RESOLVE
              </button>
              {a.workerId && (
                <button onClick={() => navigate(`/workers/${a.workerId}`)} className="px-3 py-1.5 rounded-md border border-border text-[0.68rem] font-semibold text-textSecondary hover:text-text focus-ring">
                  VIEW WORKER
                </button>
              )}
              <button
                onClick={() => setStatus(a, 'CLOSED')}
                className="px-3 py-1.5 rounded-md border border-danger/40 text-[0.68rem] font-semibold text-danger hover:bg-danger/10 flex items-center gap-1.5 focus-ring"
              >
                <ArrowUpCircle size={12} /> CLOSE
              </button>
            </div>
          </div>
        ))}
        {rows.length === 0 && (
          <div className="panel p-8 text-center text-textMuted flex flex-col items-center gap-2">
            <AlertTriangle size={20} />
            No alerts in this category.
          </div>
        )}
      </div>
    </div>
  );
}
