import { CalendarDays, ChevronDown, ChevronLeft, ChevronRight, Clock3, MapPin, Search, X } from 'lucide-react';
import { getTodayString } from '../data/filters';

function shiftDays(dateStr, offset) {
  const current = dateStr || getTodayString();
  const [year, month, day] = current.split('-').map(Number);
  const d = new Date(year, month - 1, day);
  d.setDate(d.getDate() + offset);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const dt = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${dt}`;
}

export function FilterBar({ filters, setFilters, gates = [], className = '' }) {
  const update = (key, value) => setFilters((current) => ({ ...current, [key]: value }));
  const currentDate = filters.date || getTodayString();
  const todayStr = getTodayString();
  const isToday = currentDate === todayStr;

  const handlePrevDay = () => {
    const prev = shiftDays(currentDate, -1);
    setFilters((prevF) => ({ ...prevF, date: prev, period: 'date' }));
  };

  const handleNextDay = () => {
    const next = shiftDays(currentDate, 1);
    setFilters((prevF) => ({ ...prevF, date: next, period: 'date' }));
  };

  const handleDateChange = (e) => {
    const val = e.target.value;
    if (val) {
      setFilters((prevF) => ({ ...prevF, date: val, period: 'date' }));
    }
  };

  const jumpToToday = () => {
    setFilters((prevF) => ({ ...prevF, date: todayStr, period: 'date' }));
  };

  return (
    <div
      className={`panel mb-6 flex flex-wrap items-end gap-3 p-3 sm:p-4 ${className}`}
      role="search"
      aria-label="Filter records"
    >
      <FilterField label="Search worker" className="w-full flex-[1_1_240px]">
        <ControlShell icon={Search}>
          <input
            className="filter-control pr-9"
            type="search"
            value={filters.worker || ''}
            onChange={(event) => update('worker', event.target.value)}
            placeholder="Name or employee ID"
            aria-label="Search worker by name or employee ID"
          />
          {filters.worker && (
            <button type="button" className="filter-control-action" onClick={() => update('worker', '')} aria-label="Clear worker search">
              <X size={14} />
            </button>
          )}
        </ControlShell>
      </FilterField>

      {/* Calendar Day Swapper */}
      <FilterField label="Calendar Day" className="w-full flex-[1_1_250px] sm:w-auto">
        <div className="flex items-center gap-1">
          <div className="filter-control-shell flex-1 flex items-center relative">
            <CalendarDays size={15} className="filter-control-icon text-safety pointer-events-none" aria-hidden="true" />
            <input
              type="date"
              value={currentDate}
              onChange={handleDateChange}
              className="filter-control cursor-pointer mono text-xs font-semibold pl-9 pr-2"
              aria-label="Choose calendar date"
              title="Click to open calendar"
            />
          </div>

          <button
            type="button"
            onClick={handlePrevDay}
            className="p-2 rounded-md border border-border bg-input hover:border-safety/50 text-textSecondary hover:text-text transition focus-ring"
            title="Previous Day"
            aria-label="Previous day"
          >
            <ChevronLeft size={14} />
          </button>

          <button
            type="button"
            onClick={handleNextDay}
            className="p-2 rounded-md border border-border bg-input hover:border-safety/50 text-textSecondary hover:text-text transition focus-ring"
            title="Next Day"
            aria-label="Next day"
          >
            <ChevronRight size={14} />
          </button>

          {!isToday && (
            <button
              type="button"
              onClick={jumpToToday}
              className="px-2.5 py-1.5 rounded-md border border-safety/40 bg-safetySubtle text-safety hover:bg-safety/20 text-[0.65rem] font-bold uppercase tracking-wider transition focus-ring"
              title="Jump to Today"
            >
              Today
            </button>
          )}
        </div>
      </FilterField>

      <FilterField label="Shift" className="w-full flex-[1_1_130px] sm:w-auto">
        <ControlShell icon={Clock3} select>
          <select className="filter-control pr-9" value={filters.shift || 'ALL'} onChange={(event) => update('shift', event.target.value)} aria-label="Filter by shift">
            <option value="ALL" className="bg-surface text-text">All shifts</option>
            <option value="A" className="bg-surface text-text">Shift A</option>
            <option value="B" className="bg-surface text-text">Shift B</option>
            <option value="C" className="bg-surface text-text">Shift C</option>
          </select>
        </ControlShell>
      </FilterField>

      <FilterField label="Mine checkpoint" className="w-full flex-[1_1_190px] sm:w-auto">
        <ControlShell icon={MapPin} select>
          <select className="filter-control pr-9" value={filters.gateId || 'ALL'} onChange={(event) => update('gateId', event.target.value)} aria-label="Filter by mine checkpoint">
            <option value="ALL" className="bg-surface text-text">All checkpoints</option>
            {gates.map((gate) => (
              <option key={gate.gate_id || gate.id} value={gate.gate_id || gate.id} className="bg-surface text-text">{gate.name}</option>
            ))}
          </select>
        </ControlShell>
      </FilterField>
    </div>
  );
}

function FilterField({ label, className = '', children }) {
  return (
    <label className={`block min-w-0 ${className}`}>
      <span className="filter-label">{label}</span>
      {children}
    </label>
  );
}

function ControlShell({ icon: Icon, select = false, children }) {
  return (
    <div className="filter-control-shell">
      <Icon size={15} className="filter-control-icon" aria-hidden="true" />
      {children}
      {select && <ChevronDown size={14} className="filter-control-chevron" aria-hidden="true" />}
    </div>
  );
}