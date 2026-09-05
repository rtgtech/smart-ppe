import { useCallback, useEffect, useRef, useState } from 'react';

const defaultVoiceUrl = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/api/v1/voice/ws`;
};

const VOICE_URL = import.meta.env.VITE_VOICE_WS_URL || defaultVoiceUrl();
const VOICE_DEBUG = import.meta.env.DEV || import.meta.env.VITE_VOICE_DEBUG === 'true';

function voiceLog(message, details) {
  if (!VOICE_DEBUG) return;
  if (details === undefined) console.info(`[SURAKSHA Voice] ${message}`);
  else console.info(`[SURAKSHA Voice] ${message}`, details);
}

export function useVoiceAgent() {
  const [status, setStatus] = useState('idle');
  const [mode, setMode] = useState(null);
  const [error, setError] = useState(null);
  const [transcript, setTranscript] = useState([]);
  const socketRef = useRef(null);
  const sessionIdRef = useRef(null);
  const modeRef = useRef(null);
  const streamRef = useRef(null);
  const audioContextRef = useRef(null);
  const captureNodeRef = useRef(null);
  const playbackSourcesRef = useRef([]);
  const playbackCursorRef = useRef(0);
  const operationRef = useRef(0);
  const sessionErrorRef = useRef(false);

  const releaseAudio = useCallback(async () => {
    captureNodeRef.current?.disconnect();
    captureNodeRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    playbackSourcesRef.current.forEach((source) => {
      try { source.stop(); } catch { /* source already ended */ }
    });
    playbackSourcesRef.current = [];
    playbackCursorRef.current = 0;
    const context = audioContextRef.current;
    audioContextRef.current = null;
    if (context && context.state !== 'closed') await context.close();
  }, []);

  const stopSession = useCallback((reason = 'user-stopped') => {
    operationRef.current += 1;
    const socket = socketRef.current;
    const sessionId = sessionIdRef.current;
    const preserveError = sessionErrorRef.current;
    sessionIdRef.current = null;
    modeRef.current = null;
    socketRef.current = null;
    if (socket?.readyState === WebSocket.OPEN && sessionId) {
      socket.send(JSON.stringify({ type: 'session.stop', sessionId, reason }));
    }
    socket?.close(1000, reason);
    void releaseAudio();
    setMode(null);
    setStatus(preserveError ? 'error' : 'idle');
    if (!preserveError) setTranscript([]);
  }, [releaseAudio]);

  const clearPlayback = useCallback(() => {
    playbackSourcesRef.current.forEach((source) => {
      try { source.stop(); } catch { /* source already ended */ }
    });
    playbackSourcesRef.current = [];
    playbackCursorRef.current = audioContextRef.current?.currentTime || 0;
  }, []);

  const playAudio = useCallback((payload) => {
    const context = audioContextRef.current;
    if (!context || context.state === 'closed' || payload.byteLength < 2) return;
    const pcm = new Int16Array(payload);
    const buffer = context.createBuffer(1, pcm.length, 24_000);
    const channel = buffer.getChannelData(0);
    for (let index = 0; index < pcm.length; index += 1) channel[index] = pcm[index] / 32768;

    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);
    const startAt = Math.max(context.currentTime + 0.02, playbackCursorRef.current);
    source.start(startAt);
    playbackCursorRef.current = startAt + buffer.duration;
    playbackSourcesRef.current.push(source);
    source.onended = () => {
      playbackSourcesRef.current = playbackSourcesRef.current.filter((item) => item !== source);
    };
  }, []);

  const startCapture = useCallback(async (stream, socket, operation) => {
    const context = audioContextRef.current;
    if (!context || operation !== operationRef.current) return;
    await context.audioWorklet.addModule('/pcm-processor.js');
    if (operation !== operationRef.current) return;
    const source = context.createMediaStreamSource(stream);
    const capture = new AudioWorkletNode(context, 'pcm-capture', {
      numberOfInputs: 1,
      numberOfOutputs: 0,
    });
    source.connect(capture);
    capture.port.onmessage = (event) => {
      if (socket.readyState === WebSocket.OPEN && operation === operationRef.current) {
        socket.send(event.data);
      }
    };
    captureNodeRef.current = capture;
    setStatus('listening');
  }, []);

  const startSession = useCallback(async (nextMode) => {
    if (sessionIdRef.current) return;
    const operation = operationRef.current + 1;
    operationRef.current = operation;
    const sessionId = crypto.randomUUID();
    sessionIdRef.current = sessionId;
    modeRef.current = nextMode;
    sessionErrorRef.current = false;
    setMode(nextMode);
    setStatus('connecting');
    setError(null);
    setTranscript([]);

    try {
      const audioContext = new window.AudioContext({ latencyHint: 'interactive' });
      audioContextRef.current = audioContext;
      await audioContext.resume();
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      if (operation !== operationRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;

      const socket = new WebSocket(VOICE_URL);
      socket.binaryType = 'arraybuffer';
      socketRef.current = socket;
      socket.onopen = () => {
        if (operation !== operationRef.current) return socket.close();
        socket.send(JSON.stringify({ type: 'session.start', sessionId, mode: nextMode }));
        void startCapture(stream, socket, operation).catch((caught) => {
          sessionErrorRef.current = true;
          setError(caught instanceof Error ? caught.message : 'Audio capture could not start.');
          setStatus('error');
          socket.close(1011, 'audio-capture-failed');
        });
      };
      socket.onmessage = (event) => {
        if (operation !== operationRef.current) return;
        if (event.data instanceof ArrayBuffer) {
          playAudio(event.data);
          return;
        }
        try {
          const message = JSON.parse(event.data);
          if (message.sessionId && message.sessionId !== sessionIdRef.current) return;
          if (message.type === 'audio.clear') clearPlayback();
          if (message.type === 'status' && message.state) setStatus(message.state);
          if (message.type === 'transcript' && message.speaker && message.text) {
            setTranscript((lines) => [...lines.slice(-2), {
              speaker: message.speaker,
              text: message.text,
            }]);
          }
          if (message.type === 'error') {
            sessionErrorRef.current = true;
            setError(message.message || 'The voice agent encountered an error.');
            setStatus('error');
          }
        } catch (caught) {
          voiceLog('Invalid server event', caught);
        }
      };
      socket.onerror = () => {
        if (operation === operationRef.current) {
          sessionErrorRef.current = true;
          setError('Could not connect to the voice service. Is the backend running?');
          setStatus('error');
        }
      };
      socket.onclose = () => {
        if (operation === operationRef.current && sessionIdRef.current) stopSession('socket-closed');
      };
    } catch (caught) {
      if (operation !== operationRef.current) return;
      sessionIdRef.current = null;
      modeRef.current = null;
      sessionErrorRef.current = true;
      setMode(null);
      setStatus('error');
      setError(caught instanceof Error ? caught.message : 'Microphone access was not available.');
      await releaseAudio();
    }
  }, [clearPlayback, playAudio, releaseAudio, startCapture, stopSession]);

  const toggleSession = useCallback(() => {
    if (sessionIdRef.current) stopSession('microphone-clicked');
    else void startSession('toggle');
  }, [startSession, stopSession]);

  const beginPushToTalk = useCallback(() => {
    if (!sessionIdRef.current) void startSession('push-to-talk');
  }, [startSession]);

  const endPushToTalk = useCallback(() => {
    if (sessionIdRef.current && modeRef.current === 'push-to-talk') {
      stopSession('control-released');
    }
  }, [stopSession]);

  const clearError = useCallback(() => {
    sessionErrorRef.current = false;
    setError(null);
    setStatus('idle');
  }, []);

  useEffect(() => () => stopSession('component-unmounted'), [stopSession]);

  return {
    status,
    mode,
    error,
    transcript,
    toggleSession,
    beginPushToTalk,
    endPushToTalk,
    clearError,
  };
}
