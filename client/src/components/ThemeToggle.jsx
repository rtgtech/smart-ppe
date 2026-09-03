import { Moon, Sun } from 'lucide-react';
import { useTheme } from '../theme-context';

export default function ThemeToggle({ showLabel = false, className = '' }) {
  const { theme, toggleTheme } = useTheme();
  const isLight = theme === 'light';
  const label = isLight ? 'Use dark theme' : 'Use light theme';
  const Icon = isLight ? Moon : Sun;

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className={`inline-flex items-center justify-center gap-2 rounded-md border border-border bg-surface/80 p-2 text-textSecondary transition-colors hover:border-safety hover:text-safety focus-ring ${className}`}
      aria-label={label}
      title={label}
    >
      <Icon size={16} aria-hidden="true" />
      {showLabel && <span className="label-op !text-[0.62rem]">{isLight ? 'DARK' : 'LIGHT'}</span>}
    </button>
  );
}
