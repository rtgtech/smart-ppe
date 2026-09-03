import { useEffect, useState } from 'react';
import { FileText, Download, Eye, RefreshCw } from 'lucide-react';
import { PageHeader, SectionHeader, Badge } from '../components/ui';
import { listReports } from '../services/reports';

export default function Reports() {
  const [reports, setReports] = useState([]);
  useEffect(() => { listReports().then(setReports).catch(() => setReports([])); }, []);
  return (
    <div className="animate-fadeUp">
      <PageHeader eyebrow="COMPLIANCE" title="Safety Reports" subtitle="Generate, view and export audit-ready reports." />

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 mb-8">
        {reports.map((r) => (
          <div key={r.id} className="panel p-5 flex flex-col rock-texture">
            <div className="flex items-start justify-between mb-3">
              <FileText size={18} className="text-safety" />
              <span className="mono text-[0.65rem] text-textMuted">{r.records.toLocaleString()} records</span>
            </div>
            <div className="font-bold text-sm mb-1.5">{r.name}</div>
            <p className="text-xs text-textSecondary leading-relaxed mb-4 flex-1">{r.description}</p>
            <div className="text-[0.65rem] text-textMuted mb-3">Last generated: {r.lastGenerated}</div>
            <div className="flex gap-2">
              <button className="flex-1 py-2 rounded-md border border-border text-[0.68rem] font-bold uppercase tracking-wide hover:border-safety hover:text-safety transition flex items-center justify-center gap-1.5 focus-ring">
                <Eye size={12} /> View
              </button>
              <button className="flex-1 py-2 rounded-md border border-border text-[0.68rem] font-bold uppercase tracking-wide hover:border-safety hover:text-safety transition flex items-center justify-center gap-1.5 focus-ring">
                <RefreshCw size={12} /> Generate
              </button>
              <button className="flex-1 py-2 rounded-md bg-safety text-onSafety text-[0.68rem] font-bold uppercase tracking-wide hover:brightness-110 transition flex items-center justify-center gap-1.5 focus-ring">
                <Download size={12} /> Download
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="panel overflow-hidden">
        <div className="p-5 pb-0"><SectionHeader title="Recent Reports" /></div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                {['Report', 'Date', 'Records', 'Status'].map((h) => (
                  <th key={h} className="label-op text-left px-4 py-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {reports.map((r, i) => (
                <tr key={i} className="border-b border-border/50 last:border-0 hover:bg-elevated/50">
                  <td className="px-4 py-3 font-medium">{r.name}</td>
                  <td className="px-4 py-3 mono text-textSecondary">{r.date}</td>
                  <td className="px-4 py-3 mono">{r.records.toLocaleString()}</td>
                  <td className="px-4 py-3"><Badge tone={r.status === 'READY' ? 'safety' : 'default'}>{r.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
