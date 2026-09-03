import { useState } from 'react';
import { PageHeader, Badge } from '../components/ui';
import { AUDIT_LOG, GATES } from '../data/mockData';

export default function Audit() {
  const [decisionFilter, setDecisionFilter] = useState('ALL');
  const rows = AUDIT_LOG.filter((r) => decisionFilter === 'ALL' || r.decision.toUpperCase() === decisionFilter);

  return (
    <div className="animate-fadeUp">
      <PageHeader eyebrow="TRACEABILITY" title="Audit Log" subtitle="Every safety decision is traceable." />

      <div className="panel p-4 mb-5 flex flex-wrap gap-3 items-center">
        <FilterSelect label="Date" options={['Today', 'Yesterday', 'Last 7 days']} />
        <FilterSelect label="Gate" options={['All Gates', ...GATES.map((g) => g.name)]} />
        <FilterSelect label="Source" options={['All Sources', 'AI CAMERA', 'AI + RFID', 'RFID']} />
        <div>
          <div className="label-op mb-1">Decision</div>
          <select
            className="bg-input border border-border rounded-md px-3 py-1.5 text-xs focus-ring"
            value={decisionFilter}
            onChange={(e) => setDecisionFilter(e.target.value)}
          >
            {['ALL', 'ALLOWED', 'DENIED', 'WARNING'].map((o) => <option key={o}>{o}</option>)}
          </select>
        </div>
      </div>

      <div className="panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                {['Time', 'Event ID', 'Worker', 'Gate', 'Decision', 'Source'].map((h) => (
                  <th key={h} className="label-op text-left px-4 py-3 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.eventId} className="border-b border-border/50 last:border-0 hover:bg-elevated/50">
                  <td className="px-4 py-3 mono text-textSecondary">{r.time}</td>
                  <td className="px-4 py-3 mono">{r.eventId}</td>
                  <td className="px-4 py-3 font-medium whitespace-nowrap">{r.worker}</td>
                  <td className="px-4 py-3 mono">{r.gate}</td>
                  <td className="px-4 py-3">
                    <Badge tone={r.decision === 'DENIED' ? 'danger' : r.decision === 'WARNING' ? 'warning' : 'safety'}>{r.decision}</Badge>
                  </td>
                  <td className="px-4 py-3 text-textSecondary whitespace-nowrap">{r.source}</td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-textMuted">No events match this filter.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function FilterSelect({ label, options }) {
  return (
    <div>
      <div className="label-op mb-1">{label}</div>
      <select className="bg-input border border-border rounded-md px-3 py-1.5 text-xs focus-ring">
        {options.map((o) => <option key={o}>{o}</option>)}
      </select>
    </div>
  );
}
