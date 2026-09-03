import { Award, ShieldCheck } from 'lucide-react';
import { PageHeader } from '../components/ui';
import { CHAMPIONS } from '../data/mockData';

export default function Champions() {
  const [top, ...rest] = CHAMPIONS;

  return (
    <div className="animate-fadeUp">
      <PageHeader eyebrow="RECOGNITION" title="Safety Champions" subtitle="Recognizing consistent safe behaviour." />

      <div className="panel-elevated p-8 mb-6 rock-texture flex flex-col sm:flex-row items-center gap-6">
        <div className="w-20 h-20 rounded-full bg-safetySubtle border border-safetyDark flex items-center justify-center shrink-0">
          <Award size={30} className="text-safety" />
        </div>
        <div className="flex-1 text-center sm:text-left">
          <div className="label-op !text-safety mb-1">Top Performer</div>
          <div className="text-2xl font-extrabold tracking-tight">{top.worker}</div>
          <div className="flex flex-wrap justify-center sm:justify-start gap-x-6 gap-y-1 mt-3">
            <Metric value={`${top.compliance}%`} label="30-Day Compliance" />
            <Metric value={`${top.streak} Days`} label="Safe Streak" />
          </div>
        </div>
        <div className="panel px-5 py-4 text-center border-safety/40 shrink-0">
          <ShieldCheck size={18} className="text-safety mx-auto mb-1.5" />
          <div className="label-op !text-safety">Safety Champion</div>
          <div className="text-[0.68rem] text-textSecondary mt-1">30 consecutive days<br />full PPE compliance</div>
        </div>
      </div>

      <div className="panel overflow-hidden">
        <div className="p-5 pb-0 label-op">Leaderboard</div>
        <div className="divide-y divide-border/60">
          {rest.map((c) => (
            <div key={c.workerId} className="flex items-center gap-4 px-5 py-4">
              <div className="w-8 h-8 rounded-full bg-elevated border border-border flex items-center justify-center font-bold text-xs text-textSecondary shrink-0">
                {c.rank}
              </div>
              <div className="flex-1">
                <div className="text-sm font-semibold">{c.worker}</div>
                <div className="mono text-[0.65rem] text-textMuted">{c.workerId}</div>
              </div>
              <div className="text-right">
                <div className="mono font-bold text-safety">{c.compliance}%</div>
                <div className="text-[0.65rem] text-textMuted">{c.streak}-day streak</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Metric({ value, label }) {
  return (
    <div>
      <div className="text-lg font-bold mono text-safety">{value}</div>
      <div className="label-op">{label}</div>
    </div>
  );
}
