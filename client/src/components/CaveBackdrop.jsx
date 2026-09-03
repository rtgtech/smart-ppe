import heroTunnel from '../assets/hero-tunnel.png';

export default function CaveBackdrop({ intensity = 1 }) {
  return (
    <div className="cave-backdrop-base absolute inset-0 overflow-hidden">
      <img
        src={heroTunnel}
        alt=""
        className="cave-backdrop-image absolute inset-0 h-full w-full object-cover object-[58%_center] opacity-90 scale-[1.015]"
      />

      <div className="cave-overlay-horizontal absolute inset-0" />
      <div className="cave-overlay-vertical absolute inset-0" />
      <div
        className="cave-overlay-vignette absolute inset-0"
        style={{ opacity: 0.72 + intensity * 0.08 }}
      />
    </div>
  );
}
