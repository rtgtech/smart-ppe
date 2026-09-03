import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Camera, Nfc, Router, WifiOff } from 'lucide-react';
import { PageHeader, StatCard, Badge, StatusDot } from '../components/ui';
import { listDevices } from '../services/devices';

const ICONS = { 'AI CAMERA': Camera, 'RFID READER': Nfc, 'GATE CONTROLLER': Router };

export default function Devices() {
  const navigate = useNavigate();
  const [devices, setDevices] = useState([]);
  useEffect(() => { listDevices().then(setDevices).catch(() => setDevices([])); }, []);
  const online = devices.filter((d) => d.status === 'ONLINE').length;
  const offline = devices.filter((d) => d.status === 'OFFLINE').length;

  return (
    <div className="animate-fadeUp">
      <PageHeader
        eyebrow="INFRASTRUCTURE"
        title="Safety Devices"
        subtitle="Cameras, RFID readers and edge controllers across every gate."
        right={
          <button onClick={() => navigate('/devices/sync')} className="label-op !text-xs border border-border px-3.5 py-2 rounded-md hover:border-safety hover:text-safety focus-ring flex items-center gap-1.5">
            <WifiOff size={13} /> OFFLINE SYNC
          </button>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <StatCard label="Online" value={online} tone="safety" />
        <StatCard label="Offline" value={offline} tone="danger" />
        <StatCard label="Sync Queue" value="18" tone="warning" />
        <StatCard label="AI Confidence" value="96.4%" tone="info" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
        {devices.map((d) => {
          const Icon = ICONS[d.type];
          return (
            <div key={d.id} className="panel p-4 flex items-center gap-4 rock-texture">
              <div className={`w-10 h-10 rounded-md flex items-center justify-center shrink-0 ${d.status === 'ONLINE' ? 'bg-safetySubtle text-safety' : 'bg-dangerSubtle text-danger'}`}>
                <Icon size={16} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <span className="mono font-bold text-sm">{d.id}</span>
                  <Badge tone={d.status === 'ONLINE' ? 'safety' : 'danger'}><StatusDot status={d.status} /> {d.status}</Badge>
                </div>
                <div className="text-[0.68rem] text-textSecondary mt-1">{d.type} · {d.gate}</div>
                <div className="text-[0.65rem] text-textMuted mt-0.5">Last heartbeat: {d.heartbeat}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
