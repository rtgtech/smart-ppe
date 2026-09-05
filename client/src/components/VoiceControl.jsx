import { Mic, MicOff, Radio, X } from 'lucide-react';

const STATUS_TEXT = {
  idle: 'Voice agent',
  connecting: 'Connecting…',
  listening: 'Listening…',
  processing: 'Thinking…',
  speaking: 'Speaking…',
  error: 'Connection issue',
};

export default function VoiceControl({
  status,
  mode,
  error,
  transcript,
  onToggle,
  onDismissError,
}) {
  const active = status !== 'idle' && status !== 'error';

  return (
    <div className="fixed z-[60] right-4 bottom-20 lg:right-7 lg:bottom-6 flex items-center gap-3">
      {(transcript.length > 0 || error) && (
        <div
          className="absolute right-0 bottom-16 w-[min(24rem,calc(100vw-2rem))] rounded-lg border border-border bg-surface/95 p-3 shadow-2xl backdrop-blur"
          aria-live="polite"
        >
          <div className="mb-2 flex items-center justify-between text-[0.65rem] font-bold uppercase tracking-wider text-safety">
            <span className="flex items-center gap-1.5"><Radio size={14} /> Live voice</span>
            {error && (
              <button onClick={onDismissError} aria-label="Dismiss error" className="text-textSecondary hover:text-text">
                <X size={14} />
              </button>
            )}
          </div>
          {error ? (
            <p className="m-0 text-xs leading-relaxed text-danger">{error}</p>
          ) : transcript.map((line, index) => (
            <p key={`${line.speaker}-${index}`} className="my-1 grid grid-cols-[5rem_minmax(0,1fr)] gap-2 text-xs leading-relaxed text-textSecondary">
              <strong className="whitespace-nowrap text-text">{line.speaker === 'user' ? 'You' : 'SURAKSHA'}</strong>
              <span className="min-w-0 break-words">{line.text}</span>
            </p>
          ))}
        </div>
      )}

      <div className="hidden sm:block rounded-lg border border-border bg-bgDeep/90 px-3 py-2 text-right shadow-xl backdrop-blur">
        <strong className="block text-xs text-text">{STATUS_TEXT[status]}</strong>
        <span className="mt-0.5 block text-[0.65rem] text-textMuted">
          {mode === 'push-to-talk'
            ? 'Release Left Ctrl to stop'
            : active ? 'Click to end session' : 'Click or hold Left Ctrl'}
        </span>
      </div>

      <button
        className={`relative grid h-14 w-14 place-items-center rounded-full border shadow-xl transition-colors focus-ring ${
          active
            ? 'border-safety bg-safety text-onSafety'
            : status === 'error'
              ? 'border-danger bg-dangerSubtle text-danger'
              : 'border-border bg-elevated text-safety hover:border-safety'
        }`}
        onClick={onToggle}
        aria-label={active ? 'Stop voice agent' : 'Start voice agent'}
        aria-pressed={active}
      >
        {active && <span className="absolute inset-0 rounded-full border border-safety animate-ping" />}
        {status === 'error' ? <MicOff size={22} /> : <Mic size={22} />}
      </button>
    </div>
  );
}
