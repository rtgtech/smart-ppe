import { useEffect, useState } from 'react';
import { WifiOff, ArrowDown, User, ScanFace, Database, ListOrdered, Wifi, CheckCircle2 } from 'lucide-react';
import { PageHeader, Badge } from '../components/ui';
import { getSyncQueue } from '../services/devices';

const FLOW = [
  { label: 'WORKER', icon: User },
  { label: 'AI + RFID', icon: ScanFace },
  { label: 'LOCAL VERIFICATION', icon: CheckCircle2 },
  { label: 'LOCAL DATABASE', icon: Database },
  { label: 'SYNC QUEUE', icon: ListOrdered },
  { label: 'NETWORK RESTORED', icon: Wifi },
  { label: 'SYNC COMPLETE', icon: CheckCircle2 },
];

export default function DevicesSync() {
  const [queue, setQueue] = useState([]);
  useEffect(() => { getSyncQueue().then(setQueue).catch(() => setQueue([])); }, []);
  return (
    <div className="animate-fadeUp">
      <PageHeader eyebrow="RESILIENCE" title="Offline Operations" />

      <div className="panel-elevated p-8 mb-6 rock-texture text-center">
        <WifiOff size={26} className="mx-auto text-warning mb-4" />
        <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight leading-tight">
          NO NETWORK<br />DOES NOT MEAN<br />NO SAFETY.
        </h2>
        <p className="text-sm text-textSecondary mt-4 max-w-lg mx-auto leading-relaxed">
          Gate verification continues locally when network connectivity is unavailable.
          Every decision is stored on-device and synced automatically once the link is restored.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <StatusCard label="Network" value="OFFLINE" tone="warning" />
        <StatusCard label="Local Verification" value="ACTIVE" tone="safety" />
        <StatusCard label="Events Waiting to Sync" value="18" tone="default" />
        <StatusCard label="Last Sync" value="10:31:52" tone="default" mono />
      </div>

      <div className="panel p-6 mb-8 overflow-x-auto">
        <div className="label-op mb-5">Verification Pipeline</div>
        <div className="flex items-center gap-2 min-w-max">
          {FLOW.map((f, i) => (
            <div key={f.label} className="flex items-center gap-2">
              <div className="flex flex-col items-center gap-2 w-28">
                <div className="w-10 h-10 rounded-md bg-elevated border border-border flex items-center justify-center">
                  <f.icon size={15} className="text-safety" />
                </div>
                <span className="label-op !text-[0.58rem] text-center leading-tight">{f.label}</span>
              </div>
              {i < FLOW.length - 1 && <ArrowDown size={14} className="text-textMuted rotate-[-90deg] shrink-0" />}
            </div>
          ))}
        </div>
      </div>

      <div className="panel overflow-hidden">
        <div className="p-5 pb-0 label-op">Sync Events</div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs mt-3">
            <thead>
              <tr className="border-b border-border">
                {['Event ID', 'Worker', 'Type', 'Status'].map((h) => <th key={h} className="label-op text-left px-4 py-3">{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {queue.map((e) => (
                <tr key={e.id} className="border-b border-border/50 last:border-0 hover:bg-elevated/50">
                  <td className="px-4 py-3 mono">{e.id}</td>
                  <td className="px-4 py-3 font-medium">{e.worker}</td>
                  <td className="px-4 py-3 text-textSecondary">{e.type}</td>
                  <td className="px-4 py-3"><Badge tone="warning">{e.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StatusCard({ label, value, tone, mono }) {
  const toneColor = { safety: 'text-safety', warning: 'text-warning', default: 'text-text' }[tone];
  return (
    <div className="panel p-4 rock-texture">
      <div className="label-op mb-2">{label}</div>
      <div className={`text-lg font-bold ${mono ? 'mono' : ''} ${toneColor}`}>{value}</div>
    </div>
  );
}
