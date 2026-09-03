import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mountain, Lock } from 'lucide-react';
import CaveBackdrop from '../components/CaveBackdrop';
import ThemeToggle from '../components/ThemeToggle';

const ROLES = ['Mine Administrator', 'Safety Officer', 'Shift Supervisor', 'Gate Operator', 'Auditor'];

export default function Login() {
  const navigate = useNavigate();
  const [role, setRole] = useState('Safety Officer');

  function handleSubmit(e) {
    e.preventDefault();
    navigate('/dashboard');
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden px-4">
      <CaveBackdrop intensity={0.6} />
      <ThemeToggle className="absolute right-5 top-5 z-20" />

      <form onSubmit={handleSubmit} className="relative z-10 w-full max-w-md panel-elevated p-8 rock-texture animate-fadeUp">
        <div className="flex items-center gap-2 mb-1">
          <Mountain size={20} className="text-safety" />
          <span className="font-extrabold tracking-tight">SURAKSHA MINE OS</span>
        </div>
        <div className="label-op text-safety mb-6">SECURE ACCESS</div>

        <div className="space-y-4">
          <Field label="Employee ID">
            <input defaultValue="SO-2291" className="field" />
          </Field>
          <Field label="Password">
            <div className="relative">
              <input type="password" defaultValue="••••••••••" className="field pr-9" />
              <Lock size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-textMuted" />
            </div>
          </Field>
          <Field label="Mine">
            <select className="field" defaultValue="Central Coal Mine">
              <option>Central Coal Mine</option>
              <option>Jharia Coal Mine</option>
              <option>Korba Coal Mine</option>
            </select>
          </Field>
          <Field label="Role">
            <select className="field" value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLES.map((r) => <option key={r}>{r}</option>)}
            </select>
          </Field>
        </div>

        <button
          type="submit"
          className="w-full mt-7 py-3 rounded-md bg-safety text-onSafety font-bold text-sm tracking-wide shadow-glowSm hover:brightness-110 transition focus-ring"
        >
          SECURE LOGIN
        </button>

        <div className="flex items-center justify-center gap-1.5 mt-5">
          <span className="status-dot bg-safety animate-pulseGlow" />
          <span className="label-op !text-[0.62rem] text-safety">SYSTEM ONLINE</span>
        </div>
      </form>

    </div>
  );
}

function Field({ label, children }) {
  return (
    <label className="block">
      <div className="label-op mb-1.5">{label}</div>
      {children}
    </label>
  );
}
