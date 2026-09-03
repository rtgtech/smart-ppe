/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: 'rgb(var(--color-bg) / <alpha-value>)',
        bgDeep: 'rgb(var(--color-bg-deep) / <alpha-value>)',
        surface: 'rgb(var(--color-surface) / <alpha-value>)',
        elevated: 'rgb(var(--color-elevated) / <alpha-value>)',
        input: 'rgb(var(--color-input) / <alpha-value>)',
        border: 'rgb(var(--color-border) / <alpha-value>)',
        text: 'rgb(var(--color-text) / <alpha-value>)',
        textSecondary: 'rgb(var(--color-text-secondary) / <alpha-value>)',
        textMuted: 'rgb(var(--color-text-muted) / <alpha-value>)',
        safety: 'rgb(var(--color-safety) / <alpha-value>)',
        safetyDark: 'rgb(var(--color-safety-dark) / <alpha-value>)',
        safetySubtle: 'rgb(var(--color-safety-subtle) / <alpha-value>)',
        onSafety: 'rgb(var(--color-on-safety) / <alpha-value>)',
        danger: 'rgb(var(--color-danger) / <alpha-value>)',
        dangerSubtle: 'rgb(var(--color-danger-subtle) / <alpha-value>)',
        dangerBorder: 'rgb(var(--color-danger-border) / <alpha-value>)',
        warning: 'rgb(var(--color-warning) / <alpha-value>)',
        warningSubtle: 'rgb(var(--color-warning-subtle) / <alpha-value>)',
        warningBorder: 'rgb(var(--color-warning-border) / <alpha-value>)',
        info: 'rgb(var(--color-info) / <alpha-value>)',
        infoSubtle: 'rgb(var(--color-info-subtle) / <alpha-value>)',
        infoBorder: 'rgb(var(--color-info-border) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['Onest', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 24px rgb(var(--color-safety) / 0.18)',
        glowSm: '0 0 12px rgb(var(--color-safety) / 0.25)',
      },
      keyframes: {
        pulseGlow: {
          '0%,100%': { opacity: 1 },
          '50%': { opacity: 0.55 },
        },
        scan: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        },
        slideIn: {
          '0%': { transform: 'translateX(12px)', opacity: 0 },
          '100%': { transform: 'translateX(0)', opacity: 1 },
        },
        fadeUp: {
          '0%': { transform: 'translateY(6px)', opacity: 0 },
          '100%': { transform: 'translateY(0)', opacity: 1 },
        },
      },
      animation: {
        pulseGlow: 'pulseGlow 2.2s ease-in-out infinite',
        scan: 'scan 2.4s linear infinite',
        slideIn: 'slideIn 0.35s ease-out',
        fadeUp: 'fadeUp 0.4s ease-out',
      },
    },
  },
  plugins: [],
};
