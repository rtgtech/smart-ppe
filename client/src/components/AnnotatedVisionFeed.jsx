import { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, LoaderCircle, WifiOff } from 'lucide-react';

const socketUrl = (id) => {
  const base = import.meta.env.VITE_ENTRY_WS_URL?.replace(/\/$/, '');
  if (base) return `${base}/${id}/stream`;
  return `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.hostname}:8000/api/v1/entry/attempts/${id}/stream`;
};

export default function AnnotatedVisionFeed({ sessionId, onEntry, onConnection, onError }) {
  const video = useRef(null);
  const canvas = useRef(null);
  const imageUrl = useRef(null);
  const [image, setImage] = useState(null);
  const [message, setMessage] = useState('');

  const fail = useCallback((text) => {
    setMessage(text);
    onError?.(text);
  }, [onError]);

  useEffect(() => {
    if (!sessionId) return undefined;
    let media, timer, socket, waiting = false, complete = false, cancelled = false;
    const stop = () => {
      clearInterval(timer);
      media?.getTracks().forEach((track) => track.stop());
      if (socket?.readyState < WebSocket.CLOSING) socket.close();
      onConnection?.('offline');
    };
    const send = () => {
      if (waiting || socket?.readyState !== WebSocket.OPEN || video.current?.readyState < 2) return;
      const scale = Math.min(1, 960 / video.current.videoWidth);
      canvas.current.width = Math.round(video.current.videoWidth * scale);
      canvas.current.height = Math.round(video.current.videoHeight * scale);
      canvas.current.getContext('2d').drawImage(video.current, 0, 0, canvas.current.width, canvas.current.height);
      canvas.current.toBlob((blob) => {
        if (blob && socket.readyState === WebSocket.OPEN) {
          waiting = true;
          socket.send(blob);
        }
      }, 'image/jpeg', .8);
    };
    const start = async () => {
      try {
        onConnection?.('connecting');
        media = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: false });
        if (cancelled) return stop();
        video.current.srcObject = media;
        await video.current.play();
        socket = new WebSocket(socketUrl(sessionId));
        socket.binaryType = 'blob';
        socket.onopen = () => {
          onConnection?.('online');
          send();
          timer = setInterval(send, 100);
        };
        socket.onmessage = (event) => {
          if (typeof event.data !== 'string') {
            const next = URL.createObjectURL(event.data);
            if (imageUrl.current) URL.revokeObjectURL(imageUrl.current);
            imageUrl.current = next;
            setImage(next);
            waiting = false;
            return;
          }
          const data = JSON.parse(event.data);
          if (data.entry) onEntry?.(data.entry);
          if (data.type === 'error') {
            waiting = false;
            fail(data.message || 'Inference failed');
          }
          if (data.type === 'session_complete') {
            complete = true;
            stop();
          }
        };
        socket.onerror = () => fail('Could not connect to the vision server.');
        socket.onclose = () => {
          stop();
          if (!complete && !cancelled) fail('Vision stream disconnected.');
        };
      } catch (error) {
        fail(error.message || 'Camera access failed.');
        stop();
      }
    };
    start();
    return () => {
      cancelled = true;
      stop();
    };
  }, [fail, onConnection, onEntry, sessionId]);

  useEffect(() => () => imageUrl.current && URL.revokeObjectURL(imageUrl.current), []);

  return (
    <div className="relative h-full min-h-[420px] overflow-hidden bg-black">
      <video ref={video} muted playsInline className="hidden" />
      <canvas ref={canvas} className="hidden" />
      {image ? <img src={image} alt="Live annotated entry scan" className="absolute inset-0 h-full w-full object-contain" /> : (
        <div className="absolute inset-0 grid place-items-center text-center text-textMuted">
          <div>{message ? <WifiOff className="mx-auto mb-3 text-danger" size={36} /> : sessionId ? <LoaderCircle className="mx-auto mb-3 animate-spin text-safety" size={36} /> : <Camera className="mx-auto mb-3" size={36} />}<p className="text-sm">{message || (sessionId ? 'Starting camera…' : 'Camera is idle')}</p></div>
        </div>
      )}
      {image && <span className="absolute left-3 top-3 rounded bg-black/70 px-2 py-1 font-mono text-[10px] text-safety">LIVE · ANNOTATED</span>}
    </div>
  );
}
