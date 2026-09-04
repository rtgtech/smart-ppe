import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { LineChart, Line, ResponsiveContainer, YAxis } from 'recharts';
import { AlertOctagon, ArrowLeft, Download, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { Badge, StatCard } from '../components/ui';
import { getWorker } from '../services/workers';
import { listCompliance } from '../services/compliance';
import { downloadEmployeeReportPdf } from '../services/reports';

export default function WorkerProfile() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [worker, setWorker] = useState(null);
  const [error, setError] = useState('');
  const [history, setHistory] = useState([]);
  const [downloadingPeriod, setDownloadingPeriod] = useState(null); // 'WEEKLY' | 'MONTHLY' | null
  const [pdfStatus, setPdfStatus] = useState({ type: '', msg: '' });

  const handleDownloadPdf = async (periodType) => {
    if (!worker) return;
    setDownloadingPeriod(periodType);
    setPdfStatus({ type: '', msg: '' });
    try {
      const filename = await downloadEmployeeReportPdf({
        workerId: worker.worker_id || worker.id,
        period: periodType,
      });
      setPdfStatus({ type: 'success', msg: `Downloaded ${filename}` });
    } catch (err) {
      setPdfStatus({ type: 'error', msg: err.message || 'Download failed' });
    } finally {
      setDownloadingPeriod(null);
    }
  };

  useEffect(() => {
    let mounted = true;
    async function loadWorker() {
      try {
        const row = await getWorker(id);
        if (mounted) {
          setWorker(row);
          listCompliance(row.worker_id).then((logs) => mounted && setHistory(logs)).catch(() => { });
        }
      } catch (err) {
        if (mounted) setError(err.message || 'Unable to load worker.');
      }
    }
    loadWorker();
    return () => { mounted = false; };
  }, [id]);

  if (error) {
    return (
      <div className="animate-fadeUp">
        <button onClick={() => navigate('/workers')} className="flex items-center gap-1.5 text-xs text-textSecondary hover:text-text mb-4 focus-ring">
          <ArrowLeft size={13} /> Back to Workers
        </button>
        <div className="panel border-danger/40 text-danger text-xs px-4 py-3">{error}</div>
      </div>
    );
  }

  if (!worker) {
    return (
      <div className="animate-fadeUp">
        <button onClick={() => navigate('/workers')} className="flex items-center gap-1.5 text-xs text-textSecondary hover:text-text mb-4 focus-ring">
          <ArrowLeft size={13} /> Back to Workers
        </button>
        <div className="panel text-textMuted text-xs px-4 py-8 text-center">Loading worker...</div>
      </div>
    );
  }

  return (
    <div className="animate-fadeUp">
      <button onClick={() => navigate('/workers')} className="flex items-center gap-1.5 text-xs text-textSecondary hover:text-text mb-4 focus-ring">
        <ArrowLeft size={13} /> Back to Workers
      </button>

      <div className="flex flex-wrap items-start justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight">{worker.name}</h1>
          <div className="flex flex-wrap items-center gap-2 mt-2">
            <span className="mono text-xs text-textSecondary">{worker.id}</span>
            <span className="text-textMuted">·</span>
            <span className="label-op !text-[0.62rem]">{worker.department}</span>
            <Badge tone={worker.status === 'ACTIVE' ? 'safety' : 'default'}>{worker.status}</Badge>
          </div>
        </div>
        <div className="text-right">
          <div className="text-4xl font-extrabold mono text-safety">{worker.ppeScore}</div>
          <div className="label-op">Safety Score</div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard label="30-Day Compliance" value={`${worker.ppeScore}%`} />
        <StatCard label="Violations" value={worker.violations} tone="warning" />
        <StatCard label="Entry Denials" value={worker.denials} tone="danger" />
        <StatCard label="Safety Streak" value={`${worker.streak} days`} tone="safety" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <div className="xl:col-span-2 panel p-5">
          <div className="label-op mb-3">30-Day PPE Compliance</div>
          <div style={{ height: 160 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history.map((item) => ({ day: item.time, compliance: item.compliance_score }))}>
                <YAxis domain={[70, 100]} hide />
                <Line type="monotone" dataKey="compliance" stroke="rgb(var(--color-safety))" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="label-op mt-6 mb-3">History</div>
          <div className="space-y-2.5">
            {history.map((h, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-border/60 last:border-0">
                <div className="flex items-center gap-3">
                  <span className="mono text-xs text-textMuted w-14">{new Date(h.time).toLocaleDateString(undefined, { day: '2-digit', month: 'short' }).toUpperCase()}</span>
                  <span className="text-xs">{h.decision}</span>
                </div>
                <Badge tone={h.decision === 'DENIED' ? 'danger' : h.decision === 'WARNING' ? 'warning' : 'safety'}>{h.decision}</Badge>
              </div>
            ))}
            {history.length === 0 && <div className="text-xs text-textMuted">No compliance history recorded.</div>}
          </div>
        </div>

        <div className="panel p-5 border-warning/30">
          <div className="flex items-center gap-2 mb-3 text-warning">
            <AlertOctagon size={16} />
            <span className="label-op !text-warning">Repeated PPE Violations</span>
          </div>
          <p className="text-xs text-textSecondary leading-relaxed mb-4">
            The system has identified repeated non-compliance for this worker across
            the last 30 days, concentrated around safety boots and gas detector checks.
          </p>
          <div className="label-op mb-1.5">Recommended Action</div>
          <p className="text-xs text-text mb-5">Supervisor intervention.</p>
          <button onClick={() => navigate('/alerts')} className="w-full py-2.5 rounded-md border border-border text-xs font-bold uppercase tracking-wide hover:border-safety hover:text-safety transition focus-ring mb-3">
            View Audit History
          </button>

          <div className="pt-3 border-t border-border/50">
            <div className="label-op !text-[0.62rem] mb-2 text-textMuted">Download Safety Dossier</div>
            <div className="flex gap-2">
              <button
                onClick={() => handleDownloadPdf('WEEKLY')}
                disabled={downloadingPeriod !== null}
                className="flex-1 py-2 rounded-md border border-border text-[0.68rem] font-bold uppercase tracking-wide hover:border-safety hover:text-safety transition flex items-center justify-center gap-1.5 focus-ring disabled:opacity-50"
              >
                {downloadingPeriod === 'WEEKLY' ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
                Weekly PDF
              </button>
              <button
                onClick={() => handleDownloadPdf('MONTHLY')}
                disabled={downloadingPeriod !== null}
                className="flex-1 py-2 rounded-md bg-safety text-onSafety text-[0.68rem] font-bold uppercase tracking-wide hover:brightness-110 transition flex items-center justify-center gap-1.5 focus-ring disabled:opacity-50"
              >
                {downloadingPeriod === 'MONTHLY' ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
                Monthly PDF
              </button>
            </div>
            {pdfStatus.msg && (
              <div className={`mt-2.5 text-[0.7rem] px-2.5 py-1.5 rounded flex items-center gap-1.5 animate-fadeIn ${
                pdfStatus.type === 'success' ? 'bg-safetySubtle text-safety border border-safety/30' : 'bg-dangerSubtle text-danger border border-danger/30'
              }`}>
                {pdfStatus.type === 'success' ? <CheckCircle2 size={12} /> : <AlertCircle size={12} />}
                {pdfStatus.msg}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
