import { useEffect, useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Users,
  LogIn,
  LogOut,
  AlertTriangle,
  Search,
  Plus,
  X,
  MapPin,
  Clock,
  ShieldCheck,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react';
import { PageHeader, StatCard, SectionHeader, Badge, Button, StatusDot } from '../components/ui';
import {
  listAttendance,
  getZones,
  getAttendanceKpi,
  checkInWorker,
  checkOutWorker,
} from '../services/attendance';
import { listGates } from '../services/gates';
import { listWorkers } from '../services/workers';
import { FilterBar } from '../components/DataFilters';
import { DEFAULT_FILTERS } from '../data/filters';

const STATUS_FILTERS = ['ALL', 'UNDERGROUND', 'EXITED', 'FLAGGED PPE'];

function parseIsoDate(isoStr) {
  if (!isoStr) return null;
  if (typeof isoStr === 'string') {
    const clean = isoStr.replace('Z', '').split('.')[0];
    const parts = clean.split(/[-T:\s]/);
    if (parts.length >= 5) {
      const year = parseInt(parts[0], 10);
      const month = parseInt(parts[1], 10) - 1;
      const day = parseInt(parts[2], 10);
      const hour = parseInt(parts[3], 10);
      const min = parseInt(parts[4], 10);
      const sec = parts[5] ? parseInt(parts[5], 10) : 0;
      return new Date(year, month, day, hour, min, sec);
    }
  }
  const d = new Date(isoStr);
  return isNaN(d.getTime()) ? null : d;
}

function formatTime(isoStr) {
  const d = parseIsoDate(isoStr);
  if (!d) return '—';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: true });
}

function formatDate(isoStr) {
  const d = parseIsoDate(isoStr);
  if (!d) return '—';
  return d.toLocaleDateString([], { day: '2-digit', month: 'short', year: 'numeric' });
}

function calcDuration(entryIso, exitIso) {
  const start = parseIsoDate(entryIso);
  if (!start) return '—';
  const end = parseIsoDate(exitIso) || new Date();
  const diffMs = Math.max(0, end.getTime() - start.getTime());
  const mins = Math.floor(diffMs / 60000);
  const hrs = Math.floor(mins / 60);
  const remMins = mins % 60;
  if (hrs === 0) return `${remMins}m`;
  return `${hrs}h ${remMins}m`;
}

export default function Attendance() {
  const navigate = useNavigate();
  const [kpi, setKpi] = useState({});
  const [zones, setZones] = useState([]);
  const [rows, setRows] = useState([]);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [gates, setGates] = useState([]);
  const [workersList, setWorkersList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [actionLoading, setActionLoading] = useState({});

  // Check-In Modal State
  const [checkInModal, setCheckInModal] = useState(false);
  const [checkInForm, setCheckInForm] = useState({
    worker_id: '',
    gate_id: '',
    entry_time: '',
  });
  const [modalSaving, setModalSaving] = useState(false);
  const [modalError, setModalError] = useState('');

  const loadData = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    else setRefreshing(true);
    try {
      const [nextKpi, nextZones, nextRows] = await Promise.all([
        getAttendanceKpi(filters),
        getZones(filters),
        listAttendance(filters),
      ]);
      setKpi(nextKpi || {});
      setZones(nextZones || []);
      setRows(nextRows || []);
    } catch {
      // Keep existing data on transient network hiccups
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [filters]);

  useEffect(() => {
    listGates().then(setGates).catch(() => {});
    listWorkers().then(setWorkersList).catch(() => {});
  }, []);

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- initial data fetch on mount and filter changes
    loadData();
  }, [loadData]);

  // Client-side quick filter
  const filteredRows = useMemo(() => {
    return rows.filter((r) => {
      const q = searchQuery.toLowerCase().trim();
      const matchesQuery =
        !q ||
        (r.worker && r.worker.toLowerCase().includes(q)) ||
        (r.workerId && r.workerId.toLowerCase().includes(q)) ||
        (r.location && r.location.toLowerCase().includes(q)) ||
        (r.department && r.department.toLowerCase().includes(q));

      const matchesStatus =
        statusFilter === 'ALL' ||
        (statusFilter === 'UNDERGROUND' && r.status === 'UNDERGROUND') ||
        (statusFilter === 'EXITED' && r.status === 'EXITED') ||
        (statusFilter === 'FLAGGED PPE' && (r.ppe === 'FLAGGED' || r.ppe === 'DENIED'));

      return matchesQuery && matchesStatus;
    });
  }, [rows, searchQuery, statusFilter]);

  async function handleCheckOut(attendanceId, e) {
    if (e) e.stopPropagation();
    setActionLoading((prev) => ({ ...prev, [attendanceId]: true }));
    try {
      await checkOutWorker(attendanceId);
      await loadData(true);
    } catch (err) {
      alert(err.message || 'Failed to mark worker checkout.');
    } finally {
      setActionLoading((prev) => ({ ...prev, [attendanceId]: false }));
    }
  }

  function openCheckIn() {
    const selectedDate = filters.date || (new Date().toISOString().slice(0, 10));
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const mins = String(now.getMinutes()).padStart(2, '0');
    const initialDateTime = `${selectedDate}T${hours}:${mins}`;

    setCheckInForm({
      worker_id: workersList[0]?.worker_id || '',
      gate_id: gates[0]?.gate_id || '',
      entry_time: initialDateTime,
    });
    setModalError('');
    setCheckInModal(true);
  }

  async function handleManualCheckIn(e) {
    e.preventDefault();
    if (!checkInForm.worker_id || !checkInForm.gate_id) {
      setModalError('Please select both a worker and an entry gate.');
      return;
    }
    setModalSaving(true);
    setModalError('');
    try {
      await checkInWorker({
        worker_id: Number(checkInForm.worker_id),
        gate_id: Number(checkInForm.gate_id),
        entry_time: checkInForm.entry_time || undefined,
      });
      setCheckInModal(false);
      await loadData(true);
    } catch (err) {
      setModalError(err.message || 'Failed to record entry.');
    } finally {
      setModalSaving(false);
    }
  }

  return (
    <div className="animate-fadeUp">
      <PageHeader
        eyebrow="REAL-TIME OCCUPANCY"
        title="Workforce Presence"
        subtitle="Live underground workforce density, gate transits, and exit reconciliation."
        right={
          <div className="flex items-center gap-2">
            <button
              onClick={() => loadData(true)}
              className="p-2 rounded-md border border-border text-textSecondary hover:text-text hover:border-safety/40 transition focus-ring"
              title="Refresh attendance records"
              aria-label="Refresh attendance"
            >
              <RefreshCw size={14} className={refreshing ? 'animate-spin text-safety' : ''} />
            </button>
            <Button onClick={openCheckIn}>
              <Plus size={13} /> LOG ENTRY
            </Button>
          </div>
        }
      />

      <FilterBar filters={filters} setFilters={setFilters} gates={gates} />

      {/* KPI Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard
          label="Entered Today"
          value={loading ? '—' : (kpi.enteredToday ?? 0)}
          icon={LogIn}
        />
        <StatCard
          label="Exited Today"
          value={loading ? '—' : (kpi.exitedToday ?? 0)}
          icon={LogOut}
        />
        <StatCard
          label="Currently Underground"
          value={loading ? '—' : (kpi.currentlyUnderground ?? 0)}
          tone="safety"
          icon={Users}
          sub={
            <span className="flex items-center gap-1.5 text-[0.68rem] text-safety font-semibold">
              <StatusDot status="ONLINE" /> LIVE HEADCOUNT
            </span>
          }
        />
        <StatCard
          label="Missing Exit Scans"
          value={loading ? '—' : (kpi.missingExitScans ?? 0)}
          tone="warning"
          icon={AlertTriangle}
          sub={kpi.missingExitScans > 0 ? 'Exceeding shift duration' : 'All exits reconciled'}
        />
      </div>

      {/* Zone Occupancy Headcount */}
      <div className="panel p-5 mb-6">
        <SectionHeader
          title="Underground Density by Zone"
          subtitle="Live worker occupancy per mine shaft and checkpoint location."
        />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {zones.map((z) => (
            <div
              key={z.zone}
              className="panel-elevated p-4 text-center rock-texture relative overflow-hidden group hover:border-safety/40 transition-colors"
            >
              <div className="flex items-center justify-center gap-1 text-textSecondary text-[0.7rem] uppercase tracking-wider font-bold mb-1.5">
                <MapPin size={11} className="text-safety" />
                <span className="truncate">{z.zone}</span>
              </div>
              <div className="text-2xl font-extrabold mono text-safety">
                {z.count}
              </div>
              <div className="text-[0.65rem] text-textMuted mt-1">
                {z.count === 1 ? '1 worker inside' : `${z.count} workers inside`}
              </div>
            </div>
          ))}
          {zones.length === 0 && !loading && (
            <div className="col-span-full py-6 text-center text-xs text-textMuted">
              No active zones reported for this selection.
            </div>
          )}
        </div>
      </div>

      {/* Filters and Search */}
      <div className="flex flex-col gap-3 mb-4 lg:flex-row lg:items-end">
        <label className="block w-full max-w-md flex-1">
          <span className="filter-label">Search Presence Records</span>
          <div className="filter-control-shell">
            <Search size={15} className="filter-control-icon" aria-hidden="true" />
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search name, Employee ID, or zone..."
              className="filter-control pr-9"
              aria-label="Search attendance records"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="filter-control-action"
                aria-label="Clear search"
              >
                <X size={14} />
              </button>
            )}
          </div>
        </label>

        <div className="flex flex-wrap gap-2 lg:pb-px">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setStatusFilter(f)}
              className={`label-op !text-[0.62rem] px-3 py-2 rounded-md border transition-colors ${
                statusFilter === f
                  ? 'border-safety text-safety bg-safetySubtle'
                  : 'border-border text-textSecondary hover:text-text'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Presence Records Table */}
      <div className="panel overflow-hidden">
        <div className="p-4 border-b border-border/60 flex items-center justify-between">
          <SectionHeader
            title="Workforce Transit & Occupancy Logs"
            subtitle={`${filteredRows.length} transit records shown`}
          />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border bg-elevated/40">
                {['Worker', 'Gate & Zone', 'Entry Time', 'Exit / Duration', 'PPE Status', 'Occupancy', 'Action'].map((h) => (
                  <th key={h} className="label-op text-left px-4 py-3 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-textMuted">
                    Loading workforce presence logs...
                  </td>
                </tr>
              )}
              {filteredRows.map((r) => {
                const isUnderground = r.status === 'UNDERGROUND';
                const isActing = actionLoading[r.attendance_id];
                return (
                  <tr
                    key={r.attendance_id}
                    onClick={() => r.workerId && navigate(`/workers/${r.workerId}`)}
                    className="border-b border-border/50 last:border-0 hover:bg-elevated/60 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="flex items-center gap-2.5">
                        <div className={`w-7 h-7 rounded-full border flex items-center justify-center font-bold text-[0.65rem] shrink-0 ${
                          isUnderground
                            ? 'bg-safety/10 border-safety/40 text-safety'
                            : 'bg-elevated border-border text-textMuted'
                        }`}>
                          {r.worker ? r.worker[0]?.toUpperCase() : 'W'}
                        </div>
                        <div>
                          <div className="font-semibold text-text">{r.worker}</div>
                          <div className="mono text-[0.68rem] text-textMuted flex items-center gap-1.5">
                            <span>{r.workerId}</span>
                            <span>·</span>
                            <span>{r.department}</span>
                          </div>
                        </div>
                      </div>
                    </td>

                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="font-medium text-text">{r.gate}</div>
                      <div className="text-[0.68rem] text-textSecondary flex items-center gap-1">
                        <MapPin size={10} className="text-safety" />
                        <span>{r.location}</span>
                      </div>
                    </td>

                    <td className="px-4 py-3 whitespace-nowrap">
                      <div className="mono font-semibold text-text">{formatTime(r.entry)}</div>
                      <div className="mono text-[0.65rem] text-textMuted">{formatDate(r.entry)}</div>
                    </td>

                    <td className="px-4 py-3 whitespace-nowrap">
                      {isUnderground ? (
                        <span className="inline-flex items-center gap-1 mono text-[0.72rem] text-safety font-bold bg-safetySubtle/50 px-2 py-0.5 rounded border border-safetyDark/40">
                          <Clock size={11} /> {calcDuration(r.entry, null)} inside
                        </span>
                      ) : (
                        <div>
                          <div className="mono text-textSecondary">{formatTime(r.exit)}</div>
                          <div className="mono text-[0.65rem] text-textMuted">Duration: {calcDuration(r.entry, r.exit)}</div>
                        </div>
                      )}
                    </td>

                    <td className="px-4 py-3 whitespace-nowrap">
                      <Badge
                        tone={
                          r.ppe === 'VERIFIED'
                            ? 'safety'
                            : r.ppe === 'FLAGGED'
                            ? 'warning'
                            : r.ppe === 'DENIED'
                            ? 'danger'
                            : 'default'
                        }
                      >
                        {r.ppe === 'VERIFIED' && <ShieldCheck size={11} />}
                        {r.ppe}
                      </Badge>
                    </td>

                    <td className="px-4 py-3 whitespace-nowrap">
                      <Badge tone={isUnderground ? 'info' : 'default'}>
                        {isUnderground && <StatusDot status="ONLINE" />}
                        {r.status}
                      </Badge>
                    </td>

                    <td className="px-4 py-3 whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                      {isUnderground ? (
                        <button
                          onClick={(e) => handleCheckOut(r.attendance_id, e)}
                          disabled={isActing}
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded border border-danger/40 bg-danger/5 text-danger hover:bg-danger/15 text-[0.68rem] font-bold uppercase tracking-wider transition focus-ring disabled:opacity-50"
                          title="Record exit time for this worker"
                        >
                          <LogOut size={11} />
                          {isActing ? 'Saving…' : 'Clock Out'}
                        </button>
                      ) : (
                        <span className="text-[0.68rem] text-textMuted flex items-center gap-1">
                          <CheckCircle2 size={12} className="text-textMuted" /> Exited
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
              {!loading && filteredRows.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-textMuted">
                    No workforce presence records match this search.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Manual Check-In Modal */}
      {checkInModal && (
        <div className="fixed inset-0 z-50 bg-bg/80 backdrop-blur flex items-center justify-center px-4">
          <form
            onSubmit={handleManualCheckIn}
            className="panel-elevated w-full max-w-lg p-6 animate-fadeUp relative overflow-hidden rock-texture"
          >
            <div className="flex items-start justify-between gap-4 mb-5">
              <div>
                <div className="label-op text-safety mb-1">MANUAL RECORD</div>
                <h2 className="text-lg font-extrabold tracking-tight">Log Worker Entry</h2>
                <p className="text-xs text-textSecondary mt-0.5">
                  Record checkpoint check-in for a worker currently on duty.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setCheckInModal(false)}
                className="p-1.5 text-textSecondary hover:text-text focus-ring rounded"
              >
                <X size={18} />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block">
                  <div className="label-op mb-1.5">Select Worker</div>
                  <select
                    required
                    value={checkInForm.worker_id}
                    onChange={(e) =>
                      setCheckInForm((prev) => ({ ...prev, worker_id: e.target.value }))
                    }
                    className="field w-full"
                  >
                    <option value="">Choose worker...</option>
                    {workersList.map((w) => (
                      <option key={w.worker_id} value={w.worker_id}>
                        {w.name} ({w.id || w.employee_code}) — {w.department}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div>
                <label className="block">
                  <div className="label-op mb-1.5">Checkpoint Gate</div>
                  <select
                    required
                    value={checkInForm.gate_id}
                    onChange={(e) =>
                      setCheckInForm((prev) => ({ ...prev, gate_id: e.target.value }))
                    }
                    className="field w-full"
                  >
                    <option value="">Choose checkpoint gate...</option>
                    {gates.map((g) => (
                      <option key={g.gate_id} value={g.gate_id}>
                        {g.name} — {g.location}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div>
                <label className="block">
                  <div className="label-op mb-1.5">Entry Date & Time</div>
                  <input
                    type="datetime-local"
                    required
                    value={checkInForm.entry_time}
                    onChange={(e) =>
                      setCheckInForm((prev) => ({ ...prev, entry_time: e.target.value }))
                    }
                    className="field w-full mono text-xs"
                  />
                </label>
              </div>
            </div>

            {modalError && (
              <div
                className="mt-4 rounded-md border border-danger/40 bg-dangerSubtle px-3 py-2.5 text-xs text-danger"
                role="alert"
              >
                {modalError}
              </div>
            )}

            <div className="flex justify-end gap-2 mt-6">
              <Button
                type="button"
                variant="outline"
                onClick={() => setCheckInModal(false)}
              >
                CANCEL
              </Button>
              <Button type="submit" disabled={modalSaving}>
                {modalSaving ? 'SAVING...' : 'CONFIRM ENTRY'}
              </Button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
