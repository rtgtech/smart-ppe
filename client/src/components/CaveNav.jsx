import { useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutGrid, Radio, Users, HardHat, ClipboardCheck,
  AlertTriangle, FileText, BrainCircuit, Cpu, ScrollText,
} from 'lucide-react';

const NAV_ITEMS = [
  { key: 'OVERVIEW', path: '/dashboard', icon: LayoutGrid },
  { key: 'LIVE', path: '/live', icon: Radio },
  { key: 'WORKERS', path: '/workers', icon: Users },
  { key: 'PPE', path: '/ppe', icon: HardHat },
  { key: 'ATTENDANCE', path: '/attendance', icon: ClipboardCheck },
  { key: 'ALERTS', path: '/alerts', icon: AlertTriangle },
  { key: 'REPORTS', path: '/reports', icon: FileText },
  { key: 'INSIGHTS', path: '/insights', icon: BrainCircuit },
  { key: 'DEVICES', path: '/devices', icon: Cpu },
  { key: 'AUDIT', path: '/audit', icon: ScrollText },
];

const VIEW_W = 1440;
const VIEW_H = 210;
const ARCH_DEPTH = 132; // how deep the arch dips at the ends
const ARCH_TOP = 34; // y at the very center (apex)

/** y position of the outer contour at a given x, forming a shallow arch */
function outerY(x) {
  const t = (x - VIEW_W / 2) / (VIEW_W / 2); // -1..1
  return ARCH_TOP + ARCH_DEPTH * (t * t);
}

function buildArchPath(offset = 0) {
  const pts = [];
  const steps = 24;
  for (let i = 0; i <= steps; i++) {
    const x = (VIEW_W / steps) * i;
    const y = outerY(x) + offset;
    pts.push([x, y]);
  }
  let d = `M ${pts[0][0]},${pts[0][1]}`;
  for (let i = 1; i < pts.length; i++) {
    const [x, y] = pts[i];
    const [px, py] = pts[i - 1];
    const mx = (px + x) / 2;
    d += ` Q ${px},${py} ${mx},${(py + y) / 2}`;
  }
  d += ` T ${pts[pts.length - 1][0]},${pts[pts.length - 1][1]}`;
  return d;
}

export default function CaveNav({ compact = false }) {
  const navigate = useNavigate();
  const location = useLocation();

  const outerPath = useMemo(() => buildArchPath(0), []);
  const innerPath = useMemo(() => buildArchPath(46), []);

  const positions = useMemo(() => {
    const n = NAV_ITEMS.length;
    return NAV_ITEMS.map((item, i) => {
      const x = 60 + ((VIEW_W - 120) / (n - 1)) * i;
      const y = outerY(x) - 26;
      return { ...item, x, y };
    });
  }, []);

  if (compact) return null;

  return (
    <div className="relative w-full select-none hidden lg:block" style={{ height: VIEW_H }}>
      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        preserveAspectRatio="none"
        className="absolute inset-0 w-full h-full"
      >
        <defs>
          <linearGradient id="archGlow" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="rgb(var(--color-safety))" stopOpacity="0.08" />
            <stop offset="50%" stopColor="rgb(var(--color-safety))" stopOpacity="0.35" />
            <stop offset="100%" stopColor="rgb(var(--color-safety))" stopOpacity="0.08" />
          </linearGradient>
        </defs>
        <path d={outerPath} fill="none" stroke="rgb(var(--color-border))" strokeWidth="1.5" />
        <path d={outerPath} fill="none" stroke="url(#archGlow)" strokeWidth="1" opacity="0.9" />
        <path d={innerPath} fill="none" stroke="rgb(var(--color-grid))" strokeWidth="1" strokeDasharray="2 6" />
      </svg>

      {positions.map(({ key, path, icon: Icon, x, y }) => {
        const active = location.pathname === path || (path === '/dashboard' && location.pathname === '/dashboard');
        return (
          <button
            key={key}
            onClick={() => navigate(path)}
            style={{ left: `${(x / VIEW_W) * 100}%`, top: y }}
            className={[
              'absolute -translate-x-1/2 flex items-center gap-1.5 px-2.5 py-1.5 rounded-md',
              'border transition-all duration-200 group focus-ring',
              active
                ? 'bg-surface border-safety shadow-glowSm text-text'
                : 'bg-input border-border text-textSecondary hover:-translate-y-0.5 hover:border-textMuted hover:text-text',
            ].join(' ')}
          >
            <span
              className={[
                'status-dot',
                active ? 'bg-safety shadow-glowSm animate-pulseGlow' : 'bg-textMuted group-hover:bg-safety',
              ].join(' ')}
            />
            <Icon size={13} strokeWidth={2} className={active ? 'text-safety' : ''} />
            <span className="label-op !text-[0.62rem]">{key}</span>
          </button>
        );
      })}
    </div>
  );
}

export { NAV_ITEMS };
