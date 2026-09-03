import { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, LoaderCircle, RefreshCw, WifiOff } from 'lucide-react';

const MAX_FRAME_WIDTH = 960;
const TARGET_FPS = 12;

function getWebSocketUrl() {
  if (import.meta.env.VITE_VISION_WS_URL) return import.meta.env.VITE_VISION_WS_URL;
  if (import.meta.env.VITE_WS_URL) return import.meta.env.VITE_WS_URL;
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.hostname}:8000/ws/inference`;
}

export default function AnnotatedVisionFeed({ active, onConnectionChange, onFrameMeta }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const socketRef = useRef(null);
  const mediaRef = useRef(null);
  const timerRef = useRef(null);
  const waitingRef = useRef(false);
  const resultUrlRef = useRef(null);
  const runRef = useRef(0);
  const [resultUrl, setResultUrl] = useState(null);
  const [_connection, setConnection] = useState('offline');
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);

  const updateConnection = useCallback((next) => {
    setConnection(next);
    onConnectionChange?.(next);
  }, [onConnectionChange]);

  const release = useCallback(() => {
    runRef.current += 1;
    if (timerRef.current !== null) window.clearInterval(timerRef.current);
    timerRef.current = null;
    const socket = socketRef.current;
    socketRef.current = null;
    if (socket && socket.readyState < WebSocket.CLOSING) socket.close();
    mediaRef.current?.getTracks().forEach((track) => track.stop());
    mediaRef.current = null;
    waitingRef.current = false;
    if (videoRef.current) videoRef.current.srcObject = null;
  }, []);

  const sendFrame = useCallback(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const socket = socketRef.current;
    if (!video || !canvas || !socket || socket.readyState !== WebSocket.OPEN ||
        waitingRef.current || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA ||
        socket.bufferedAmount > 512_000) return;

    const scale = Math.min(1, MAX_FRAME_WIDTH / video.videoWidth);
    canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
    canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
    const context = canvas.getContext('2d', { alpha: false });
    if (!context) return;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (!blob || socket.readyState !== WebSocket.OPEN) return;
      waitingRef.current = true;
      socket.send(blob);
    }, 'image/jpeg', 0.78);
  }, []);

  /* The inactive transition must synchronously clear connection/frame UI with the camera cleanup. */
  /* oxlint-disable react/set-state-in-effect */
  useEffect(() => {
    if (!active) {
      release();
      updateConnection('offline');
      setError('');
      if (resultUrlRef.current) URL.revokeObjectURL(resultUrlRef.current);
      resultUrlRef.current = null;
      setResultUrl(null);
      return undefined;
    }

    const run = runRef.current + 1;
    runRef.current = run;
    let cancelled = false;
    const isCurrent = () => !cancelled && runRef.current === run;

    async function start() {
      setError('');
      updateConnection('connecting');
      try {
        const media = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'environment' },
          audio: false,
        });
        if (!isCurrent()) {
          media.getTracks().forEach((track) => track.stop());
          return;
        }
        mediaRef.current = media;
        if (!videoRef.current) throw new Error('Camera capture could not be initialized.');
        videoRef.current.srcObject = media;
        await videoRef.current.play();

        const socket = new WebSocket(getWebSocketUrl());
        let socketFailed = false;
        socket.binaryType = 'blob';
        socketRef.current = socket;
        socket.onopen = () => {
          if (!isCurrent()) return;
          socket.send(JSON.stringify({ type: 'config', confidence: 0.5 }));
          updateConnection('online');
          sendFrame();
          timerRef.current = window.setInterval(sendFrame, Math.round(1000 / TARGET_FPS));
        };
        socket.onmessage = (event) => {
          if (!isCurrent()) return;
          if (typeof event.data === 'string') {
            try {
              const message = JSON.parse(event.data);
              if (message.type === 'error') {
                waitingRef.current = false;
                setError(message.message || 'The inference server reported an error.');
              } else if (message.type === 'frame_meta') {
                onFrameMeta?.(message);
              }
            } catch {
              waitingRef.current = false;
              setError('The inference server returned an invalid response.');
            }
            return;
          }
          const nextUrl = URL.createObjectURL(event.data);
          if (resultUrlRef.current) URL.revokeObjectURL(resultUrlRef.current);
          resultUrlRef.current = nextUrl;
          setResultUrl(nextUrl);
          waitingRef.current = false;
        };
        socket.onerror = () => {
          if (!isCurrent()) return;
          socketFailed = true;
          updateConnection('error');
          setError(`Could not connect to the vision server at ${getWebSocketUrl()}.`);
        };
        socket.onclose = () => {
          if (!isCurrent()) return;
          waitingRef.current = false;
          updateConnection(socketFailed ? 'error' : 'offline');
          setError((current) => current || 'The vision server disconnected.');
          if (resultUrlRef.current) URL.revokeObjectURL(resultUrlRef.current);
          resultUrlRef.current = null;
          setResultUrl(null);
          release();
        };
      } catch (caught) {
        if (!isCurrent()) return;
        updateConnection('error');
        setError(caught instanceof Error ? caught.message : 'Camera access failed.');
        release();
      }
    }

    void start();
    return () => {
      cancelled = true;
      release();
    };
  }, [active, onFrameMeta, release, retry, sendFrame, updateConnection]);
  /* oxlint-enable react/set-state-in-effect */

  useEffect(() => () => {
    release();
    if (resultUrlRef.current) URL.revokeObjectURL(resultUrlRef.current);
  }, [release]);

  return (
    <div className="relative w-full h-full min-h-[420px] bg-[#020604] overflow-hidden">
      {/* These capture frames but are never visible. Only server-annotated output is rendered. */}
      <video ref={videoRef} muted playsInline className="absolute w-px h-px opacity-0 pointer-events-none" aria-hidden="true" />
      <canvas ref={canvasRef} className="hidden" aria-hidden="true" />

      {resultUrl ? (
        <img src={resultUrl} alt="Live annotated PPE and identity detection" className="absolute inset-0 h-full w-full object-contain bg-black" />
      ) : (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-8 text-center text-textMuted">
          {error ? (
            <WifiOff size={36} className="text-danger" />
          ) : active ? (
            <div className="relative flex items-center justify-center">
              <LoaderCircle size={38} className="animate-spin text-safety" />
              <div className="absolute inset-0 rounded-full animate-ping bg-safety/20 -z-10" />
            </div>
          ) : (
            <Camera size={34} />
          )}
          <div>
            <div className="text-sm font-semibold text-text">
              {error ? 'Stream unavailable' : active ? 'Initializing AI Camera…' : 'Camera is idle'}
            </div>
            <div className="mt-1 text-xs text-textSecondary">
              {error || (active ? 'Starting camera feed and loading vision inference…' : 'Start verification to begin live detection.')}
            </div>
          </div>
          {error && active && (
            <button type="button" onClick={() => setRetry((value) => value + 1)} className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-semibold text-textSecondary hover:border-safety/50 hover:text-text transition focus-ring">
              <RefreshCw size={12} /> RETRY STREAM
            </button>
          )}
        </div>
      )}

      {resultUrl && <div className="absolute left-3 top-3 mono text-[0.65rem] px-2 py-1 rounded bg-black/70 border border-safety/40 text-safety"><span className="inline-block w-1.5 h-1.5 rounded-full bg-safety mr-1.5 animate-pulseGlow" />ANNOTATED LIVE</div>}
    </div>
  );
}