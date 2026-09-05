import { useCallback, useEffect, useMemo, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import AnnotatedVisionFeed from './AnnotatedVisionFeed';
import GateFlow from './GateFlow';
import { EntryContext } from './entry-context';
import { createEntryAttempt, discardEntryAttempt, getEntryAttempt } from '../services/gateCheck';
import { announceEntryViolation, prepareViolationAudio } from '../services/violationAnnouncements';

const KEY = 'suraksha_entry_session';

export default function EntryLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [entry, setEntry] = useState(null);
  const [connection, setConnection] = useState('offline');
  const [error, setError] = useState('');

  const accept = useCallback((value) => {
    setEntry(value);
    setError('');
    if (value.lifecycle === 'FINALIZED' && value.verdict !== 'ALLOWED') {
      const announcementKey = `suraksha_violation_announced:${value.event_id}`;
      if (!sessionStorage.getItem(announcementKey)) {
        sessionStorage.setItem(announcementKey, '1');
        void announceEntryViolation(value);
      }
    }
    navigate(value.phase === 'IDENTITY' ? '/entry/biometric' : '/entry/compliance', { replace: true });
  }, [navigate]);

  useEffect(() => {
    const id = sessionStorage.getItem(KEY);
    if (id) getEntryAttempt(id).then(accept).catch(() => sessionStorage.removeItem(KEY));
  }, [accept]);

  const start = useCallback(async () => {
    try {
      void prepareViolationAudio();
      const id = crypto.randomUUID();
      sessionStorage.setItem(KEY, id);
      accept(await createEntryAttempt(id));
    } catch (caught) {
      setError(caught.message || 'Could not start the scan.');
    }
  }, [accept]);

  const nextWorker = useCallback(() => {
    const id = entry?.session_id;
    if (id) discardEntryAttempt(id).catch(() => {});
    sessionStorage.removeItem(KEY);
    setEntry(null);
    setError('');
    navigate('/entry/biometric', { replace: true });
  }, [entry, navigate]);

  const context = useMemo(() => ({ entry, connection, error, start, nextWorker }), [entry, connection, error, start, nextWorker]);
  return (
    <EntryContext.Provider value={context}>
      <GateFlow step={location.pathname.endsWith('/compliance') ? 2 : 1}>
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(360px,0.85fr)]">
          <div className="panel relative min-h-[560px] overflow-hidden">
            <AnnotatedVisionFeed key={entry?.session_id || 'idle'} sessionId={entry?.session_id} onEntry={accept} onConnection={setConnection} onError={setError} />
            {!entry && <div className="absolute inset-0 grid place-items-center bg-black/45"><button onClick={start} className="rounded-md bg-safety px-7 py-3 text-xs font-bold uppercase text-onSafety shadow-glow">Start entry scan</button></div>}
          </div>
          <Outlet />
        </div>
      </GateFlow>
    </EntryContext.Provider>
  );
}
