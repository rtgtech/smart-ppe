import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import AnnotatedVisionFeed from './AnnotatedVisionFeed';
import GateFlow from './GateFlow';
import { createEntryAttempt, getEntryAttempt, resetEntrySession } from '../services/gateCheck';
import { EntryContext } from './entry-context';

const EVENT_KEY = 'suraksha_entry_event_id';
const ACTUATED_KEY = 'suraksha_entry_actuated_event_id';

export default function EntryLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [entry, setEntry] = useState(null);
  const [connection, setConnection] = useState('offline');
  const [error, setError] = useState('');
  const audioRef = useRef(null);

  const step = location.pathname.endsWith('/scan-ppe') ? 2 : location.pathname.endsWith('/compliance') ? 3 : 1;

  const routeFor = useCallback((next) => {
    if (!next) return;
    if (next.lifecycle === 'FINALIZED') navigate('/entry/compliance', { replace: true });
    else if (next.phase === 'EVIDENCE') navigate('/entry/scan-ppe', { replace: true });
    else navigate('/entry/biometric', { replace: true });
  }, [navigate]);

  const acceptEntry = useCallback((next) => {
    setEntry(next);
    setError('');
    routeFor(next);
    if (next?.lifecycle === 'FINALIZED' && next.verdict === 'DENIED' && sessionStorage.getItem(ACTUATED_KEY) !== next.event_id) {
      sessionStorage.setItem(ACTUATED_KEY, next.event_id);
      const audio = audioRef.current;
      if (audio) {
        const oscillator = audio.createOscillator();
        const gain = audio.createGain();
        oscillator.frequency.value = 720;
        gain.gain.setValueAtTime(.18, audio.currentTime);
        gain.gain.exponentialRampToValueAtTime(.001, audio.currentTime + .7);
        oscillator.connect(gain).connect(audio.destination);
        oscillator.start();
        oscillator.stop(audio.currentTime + .7);
      }
    }
  }, [routeFor]);

  useEffect(() => {
    const eventId = sessionStorage.getItem(EVENT_KEY);
    if (eventId) getEntryAttempt(eventId).then(acceptEntry).catch(() => sessionStorage.removeItem(EVENT_KEY));
  }, [acceptEntry]);

  const start = useCallback(async () => {
    try {
      if (!audioRef.current) audioRef.current = new AudioContext();
      await audioRef.current.resume();
      const eventId = crypto.randomUUID();
      sessionStorage.setItem(EVENT_KEY, eventId);
      const next = await createEntryAttempt(eventId);
      acceptEntry(next);
    } catch (caught) {
      setError(caught.message || 'The edge gate service is unavailable. The barrier remains locked.');
    }
  }, [acceptEntry]);

  const nextWorker = useCallback(() => {
    resetEntrySession();
    sessionStorage.removeItem(EVENT_KEY);
    setEntry(null);
    setError('');
    navigate('/entry/biometric', { replace: true });
  }, [navigate]);

  const handleMeta = useCallback((meta) => {
    if (meta.entry) acceptEntry(meta.entry);
  }, [acceptEntry]);

  const context = useMemo(() => ({ entry, connection, error, start, nextWorker }), [entry, connection, error, start, nextWorker]);

  return (
    <EntryContext.Provider value={context}>
      <GateFlow step={step}>
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(360px,0.85fr)]">
          <div className="panel relative min-h-[560px] overflow-hidden">
            <AnnotatedVisionFeed active={entry?.lifecycle === 'ACTIVE'} eventId={entry?.event_id} onConnectionChange={setConnection} onFrameMeta={handleMeta} />
            {!entry && <div className="absolute inset-0 grid place-items-center bg-black/45"><button onClick={start} className="rounded-md bg-safety px-7 py-3 text-xs font-bold uppercase tracking-wide text-onSafety shadow-glow">Start entry scan</button></div>}
          </div>
          <Outlet />
        </div>
      </GateFlow>
    </EntryContext.Provider>
  );
}
