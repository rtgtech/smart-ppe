import { useEffect, useMemo, useState } from 'react';
import {
  FileText,
  Download,
  Calendar,
  CalendarDays,
  User,
  Users,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ShieldCheck,
  Search,
  FileCheck2,
  ChevronDown,
} from 'lucide-react';
import { PageHeader, SectionHeader, Badge, StatCard } from '../components/ui';
import {
  listReports,
  downloadEmployeeReportPdf,
  downloadAllEmployeesReportPdf,
  downloadReportFile,
} from '../services/reports';
import { listGates } from '../services/gates';
import { listWorkers } from '../services/workers';
import { FilterBar } from '../components/DataFilters';
import { DEFAULT_FILTERS, getTodayString } from '../data/filters';

export default function Reports() {
  const [reports, setReports] = useState([]);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [gates, setGates] = useState([]);
  const [workers, setWorkers] = useState([]);

  // Report Generation State
  const [period, setPeriod] = useState('WEEKLY'); // 'WEEKLY' | 'MONTHLY'
  const [scope, setScope] = useState('INDIVIDUAL'); // 'INDIVIDUAL' | 'ALL'
  const [selectedWorkerId, setSelectedWorkerId] = useState('');
  const [reportDate, setReportDate] = useState(filters.date || getTodayString());
  const [reportMonth, setReportMonth] = useState((filters.date || getTodayString()).slice(0, 7));
  const [selectedGateId, setSelectedGateId] = useState('ALL');
  const [selectedShift, setSelectedShift] = useState('ALL');
  const [isGenerating, setIsGenerating] = useState(false);
  const [downloadingReportId, setDownloadingReportId] = useState(null);
  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [tableSearch, setTableSearch] = useState('');
  const [isArchiveOpen, setIsArchiveOpen] = useState(true);

  useEffect(() => {
    listGates().then(setGates).catch(() => {});
    listWorkers().then((list) => {
      setWorkers(list || []);
      if (list && list.length > 0) {
        setSelectedWorkerId(list[0].worker_id || list[0].id);
      }
    }).catch(() => {});
  }, []);

  const loadReports = useMemo(() => () => {
    listReports(filters).then(setReports).catch(() => setReports([]));
  }, [filters]);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  const selectedWorker = useMemo(() => {
    return workers.find((w) => String(w.worker_id || w.id) === String(selectedWorkerId)) || workers[0];
  }, [workers, selectedWorkerId]);

  const previewDateRange = useMemo(() => {
    try {
      if (period === 'WEEKLY') {
        const endD = reportDate || getTodayString();
        const parts = endD.split('-').map(Number);
        const d = new Date(parts[0], parts[1] - 1, parts[2]);
        const start = new Date(d);
        start.setDate(start.getDate() - 6);
        const formatDate = (dateObj) =>
          dateObj.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
        return `${formatDate(start)} – ${formatDate(d)}`;
      }
      const [year, month] = (reportMonth || getTodayString().slice(0, 7)).split('-').map(Number);
      const lastDay = new Date(year, month, 0).getDate();
      const d = new Date(year, month - 1, 1);
      const monthName = d.toLocaleDateString('en-GB', { month: 'short', year: 'numeric' });
      return `01 ${monthName} – ${lastDay} ${monthName}`;
    } catch {
      return reportDate || getTodayString();
    }
  }, [period, reportDate, reportMonth]);

  const buttonLabel = useMemo(() => {
    if (scope === 'INDIVIDUAL') {
      return period === 'WEEKLY' ? 'Compile & Download Weekly Employee PDF' : 'Compile & Download Monthly Employee PDF';
    }
    return period === 'WEEKLY' ? 'Compile & Download Weekly Workforce PDF' : 'Compile & Download Monthly Workforce PDF';
  }, [scope, period]);

  const handleGeneratePdf = async () => {
    setIsGenerating(true);
    setErrorMsg('');
    setSuccessMsg('');
    try {
      let downloadedFilename = '';
      if (scope === 'INDIVIDUAL') {
        if (!selectedWorkerId) throw new Error('Please select an employee');
        downloadedFilename = await downloadEmployeeReportPdf({
          workerId: selectedWorkerId,
          period,
          date: reportDate,
          month: reportMonth,
          shift: selectedShift !== 'ALL' ? selectedShift : filters.shift,
          gateId: selectedGateId !== 'ALL' ? selectedGateId : filters.gateId,
        });
      } else {
        downloadedFilename = await downloadAllEmployeesReportPdf({
          period,
          date: reportDate,
          month: reportMonth,
          shift: selectedShift !== 'ALL' ? selectedShift : filters.shift,
          gateId: selectedGateId !== 'ALL' ? selectedGateId : filters.gateId,
        });
      }
      setSuccessMsg(`Report "${downloadedFilename}" successfully generated and saved to database.`);
      loadReports();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to generate PDF report.');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleTableDownload = async (report) => {
    const reportKey = report.report_id || report.id;
    setDownloadingReportId(reportKey);
    setErrorMsg('');
    setSuccessMsg('');
    try {
      const filename = await downloadReportFile(
        report.download_url,
        report.file_url || `${report.name || 'SURAKSHA_Report'}.pdf`
      );
      setSuccessMsg(`Downloaded "${filename}".`);
    } catch (err) {
      setErrorMsg(err.message || 'Failed to download report PDF.');
    } finally {
      setDownloadingReportId(null);
    }
  };

  const totalAuditedRecords = useMemo(() => {
    return reports.reduce((acc, r) => acc + (Number(r.records) || 0), 0);
  }, [reports]);

  const filteredReports = useMemo(() => {
    if (!tableSearch.trim()) return reports;
    const term = tableSearch.toLowerCase();
    return reports.filter(
      (r) =>
        (r.name && r.name.toLowerCase().includes(term)) ||
        (r.id && r.id.toLowerCase().includes(term)) ||
        (r.target && r.target.toLowerCase().includes(term)) ||
        (r.scope && r.scope.toLowerCase().includes(term)) ||
        (r.period_label && r.period_label.toLowerCase().includes(term))
    );
  }, [reports, tableSearch]);

  return (
    <div className="animate-fadeUp space-y-8">
      {/* PAGE HEADER */}
      <PageHeader
        eyebrow="DGMS & MSHA COMPLIANCE"
        title="Safety Reports"
        subtitle="Generate, inspect, and export audit-ready safety reports from real mine operational data."
      />

      {/* SAFETY REPORT STUDIO */}
      <section className="panel overflow-hidden rock-texture border border-border/80 shadow-2xl relative">
        <div className="absolute top-0 right-0 w-96 h-96 bg-safety/5 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />

        {/* Studio Header Bar */}
        <div className="p-5 pb-4 border-b border-border/60 flex items-center justify-between flex-wrap gap-3 bg-surface/60">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-safetySubtle border border-safetyDark/50 flex items-center justify-center text-safety shadow-sm">
              <FileCheck2 size={20} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-bold text-sm uppercase tracking-wider text-text">Safety Report Studio</h2>
                <span className="w-2 h-2 rounded-full bg-safety animate-pulse" />
              </div>
              <p className="text-xs text-textSecondary mt-0.5">
                Compile certified DGMS &amp; MSHA audit dossiers from real operational records
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge tone="safety">A4 Vector PDF</Badge>
            <Badge tone="default">DGMS &amp; MSHA Audit-Ready</Badge>
          </div>
        </div>

        {/* Studio Body: 2-Column Responsive Grid */}
        <div className="p-5 sm:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6 relative z-10">
          {/* Left Column: Interactive Parameters (7 cols on lg) */}
          <div className="lg:col-span-7 flex flex-col gap-5">
            {/* 1. Cadence / Period Selection */}
            <div>
              <label className="filter-label mb-2 flex items-center justify-between">
                <span>1. Select Cadence / Period</span>
                <span className="text-[0.68rem] text-textMuted font-normal lowercase">Time-series audit window</span>
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setPeriod('WEEKLY')}
                  className={`p-3.5 rounded-lg border text-left transition-all flex items-start gap-3 focus-ring ${
                    period === 'WEEKLY'
                      ? 'bg-safetySubtle/70 border-safety text-text shadow-md shadow-safety/5'
                      : 'bg-input/60 border-border/70 hover:border-border hover:bg-input text-textSecondary'
                  }`}
                >
                  <div className={`p-2 rounded-md ${period === 'WEEKLY' ? 'bg-safety text-onSafety' : 'bg-elevated text-textMuted'}`}>
                    <CalendarDays size={16} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-bold text-text flex items-center justify-between">
                      <span>Weekly Audit</span>
                      {period === 'WEEKLY' && <CheckCircle2 size={14} className="text-safety" />}
                    </div>
                    <p className="text-[0.7rem] text-textSecondary mt-1 leading-relaxed">
                      7-day rolling window with day-by-day attendance &amp; PPE matrix
                    </p>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => setPeriod('MONTHLY')}
                  className={`p-3.5 rounded-lg border text-left transition-all flex items-start gap-3 focus-ring ${
                    period === 'MONTHLY'
                      ? 'bg-safetySubtle/70 border-safety text-text shadow-md shadow-safety/5'
                      : 'bg-input/60 border-border/70 hover:border-border hover:bg-input text-textSecondary'
                  }`}
                >
                  <div className={`p-2 rounded-md ${period === 'MONTHLY' ? 'bg-safety text-onSafety' : 'bg-elevated text-textMuted'}`}>
                    <Calendar size={16} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-bold text-text flex items-center justify-between">
                      <span>Monthly Audit</span>
                      {period === 'MONTHLY' && <CheckCircle2 size={14} className="text-safety" />}
                    </div>
                    <p className="text-[0.7rem] text-textSecondary mt-1 leading-relaxed">
                      Full calendar month comprehensive safety dossier &amp; score
                    </p>
                  </div>
                </button>
              </div>
            </div>

            {/* 2. Audit Scope */}
            <div>
              <label className="filter-label mb-2 flex items-center justify-between">
                <span>2. Select Audit Scope</span>
                <span className="text-[0.68rem] text-textMuted font-normal lowercase">Target personnel hierarchy</span>
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setScope('INDIVIDUAL')}
                  className={`p-3.5 rounded-lg border text-left transition-all flex items-start gap-3 focus-ring ${
                    scope === 'INDIVIDUAL'
                      ? 'bg-safetySubtle/70 border-safety text-text shadow-md shadow-safety/5'
                      : 'bg-input/60 border-border/70 hover:border-border hover:bg-input text-textSecondary'
                  }`}
                >
                  <div className={`p-2 rounded-md ${scope === 'INDIVIDUAL' ? 'bg-safety text-onSafety' : 'bg-elevated text-textMuted'}`}>
                    <User size={16} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-bold text-text flex items-center justify-between">
                      <span>Individual Employee</span>
                      {scope === 'INDIVIDUAL' && <CheckCircle2 size={14} className="text-safety" />}
                    </div>
                    <p className="text-[0.7rem] text-textSecondary mt-1 leading-relaxed">
                      Single worker dossier, PPE breakdown &amp; corrective actions
                    </p>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => setScope('ALL')}
                  className={`p-3.5 rounded-lg border text-left transition-all flex items-start gap-3 focus-ring ${
                    scope === 'ALL'
                      ? 'bg-safetySubtle/70 border-safety text-text shadow-md shadow-safety/5'
                      : 'bg-input/60 border-border/70 hover:border-border hover:bg-input text-textSecondary'
                  }`}
                >
                  <div className={`p-2 rounded-md ${scope === 'ALL' ? 'bg-safety text-onSafety' : 'bg-elevated text-textMuted'}`}>
                    <Users size={16} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-bold text-text flex items-center justify-between">
                      <span>All Employees</span>
                      {scope === 'ALL' && <CheckCircle2 size={14} className="text-safety" />}
                    </div>
                    <p className="text-[0.7rem] text-textSecondary mt-1 leading-relaxed">
                      Mine-wide workforce safety roster &amp; priority risk ranking
                    </p>
                  </div>
                </button>
              </div>
            </div>

            {/* 3. Parameter Controls (Date & Worker/Gate) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
              {/* Date Selector */}
              <div>
                <label className="filter-label mb-1.5 block">
                  {period === 'WEEKLY' ? 'Reference Date (Week Ending)' : 'Calendar Month'}
                </label>
                <div className="filter-control-shell">
                  {period === 'WEEKLY' ? (
                    <>
                      <CalendarDays size={15} className="filter-control-icon text-safety pointer-events-none" />
                      <input
                        type="date"
                        value={reportDate}
                        onChange={(e) => setReportDate(e.target.value)}
                        className="filter-control cursor-pointer mono text-xs font-semibold pl-9 pr-3"
                        aria-label="Select report week ending date"
                      />
                    </>
                  ) : (
                    <>
                      <Calendar size={15} className="filter-control-icon text-safety pointer-events-none" />
                      <input
                        type="month"
                        value={reportMonth}
                        onChange={(e) => setReportMonth(e.target.value)}
                        className="filter-control cursor-pointer mono text-xs font-semibold pl-9 pr-3"
                        aria-label="Select report calendar month"
                      />
                    </>
                  )}
                </div>
              </div>

              {/* Worker or Gate Selector */}
              <div>
                <label className="filter-label mb-1.5 block">
                  {scope === 'INDIVIDUAL' ? 'Select Worker' : 'Mine Checkpoint Gate'}
                </label>
                <div className="filter-control-shell">
                  {scope === 'INDIVIDUAL' ? (
                    <>
                      <User size={15} className="filter-control-icon text-safety pointer-events-none" />
                      <select
                        value={selectedWorkerId}
                        onChange={(e) => setSelectedWorkerId(e.target.value)}
                        className="filter-control pl-9 pr-8 text-xs font-medium cursor-pointer"
                        aria-label="Select worker for individual report"
                      >
                        {workers.map((w) => (
                          <option key={w.worker_id || w.id} value={w.worker_id || w.id} className="bg-surface text-text">
                            {w.employee_code || w.id} — {w.name} ({w.department || 'Operations'})
                          </option>
                        ))}
                      </select>
                    </>
                  ) : (
                    <>
                      <ShieldCheck size={15} className="filter-control-icon text-safety pointer-events-none" />
                      <select
                        value={selectedGateId}
                        onChange={(e) => setSelectedGateId(e.target.value)}
                        className="filter-control pl-9 pr-8 text-xs font-medium cursor-pointer"
                        aria-label="Select checkpoint gate"
                      >
                        <option value="ALL" className="bg-surface text-text">All Mine Checkpoints</option>
                        {gates.map((g) => (
                          <option key={g.gate_id || g.id} value={g.gate_id || g.id} className="bg-surface text-text">
                            {g.name}
                          </option>
                        ))}
                      </select>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Optional Shift Filter */}
            <div>
              <label className="filter-label mb-1.5 block">Shift Filter (Optional)</label>
              <div className="flex rounded-md border border-border p-0.5 bg-input max-w-sm">
                {['ALL', 'A', 'B', 'C'].map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setSelectedShift(s)}
                    className={`flex-1 py-1 text-xs font-bold rounded transition focus-ring ${
                      selectedShift === s ? 'bg-safety text-onSafety shadow-sm' : 'text-textSecondary hover:text-text'
                    }`}
                  >
                    {s === 'ALL' ? 'All Shifts' : `Shift ${s}`}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Right Column: Live Dossier Specification & Generate Action (5 cols on lg) */}
          <div className="lg:col-span-5">
            <div className="panel-elevated p-5 rounded-xl border border-border/80 flex flex-col justify-between h-full bg-surface/90 relative overflow-hidden shadow-lg">
              {/* Glow accent */}
              <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-safety/40 via-safety to-safety/40 opacity-80" />

              <div>
                <div className="flex items-center justify-between pb-3 mb-3 border-b border-border/60">
                  <span className="mono text-[0.68rem] text-textMuted uppercase font-bold tracking-wider">
                    Document Specification
                  </span>
                  <span className="inline-flex items-center gap-1.5 text-[0.68rem] font-semibold text-safety bg-safetySubtle/80 px-2.5 py-0.5 rounded-full border border-safetyDark/50">
                    <span className="w-1.5 h-1.5 rounded-full bg-safety animate-pulse" />
                    Live Manifest
                  </span>
                </div>

                {/* Dossier Preview Header */}
                <div className="mb-4">
                  <div className="text-sm font-bold text-text tracking-wide">
                    {scope === 'INDIVIDUAL'
                      ? `${period === 'WEEKLY' ? 'Weekly' : 'Monthly'} Employee Safety Audit`
                      : `${period === 'WEEKLY' ? 'Weekly' : 'Monthly'} Workforce Safety Roster`}
                  </div>
                  <div className="text-xs text-textSecondary mt-1">
                    {scope === 'INDIVIDUAL' && selectedWorker ? (
                      <span className="text-text font-medium">
                        {selectedWorker.name} ({selectedWorker.employee_code}) • {selectedWorker.department || 'Mining'}
                      </span>
                    ) : (
                      <span>Mine-Wide Operational Workforce ({workers.length} Registered Personnel)</span>
                    )}
                  </div>
                </div>

                {/* Key Specs List */}
                <div className="space-y-2.5 text-xs mb-6 bg-input/40 p-3.5 rounded-lg border border-border/50">
                  <div className="flex items-center justify-between py-1 border-b border-border/40 text-[0.72rem]">
                    <span className="text-textSecondary">Audit Window</span>
                    <span className="font-semibold mono text-text">{previewDateRange}</span>
                  </div>
                  <div className="flex items-center justify-between py-1 border-b border-border/40 text-[0.72rem]">
                    <span className="text-textSecondary">Target Hierarchy</span>
                    <span className="font-semibold text-text">
                      {scope === 'INDIVIDUAL' ? 'Individual Personnel Dossier' : 'Workforce Aggregate'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between py-1 border-b border-border/40 text-[0.72rem]">
                    <span className="text-textSecondary">Regulatory Coverage</span>
                    <span className="font-semibold text-safety">DGMS &amp; MSHA Standards</span>
                  </div>
                  <div className="flex items-center justify-between py-1 border-b border-border/40 text-[0.72rem]">
                    <span className="text-textSecondary">Document Engine</span>
                    <span className="font-semibold text-text">ReportLab Two-Pass Vector</span>
                  </div>
                  <div className="flex items-center justify-between py-1 text-[0.72rem]">
                    <span className="text-textSecondary">Security &amp; Audit</span>
                    <span className="font-semibold mono text-textSecondary">Tamper-Evident SHA-256</span>
                  </div>
                </div>
              </div>

              {/* Feedback Messages & Button */}
              <div>
                {successMsg && (
                  <div className="mb-3 px-3.5 py-2.5 rounded-lg border border-safety/40 bg-safetySubtle text-safety text-xs flex items-center gap-2 animate-fadeIn">
                    <CheckCircle2 size={15} className="flex-shrink-0" />
                    <span className="truncate">{successMsg}</span>
                  </div>
                )}
                {errorMsg && (
                  <div className="mb-3 px-3.5 py-2.5 rounded-lg border border-danger/40 bg-dangerSubtle text-danger text-xs flex items-center gap-2 animate-fadeIn">
                    <AlertCircle size={15} className="flex-shrink-0" />
                    <span className="truncate">{errorMsg}</span>
                  </div>
                )}

                <button
                  type="button"
                  onClick={handleGeneratePdf}
                  disabled={isGenerating || (scope === 'INDIVIDUAL' && !selectedWorkerId)}
                  className="w-full py-3.5 px-4 rounded-lg bg-safety text-onSafety font-bold text-xs uppercase tracking-wider hover:brightness-110 active:scale-[0.99] transition-all flex items-center justify-center gap-2 shadow-lg shadow-safety/15 focus-ring disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  {isGenerating ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      <span>Compiling Audit Dossier...</span>
                    </>
                  ) : (
                    <>
                      <Download size={16} />
                      <span>{buttonLabel}</span>
                    </>
                  )}
                </button>
                <p className="text-center mt-2.5 text-[0.68rem] text-textMuted">
                  Automatically logged to audit trail &amp; persisted in SQLite database
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* REAL DB SUMMARY STATS */}
      <section>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Total Reports in DB"
            value={reports.length}
            sub="Archived & ready for audit"
            tone="info"
            icon={FileText}
          />
          <StatCard
            label="Monitored Workforce"
            value={workers.length}
            sub="Employees in safety system"
            tone="safety"
            icon={Users}
          />
          <StatCard
            label="Audited Records"
            value={totalAuditedRecords.toLocaleString()}
            sub="Compliance logs analyzed"
            tone="default"
            icon={ShieldCheck}
          />
          <StatCard
            label="Compliance Standard"
            value="DGMS / MSHA"
            sub="100% Audit verification"
            tone="safety"
            icon={CheckCircle2}
          />
        </div>
      </section>

      {/* DATABASE REPORTS ARCHIVE - ACCORDION / DROPDOWN SECTION */}
      <section className="space-y-4">
        {/* FilterBar explicitly dedicated to the Archive */}
        <FilterBar filters={filters} setFilters={setFilters} gates={gates} />

        <div className="panel overflow-hidden border border-border/70 shadow-lg">
          {/* Collapsible / Dropdown Header */}
          <div
            className="p-5 pb-4 border-b border-border/60 flex flex-col md:flex-row md:items-center justify-between gap-4 bg-surface/80 cursor-pointer select-none hover:bg-elevated/40 transition-colors"
            onClick={() => setIsArchiveOpen(!isArchiveOpen)}
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded bg-safetySubtle/70 border border-safetyDark/40 flex items-center justify-center text-safety">
                <FileText size={16} />
              </div>
              <div>
                <SectionHeader
                  title="Database Reports Archive"
                  subtitle={`Showing ${filteredReports.length} ${filteredReports.length === 1 ? 'report' : 'reports'} persisted in SQLite database`}
                />
              </div>
            </div>

            <div className="flex items-center gap-3" onClick={(e) => e.stopPropagation()}>
              <div className="relative w-full md:w-72">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-textMuted pointer-events-none" />
                <input
                  type="text"
                  placeholder="Search reports by worker, ID..."
                  value={tableSearch}
                  onChange={(e) => setTableSearch(e.target.value)}
                  className="filter-control pl-8 pr-3 py-1.5 text-xs w-full"
                />
              </div>

              {/* Dropdown / Collapse Arrow Toggle */}
              <button
                type="button"
                onClick={() => setIsArchiveOpen(!isArchiveOpen)}
                className="p-2 rounded-lg bg-input hover:bg-elevated border border-border text-textSecondary hover:text-text transition-all focus-ring flex items-center justify-center"
                title={isArchiveOpen ? 'Collapse Archive' : 'Expand Archive'}
                aria-label="Toggle Database Reports Archive"
              >
                <ChevronDown
                  size={18}
                  className={`text-safety transition-transform duration-300 ${isArchiveOpen ? 'rotate-180' : ''}`}
                />
              </button>
            </div>
          </div>

          {/* Collapsible Body */}
          {isArchiveOpen && (
            <div className="overflow-x-auto animate-fadeIn">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border bg-input/40">
                    <th className="label-op text-left px-4 py-3">Report ID</th>
                    <th className="label-op text-left px-4 py-3">Report Title &amp; Scope</th>
                    <th className="label-op text-left px-4 py-3">Audit Period</th>
                    <th className="label-op text-left px-4 py-3">Records</th>
                    <th className="label-op text-left px-4 py-3">Generated At</th>
                    <th className="label-op text-left px-4 py-3">Status</th>
                    <th className="label-op text-right px-4 py-3">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredReports.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="text-center py-12 text-textSecondary">
                        <FileText size={32} className="mx-auto mb-2 text-textMuted opacity-50" />
                        <p className="font-semibold text-sm">No safety reports found</p>
                        <p className="text-xs text-textMuted mt-1">
                          {tableSearch ? 'No reports match your search query.' : 'Use the generator above to create an audit-ready PDF report.'}
                        </p>
                      </td>
                    </tr>
                  ) : (
                    filteredReports.map((r) => {
                      const reportKey = r.report_id || r.id;
                      const isDownloadingThis = downloadingReportId === reportKey;
                      return (
                        <tr key={reportKey} className="border-b border-border/50 last:border-0 hover:bg-elevated/50 transition-colors">
                          <td className="px-4 py-3">
                            <span className="mono text-[0.72rem] font-bold text-safety bg-safetySubtle/50 px-2 py-0.5 rounded border border-safetyDark/40">
                              {r.id || `RPT-${r.report_id}`}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <div className="font-semibold text-text flex items-center gap-1.5">
                              <FileText size={13} className="text-safety flex-shrink-0" />
                              <span>{r.name}</span>
                            </div>
                            <div className="text-[0.68rem] text-textMuted mt-0.5 flex items-center gap-2">
                              <span className="text-textSecondary font-medium">{r.scope || 'Workforce'}</span>
                              {r.target && <span>• {r.target}</span>}
                            </div>
                          </td>
                          <td className="px-4 py-3 text-textSecondary mono text-[0.72rem]">
                            <div className="flex items-center gap-1.5">
                              <CalendarDays size={12} className="text-textMuted" />
                              <span>{r.period_label || r.date}</span>
                            </div>
                          </td>
                          <td className="px-4 py-3 mono font-semibold">
                            <span className="text-text">{Number(r.records || 0).toLocaleString()}</span>
                            <span className="text-textMuted text-[0.68rem] ml-1">logs</span>
                          </td>
                          <td className="px-4 py-3 text-textMuted mono text-[0.72rem]">
                            {r.lastGenerated || '—'}
                          </td>
                          <td className="px-4 py-3">
                            <Badge tone={r.status === 'READY' ? 'safety' : 'default'}>{r.status || 'READY'}</Badge>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <button
                              type="button"
                              onClick={() => handleTableDownload(r)}
                              disabled={isDownloadingThis}
                              className="px-3 py-1.5 rounded-md bg-safety text-onSafety text-[0.7rem] font-bold uppercase tracking-wide hover:brightness-110 transition inline-flex items-center gap-1.5 focus-ring disabled:opacity-50 shadow-sm cursor-pointer"
                              title="Download PDF"
                            >
                              {isDownloadingThis ? (
                                <Loader2 size={12} className="animate-spin" />
                              ) : (
                                <Download size={12} />
                              )}
                              <span>Download PDF</span>
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
