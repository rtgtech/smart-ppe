import { useNavigate } from 'react-router-dom';
import {
  Mountain,
  ScanFace,
  ShieldCheck,
  WifiOff,
  FileCheck2,
} from 'lucide-react';

import PrismaticBurst from '../components/PrismaticBurst';
import ThemeToggle from '../components/ThemeToggle';
import { useTheme } from '../theme-context';

const FEATURES = [
  { icon: ScanFace, label: 'AI VISION' },
  { icon: ShieldCheck, label: 'REAL-TIME VERIFICATION' },
  { icon: WifiOff, label: 'OFFLINE-FIRST' },
  { icon: FileCheck2, label: 'AUDIT READY' },
];

export default function Home() {
  const navigate = useNavigate();
  const { theme } = useTheme();
  const isLight = theme === 'light';

  return (
    <div className="relative min-h-screen overflow-hidden flex flex-col bg-bg transition-colors duration-300">

      {/* =========================================================
          PRISMATIC BURST BACKGROUND
          ========================================================= */}
      <div className="absolute inset-0 z-0 overflow-hidden">

        <div className="absolute inset-0 opacity-100">
          <PrismaticBurst
            intensity={isLight ? 1.25 : 1.8}
            speed={0.22}
            animationType="rotate3d"
            colors={[
              '#00D9FF',
              '#4169E1',
              '#7657FF',
              '#00C9A7',
              '#00FF88',
            ]}
            distort={1.15}
            rayCount={14}
            mixBlendMode="screen"
            lightMode={isLight}
          />
        </div>

        {/* Keeps the left side dark for readable typography
            without killing the burst on the right */}
        <div
          className="
            absolute inset-0
            bg-gradient-to-r
            from-bg/95
            via-bg/60
            to-bg/5
          "
        />

        {/* Very subtle cinematic darkening */}
        <div
          className="absolute inset-0"
          style={{
            background: 'radial-gradient(ellipse at 65% 50%, rgb(var(--color-safety) / 0.08), transparent 48%)',
          }}
        />

        {/* Bottom fade */}
        <div
          className="
            absolute inset-x-0 bottom-0 h-40
            bg-gradient-to-t
            from-bg/85
            to-bg/0
          "
        />

      </div>


      {/* =========================================================
          HEADER
          ========================================================= */}
      <header
        className="
          relative z-10
          max-w-[1440px]
          w-full
          mx-auto
          px-6 lg:px-10
          pt-8
          flex items-center justify-between
        "
      >

        {/* BRAND */}
        <div className="flex items-center gap-2">

          <Mountain
            size={22}
            className="text-safety"
            strokeWidth={2.4}
          />

          <div>
            <div className="font-extrabold tracking-tight leading-none">
              SURAKSHA
            </div>

            <div
              className="
                label-op
                !text-[0.58rem]
                !text-textMuted
                leading-none
                mt-0.5
              "
            >
              MINE SAFETY INTELLIGENCE
            </div>
          </div>

        </div>


        {/* HEADER ACTIONS */}
        <div className="flex items-center gap-2">

          <ThemeToggle />

          <button
            onClick={() => navigate('/login')}
            className="
              label-op
              !text-xs
              border
              border-border
              px-3.5
              py-2
              rounded-md
              hover:border-safety
              hover:text-safety
              transition-colors
              focus-ring
              backdrop-blur-sm
            "
          >
            SECURE ACCESS
          </button>

        </div>

      </header>


      {/* =========================================================
          HERO
          ========================================================= */}
      <main
        className="
          relative z-10
          flex-1
          max-w-[1440px]
          w-full
          mx-auto
          px-6 lg:px-10
          flex flex-col
          justify-center
          items-start
          py-16
        "
      >

        {/* SYSTEM STATUS */}
        <div
          className="
            label-op
            text-safety
            mb-4
            flex
            items-center
            gap-2
          "
        >
          <span
            className="
              status-dot
              bg-safety
              animate-pulseGlow
            "
          />

          SYSTEM ONLINE — 5 MINES CONNECTED
        </div>


        {/* HEADLINE */}
        <h1
          className="
            text-4xl
            sm:text-5xl
            lg:text-6xl
            font-extrabold
            tracking-tight
            leading-[1.05]
            max-w-3xl
          "
        >
          EVERY WORKER.
          <br />
          EVERY GATE.
          <br />
          EVERY TIME.
        </h1>


        {/* DESCRIPTION */}
        <p
          className="
            text-textSecondary
            mt-6
            max-w-lg
            text-sm
            sm:text-base
            leading-relaxed
          "
        >
          Smart PPE compliance monitoring for safer underground mining
          operations — AI vision and RFID verification at every gate,
          online or off.
        </p>


        {/* CTA BUTTONS */}
        <div className="flex flex-wrap gap-3 mt-8">

          <button
            onClick={() => navigate('/dashboard')}
            className="
              px-6
              py-3
              rounded-md
              bg-safety
              text-onSafety
              font-bold
              text-sm
              tracking-wide
              shadow-glow
              hover:brightness-110
              transition
              focus-ring
            "
          >
            ENTER COMMAND CENTER
          </button>


          <button
            onClick={() => navigate('/live')}
            className="
              px-6
              py-3
              rounded-md
              border
              border-border
              text-text
              font-bold
              text-sm
              tracking-wide
              hover:border-safety
              hover:text-safety
              transition
              focus-ring
              backdrop-blur-sm
            "
          >
            SEE LIVE MONITORING
          </button>

        </div>

      </main>


      {/* =========================================================
          FEATURE BAR
          ========================================================= */}
      <footer
        className="
          relative z-10
          max-w-[1440px]
          w-full
          mx-auto
          px-6 lg:px-10
          pb-8
        "
      >

        <div
          className="
            flex
            flex-wrap
            items-center
            gap-x-8
            gap-y-3
            border-t
            border-border/70
            pt-6
          "
        >

          {FEATURES.map(({ icon: Icon, label }) => (
            <div
              key={label}
              className="
                flex
                items-center
                gap-2
                text-textSecondary
              "
            >

              <Icon
                size={14}
                className="text-safety"
              />

              <span
                className="
                  label-op
                  !text-[0.62rem]
                "
              >
                {label}
              </span>

            </div>
          ))}

        </div>

      </footer>

    </div>
  );
}
