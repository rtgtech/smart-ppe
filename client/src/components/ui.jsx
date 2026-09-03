export function StatCard({ label, value, sub, tone = 'default', icon: Icon }) {
  const toneColor = {
    default: 'text-text',
    safety: 'text-safety',
    danger: 'text-danger',
    warning: 'text-warning',
    info: 'text-info',
  }[tone];

  return (
    <div className="panel p-4 flex flex-col gap-2 rock-texture">
      <div className="flex items-center justify-between">
        <span className="label-op">{label}</span>
        {Icon && <Icon size={14} className="text-textMuted" />}
      </div>
      <div className={`text-2xl font-bold mono ${toneColor}`}>{value}</div>
      {sub && <div className="text-xs text-textSecondary">{sub}</div>}
    </div>
  );
}

export function Badge({ children, tone = 'default' }) {
  const map = {
    default: 'bg-elevated text-textSecondary border-border',
    safety: 'bg-safetySubtle text-safety border-safetyDark',
    danger: 'bg-dangerSubtle text-danger border-dangerBorder',
    warning: 'bg-warningSubtle text-warning border-warningBorder',
    info: 'bg-infoSubtle text-info border-infoBorder',
  }[tone];
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[0.68rem] font-semibold uppercase tracking-wide ${map}`}>
      {children}
    </span>
  );
}

export function SectionHeader({ title, subtitle, action }) {
  return (
    <div className="flex items-end justify-between mb-4 flex-wrap gap-3">
      <div>
        <h2 className="text-sm font-bold tracking-wide uppercase text-text">{title}</h2>
        {subtitle && <p className="text-xs text-textSecondary mt-1">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function PageHeader({ eyebrow, title, subtitle, right }) {
  return (
    <div className="flex items-start justify-between flex-wrap gap-4 mb-6">
      <div>
        {eyebrow && <div className="label-op text-safety mb-1">{eyebrow}</div>}
        <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight">{title}</h1>
        {subtitle && <p className="text-sm text-textSecondary mt-1.5 max-w-xl">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function StatusDot({ status }) {
  const color = status === 'ONLINE' || status === 'ACTIVE' || status === 'ALLOWED' || status === 'VERIFIED'
    ? 'bg-safety'
    : status === 'MAINTENANCE' || status === 'WARNING' || status === 'PENDING' || status === 'SYNCING'
      ? 'bg-warning'
      : 'bg-danger';
  return <span className={`status-dot ${color}`} />;
}

export function Button({ children, variant = 'primary', className = '', ...props }) {
  const base = 'inline-flex items-center justify-center gap-2 px-4 py-2 rounded-md text-xs font-bold uppercase tracking-wide transition-all focus-ring';
  const variants = {
    primary: 'bg-safety text-onSafety hover:brightness-110 shadow-glowSm',
    outline: 'border border-border text-text hover:border-safety hover:text-safety',
    ghost: 'text-textSecondary hover:text-text',
    danger: 'bg-danger/10 border border-danger/40 text-danger hover:bg-danger/20',
  };
  return (
    <button className={`${base} ${variants[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}
