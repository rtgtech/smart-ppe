import { CalendarDays, ChevronDown, Clock3, MapPin, Search, X } from 'lucide-react';

export function FilterBar({ filters, setFilters, gates = [], className = '' }) {
  const update = (key, value) => setFilters((current) => ({ ...current, [key]: value }));
  const showDate = filters.period === 'date';

  return (
    <div
      className={`panel mb-6 flex flex-wrap items-end gap-3 p-3 sm:p-4 ${className}`}
      role="search"
      aria-label="Filter records"
    >
      <FilterField label="Search worker" className="w-full flex-[1_1_280px]">
        <ControlShell icon={Search}>
          <input
            className="filter-control pr-9"
            type="search"
            value={filters.worker}
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

      <FilterField label="Day" className="w-full flex-[1_1_145px] sm:w-auto">
        <ControlShell icon={CalendarDays} select>
          <select className="filter-control pr-9" value={filters.period} onChange={(event) => update('period', event.target.value)} aria-label="Filter by day">
            <option value="today">Today</option>
            <option value="yesterday">Yesterday</option>
            <option value="date">Choose date</option>
          </select>
        </ControlShell>
      </FilterField>

      {showDate && (
        <FilterField label="Date" className="w-full flex-[1_1_170px] sm:w-auto">
          <ControlShell icon={CalendarDays}>
            <input className="filter-control" type="date" value={filters.date} onChange={(event) => update('date', event.target.value)} aria-label="Choose a date" />
          </ControlShell>
        </FilterField>
      )}

      <FilterField label="Shift" className="w-full flex-[1_1_145px] sm:w-auto">
        <ControlShell icon={Clock3} select>
          <select className="filter-control pr-9" value={filters.shift} onChange={(event) => update('shift', event.target.value)} aria-label="Filter by shift">
            <option value="ALL">All shifts</option>
            <option value="A">Shift A</option>
            <option value="B">Shift B</option>
            <option value="C">Shift C</option>
          </select>
        </ControlShell>
      </FilterField>

      <FilterField label="Mine checkpoint" className="w-full flex-[1_1_210px] sm:w-auto">
        <ControlShell icon={MapPin} select>
          <select className="filter-control pr-9" value={filters.gateId} onChange={(event) => update('gateId', event.target.value)} aria-label="Filter by mine checkpoint">
            <option value="ALL">All checkpoints</option>
            {gates.map((gate) => (
              <option key={gate.gate_id || gate.id} value={gate.gate_id || gate.id}>{gate.name}</option>
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
