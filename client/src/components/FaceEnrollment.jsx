import { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, Check, RefreshCw, ScanFace, Trash2, VideoOff } from 'lucide-react';
import { Button } from './ui';

const REQUIRED_CAPTURES = 5;
const MAX_CAPTURE_WIDTH = 960;

export default function FaceEnrollment({ captures, onChange, disabled = false }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const cameraRunRef = useRef(0);
  const [cameraState, setCameraState] = useState('idle');
  const [error, setError] = useState('');

  const stopCamera = useCallback(() => {
    cameraRunRef.current += 1;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraState('idle');
  }, []);

  useEffect(() => () => {
    cameraRunRef.current += 1;
    streamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  async function startCamera() {
    const cameraRun = cameraRunRef.current + 1;
    cameraRunRef.current = cameraRun;
    setError('');
    setCameraState('starting');
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error('Camera access is not available in this browser.');
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'user',
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });
      if (cameraRunRef.current !== cameraRun) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      if (!videoRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        throw new Error('Camera preview could not be initialized.');
      }
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setCameraState('ready');
    } catch (caught) {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setCameraState('error');
      setError(caught instanceof Error ? caught.message : 'Unable to start the camera.');
    }
  }

  function captureFrame() {
    const video = videoRef.current;
    if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA || captures.length >= REQUIRED_CAPTURES) return;

    const scale = Math.min(1, MAX_CAPTURE_WIDTH / video.videoWidth);
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
    canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
    const context = canvas.getContext('2d', { alpha: false });
    if (!context) {
      setError('The camera frame could not be captured.');
      return;
    }
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (!blob) {
        setError('The camera frame could not be captured.');
        return;
      }
      onChange([...captures, blob]);
      if (captures.length + 1 === REQUIRED_CAPTURES) stopCamera();
    }, 'image/jpeg', 0.9);
  }

  function clearCaptures() {
    onChange([]);
    setError('');
  }

  const complete = captures.length === REQUIRED_CAPTURES;

  return (
    <section className="mt-5 rounded-lg border border-border bg-input/50 p-4">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-bold">
            <ScanFace size={16} className={complete ? 'text-safety' : 'text-textSecondary'} />
            Face registration
            {complete && <span className="inline-flex items-center gap-1 text-[0.65rem] text-safety"><Check size={11} /> READY</span>}
          </div>
          <p className="mt-1 text-xs text-textSecondary">
            Capture five clear photos. Keep one person in frame and slightly change head position between captures.
          </p>
        </div>
        <span className={`mono text-xs ${complete ? 'text-safety' : 'text-textSecondary'}`}>
          {captures.length}/{REQUIRED_CAPTURES}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_180px] gap-3">
        <div className="relative min-h-52 overflow-hidden rounded-md border border-border bg-black">
          <video
            ref={videoRef}
            muted
            playsInline
            className={`h-52 w-full object-cover -scale-x-100 ${cameraState === 'ready' ? 'block' : 'hidden'}`}
          />
          {cameraState !== 'ready' && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-5 text-center text-textMuted">
              {cameraState === 'starting' ? <RefreshCw size={26} className="animate-spin text-safety" /> : <VideoOff size={26} />}
              <span className="text-xs">
                {cameraState === 'starting' ? 'Starting camera…' : complete ? 'Five captures complete.' : 'Start the camera to capture the worker’s face.'}
              </span>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <div className="grid grid-cols-5 sm:grid-cols-2 gap-2">
            {Array.from({ length: REQUIRED_CAPTURES }, (_, index) => (
              <div
                key={index}
                className={`aspect-square rounded-md border flex items-center justify-center ${index < captures.length ? 'border-safety/60 bg-safetySubtle text-safety' : 'border-border text-textMuted'}`}
                aria-label={`Face capture ${index + 1}${index < captures.length ? ' complete' : ' pending'}`}
              >
                {index < captures.length ? <Check size={15} /> : <span className="mono text-[0.65rem]">{index + 1}</span>}
              </div>
            ))}
          </div>

          {cameraState === 'ready' ? (
            <Button type="button" onClick={captureFrame} disabled={disabled || complete} className="w-full">
              <Camera size={13} /> CAPTURE {Math.min(captures.length + 1, REQUIRED_CAPTURES)}
            </Button>
          ) : !complete ? (
            <Button type="button" onClick={startCamera} disabled={disabled || cameraState === 'starting'} className="w-full">
              <Camera size={13} /> START CAMERA
            </Button>
          ) : null}

          {captures.length > 0 && (
            <Button type="button" variant="outline" onClick={clearCaptures} disabled={disabled} className="w-full">
              <Trash2 size={13} /> RETAKE ALL
            </Button>
          )}
        </div>
      </div>

      {error && <p className="mt-3 text-xs text-danger">{error}</p>}
    </section>
  );
}
