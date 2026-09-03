// ============================================================
// SURAKSHA — MOCK DATA
// Structured to mirror the future SQLite-backed API responses.
// Types are documented in src/data/types.js
// ============================================================

export const PPE_ITEMS = [
  { key: 'helmet', label: 'Helmet', compliance: 98, trend: +0.4, violations: 21 },
  { key: 'capLamp', label: 'Cap Lamp', compliance: 96, trend: +0.1, violations: 34 },
  { key: 'safetyBoots', label: 'Safety Boots', compliance: 94, trend: -0.6, violations: 52 },
  { key: 'reflectiveVest', label: 'Reflective Vest', compliance: 97, trend: +0.2, violations: 27 },
  { key: 'gasDetector', label: 'Gas Detector', compliance: 91, trend: -1.4, violations: 68 },
  { key: 'selfRescuer', label: 'Self-Rescuer', compliance: 93, trend: -0.3, violations: 41 },
];

export const GATES = [
  { id: 'G01', name: 'GATE 01', label: 'Main Shaft Entry', status: 'ONLINE', workers: 342, denials: 6 },
  { id: 'G02', name: 'GATE 02', label: 'Shaft Entry', status: 'ONLINE', workers: 291, denials: 11 },
  { id: 'G03', name: 'GATE 03', label: 'Ventilation Shaft', status: 'MAINTENANCE', workers: 0, denials: 0 },
  { id: 'G04', name: 'GATE 04', label: 'Secondary Access', status: 'ONLINE', workers: 101, denials: 6 },
];

export const WORKERS = [
  { id: 'WK10234', name: 'Ramesh Kumar', department: 'Underground Mining', shift: 'A', ppeScore: 92, risk: 'HIGH', status: 'ACTIVE', rfidId: 'RFID-8F31A9', violations: 7, denials: 3, streak: 4 },
  { id: 'WK10211', name: 'Arun Kumar', department: 'Operations', shift: 'A', ppeScore: 99, risk: 'LOW', status: 'ACTIVE', rfidId: 'RFID-2C10B4', violations: 0, denials: 0, streak: 27 },
  { id: 'WK10209', name: 'Sanjay Singh', department: 'Electrical', shift: 'B', ppeScore: 88, risk: 'MEDIUM', status: 'ACTIVE', rfidId: 'RFID-77AE02', violations: 3, denials: 1, streak: 6 },
  { id: 'WK10198', name: 'Vikram Yadav', department: 'Maintenance', shift: 'A', ppeScore: 81, risk: 'HIGH', status: 'ACTIVE', rfidId: 'RFID-441FDD', violations: 9, denials: 4, streak: 1 },
  { id: 'WK10187', name: 'Rahul Sharma', department: 'Mining', shift: 'B', ppeScore: 97, risk: 'LOW', status: 'ACTIVE', rfidId: 'RFID-9B0021', violations: 1, denials: 0, streak: 19 },
  { id: 'WK10176', name: 'Ravi Shankar', department: 'Mining', shift: 'A', ppeScore: 98, risk: 'LOW', status: 'ACTIVE', rfidId: 'RFID-30AC77', violations: 1, denials: 0, streak: 22 },
  { id: 'WK10165', name: 'Deepak Verma', department: 'Transport', shift: 'C', ppeScore: 76, risk: 'HIGH', status: 'ACTIVE', rfidId: 'RFID-55E110', violations: 11, denials: 5, streak: 0 },
  { id: 'WK10154', name: 'Manoj Tiwari', department: 'Electrical', shift: 'B', ppeScore: 90, risk: 'MEDIUM', status: 'ACTIVE', rfidId: 'RFID-1A9F3C', violations: 4, denials: 1, streak: 8 },
  { id: 'WK10143', name: 'Suresh Pal', department: 'Underground Mining', shift: 'A', ppeScore: 85, risk: 'MEDIUM', status: 'ON LEAVE', rfidId: 'RFID-C4402E', violations: 5, denials: 2, streak: 0 },
  { id: 'WK10132', name: 'Vijay Kumar', department: 'Operations', shift: 'C', ppeScore: 98, risk: 'LOW', status: 'ACTIVE', rfidId: 'RFID-8890AB', violations: 0, denials: 0, streak: 30 },
];

export const workerById = (id) => WORKERS.find((w) => w.id === id);

export const RECENT_EVENTS = [
  { time: '10:32:14', worker: 'Ramesh Kumar', workerId: 'WK10234', issue: 'Safety Boots Missing', gate: 'GATE 02', decision: 'ENTRY DENIED', severity: 'critical' },
  { time: '10:28:41', worker: 'Sanjay Singh', workerId: 'WK10209', issue: 'Gas Detector Missing', gate: 'GATE 01', decision: 'ENTRY DENIED', severity: 'critical' },
  { time: '09:47:21', worker: 'Vikram Yadav', workerId: 'WK10198', issue: 'Helmet Missing', gate: 'GATE 03', decision: 'WARNING', severity: 'warning' },
  { time: '09:31:02', worker: 'Deepak Verma', workerId: 'WK10165', issue: 'Self-Rescuer Missing', gate: 'GATE 02', decision: 'ENTRY DENIED', severity: 'critical' },
  { time: '09:12:57', worker: 'Manoj Tiwari', workerId: 'WK10154', issue: 'Reflective Vest Missing', gate: 'GATE 04', decision: 'WARNING', severity: 'warning' },
];

export const PPE_TREND_30D = Array.from({ length: 30 }, (_, i) => {
  const base = 90 + Math.sin(i / 4) * 2.4;
  const drift = i > 20 ? (i - 20) * 0.15 : 0;
  return { day: `D${i + 1}`, compliance: Math.round((base + drift) * 10) / 10 };
});

export const SHIFT_COMPARISON = [
  { shift: 'Shift A', compliance: 95.2, violations: 24 },
  { shift: 'Shift B', compliance: 90.8, violations: 41 },
  { shift: 'Shift C', compliance: 93.1, violations: 21 },
];

export const GATE_VIOLATIONS = GATES.filter((g) => g.status === 'ONLINE').map((g) => ({
  gate: g.name,
  denials: g.denials * 4,
}));

export const MOST_COMMON_VIOLATIONS = [
  { label: 'Gas Detector', pct: 22 },
  { label: 'Safety Boots', pct: 19 },
  { label: 'Self-Rescuer', pct: 14 },
  { label: 'Helmet', pct: 9 },
];

export const ALERTS = [
  { id: 'AL-4471', severity: 'CRITICAL', title: 'PPE Violation', worker: 'Ramesh Kumar', workerId: 'WK10234', detail: 'Safety Boots Missing', gate: 'GATE 02', time: '10:32:14', status: 'OPEN', officer: 'S. Officer Rana' },
  { id: 'AL-4470', severity: 'CRITICAL', title: 'PPE Violation', worker: 'Sanjay Singh', workerId: 'WK10209', detail: 'Gas Detector Missing', gate: 'GATE 01', time: '10:28:41', status: 'OPEN', officer: 'S. Officer Rana' },
  { id: 'AL-4469', severity: 'WARNING', title: 'PPE Violation', worker: 'Vikram Yadav', workerId: 'WK10198', detail: 'Helmet Missing', gate: 'GATE 03', time: '09:47:21', status: 'ACKNOWLEDGED', officer: 'Supervisor Meena' },
  { id: 'AL-4468', severity: 'CRITICAL', title: 'Device Offline', worker: '—', workerId: null, detail: 'RFID-002 lost heartbeat', gate: 'GATE 02', time: '09:41:09', status: 'ESCALATED', officer: 'Admin Console' },
  { id: 'AL-4467', severity: 'WARNING', title: 'PPE Violation', worker: 'Manoj Tiwari', workerId: 'WK10154', detail: 'Reflective Vest Missing', gate: 'GATE 04', time: '09:12:57', status: 'RESOLVED', officer: 'Supervisor Joshi' },
  { id: 'AL-4466', severity: 'RESOLVED', title: 'Missing Exit Scan', worker: 'Rahul Sharma', workerId: 'WK10187', detail: 'No exit RFID scan recorded', gate: 'GATE 01', time: '08:58:03', status: 'RESOLVED', officer: 'Supervisor Joshi' },
];

export const DEVICES = [
  { id: 'CAM-001', type: 'AI CAMERA', gate: 'GATE 01', status: 'ONLINE', heartbeat: '2s ago' },
  { id: 'CAM-002', type: 'AI CAMERA', gate: 'GATE 02', status: 'ONLINE', heartbeat: '1s ago' },
  { id: 'CAM-003', type: 'AI CAMERA', gate: 'GATE 03', status: 'OFFLINE', heartbeat: '4h 12m ago' },
  { id: 'CAM-004', type: 'AI CAMERA', gate: 'GATE 04', status: 'ONLINE', heartbeat: '3s ago' },
  { id: 'RFID-001', type: 'RFID READER', gate: 'GATE 01', status: 'ONLINE', heartbeat: '1s ago' },
  { id: 'RFID-002', type: 'RFID READER', gate: 'GATE 02', status: 'OFFLINE', heartbeat: '2h 04m ago' },
  { id: 'RFID-003', type: 'RFID READER', gate: 'GATE 03', status: 'OFFLINE', heartbeat: '4h 12m ago' },
  { id: 'RFID-004', type: 'RFID READER', gate: 'GATE 04', status: 'ONLINE', heartbeat: '2s ago' },
  { id: 'EDGE-001', type: 'GATE CONTROLLER', gate: 'GATE 01', status: 'ONLINE', heartbeat: '1s ago' },
  { id: 'EDGE-002', type: 'GATE CONTROLLER', gate: 'GATE 02', status: 'ONLINE', heartbeat: '1s ago' },
  { id: 'EDGE-004', type: 'GATE CONTROLLER', gate: 'GATE 04', status: 'ONLINE', heartbeat: '2s ago' },
];

export const SYNC_QUEUE = [
  { id: 'EVT-92831', worker: 'Ramesh Kumar', type: 'PPE verification', status: 'Pending' },
  { id: 'EVT-92830', worker: 'Sanjay Singh', type: 'PPE verification', status: 'Pending' },
  { id: 'EVT-92829', worker: 'Arun Kumar', type: 'Entry event', status: 'Pending' },
  { id: 'EVT-92828', worker: 'Manoj Tiwari', type: 'PPE verification', status: 'Pending' },
];

export const AUDIT_LOG = [
  { time: '10:32:14', eventId: 'EVT-92831', worker: 'Ramesh Kumar', gate: 'G02', decision: 'DENIED', source: 'AI CAMERA' },
  { time: '10:28:41', eventId: 'EVT-92830', worker: 'Sanjay Singh', gate: 'G01', decision: 'DENIED', source: 'AI CAMERA' },
  { time: '10:21:09', eventId: 'EVT-92829', worker: 'Arun Kumar', gate: 'G02', decision: 'ALLOWED', source: 'AI + RFID' },
  { time: '10:15:33', eventId: 'EVT-92828', worker: 'Rahul Sharma', gate: 'G01', decision: 'ALLOWED', source: 'AI + RFID' },
  { time: '09:47:21', eventId: 'EVT-92827', worker: 'Vikram Yadav', gate: 'G03', decision: 'WARNING', source: 'AI CAMERA' },
  { time: '09:31:02', eventId: 'EVT-92826', worker: 'Deepak Verma', gate: 'G02', decision: 'DENIED', source: 'AI CAMERA' },
];

export const CHAMPIONS = [
  { rank: 1, worker: 'Arun Kumar', workerId: 'WK10211', compliance: 99.4, streak: 27 },
  { rank: 2, worker: 'Ravi Shankar', workerId: 'WK10176', compliance: 98.9, streak: 22 },
  { rank: 3, worker: 'Vijay Kumar', workerId: 'WK10132', compliance: 98.1, streak: 30 },
  { rank: 4, worker: 'Rahul Sharma', workerId: 'WK10187', compliance: 97.6, streak: 19 },
  { rank: 5, worker: 'Manoj Tiwari', workerId: 'WK10154', compliance: 95.0, streak: 8 },
];

export const REPORTS = [
  { id: 'RPT-01', name: 'Daily PPE Report', description: 'Verification outcomes for all gates, last 24 hours.', lastGenerated: '30 Aug, 06:00', records: 1248 },
  { id: 'RPT-02', name: 'Weekly Compliance Report', description: 'PPE compliance trend and violations, last 7 days.', lastGenerated: '25 Aug, 06:00', records: 8712 },
  { id: 'RPT-03', name: 'Monthly Safety Report', description: 'Mine-wide safety summary for management review.', lastGenerated: '01 Aug, 06:00', records: 37210 },
  { id: 'RPT-04', name: 'Worker Violation Report', description: 'Per-worker PPE violation history and risk flags.', lastGenerated: '29 Aug, 18:00', records: 412 },
  { id: 'RPT-05', name: 'Gate Performance Report', description: 'Uptime, throughput and denial rates by gate.', lastGenerated: '29 Aug, 18:00', records: 4 },
  { id: 'RPT-06', name: 'Audit Report', description: 'Full decision log for DGMS / regulatory audit.', lastGenerated: '28 Aug, 09:00', records: 92831 },
];

export const RECENT_REPORTS = [
  { name: 'Daily PPE Report — 29 Aug', date: '29 Aug 2026', records: 1204, status: 'READY' },
  { name: 'Gate Performance Report — Week 34', date: '25 Aug 2026', records: 4, status: 'READY' },
  { name: 'Worker Violation Report — Shift B', date: '24 Aug 2026', records: 96, status: 'READY' },
  { name: 'Monthly Safety Report — Jul 2026', date: '01 Aug 2026', records: 33012, status: 'ARCHIVED' },
];

export const USERS = [
  { name: 'A. Deshmukh', role: 'Mine Administrator', mine: 'Central Coal Mine', lastLogin: '30 Aug, 08:12', status: 'ACTIVE' },
  { name: 'S. Officer Rana', role: 'Safety Officer', mine: 'Central Coal Mine', lastLogin: '30 Aug, 10:02', status: 'ACTIVE' },
  { name: 'Supervisor Meena', role: 'Shift Supervisor', mine: 'Central Coal Mine', lastLogin: '30 Aug, 09:55', status: 'ACTIVE' },
  { name: 'Supervisor Joshi', role: 'Shift Supervisor', mine: 'Central Coal Mine', lastLogin: '29 Aug, 22:10', status: 'ACTIVE' },
  { name: 'Gate Op. Chandra', role: 'Gate Operator', mine: 'Central Coal Mine', lastLogin: '30 Aug, 06:01', status: 'ACTIVE' },
  { name: 'Auditor Kulkarni', role: 'Auditor', mine: 'DGMS Regional Office', lastLogin: '20 Aug, 14:40', status: 'INACTIVE' },
];

export const MANDATORY_PPE = [
  { key: 'helmet', label: 'Helmet', state: 'REQUIRED' },
  { key: 'capLamp', label: 'Cap Lamp', state: 'REQUIRED' },
  { key: 'safetyBoots', label: 'Safety Boots', state: 'REQUIRED' },
  { key: 'reflectiveVest', label: 'Reflective Vest', state: 'REQUIRED' },
  { key: 'gasDetector', label: 'Gas Detector', state: 'REQUIRED' },
  { key: 'selfRescuer', label: 'Self-Rescuer', state: 'REQUIRED' },
];

export const ZONES = [
  { zone: 'Zone A', count: 218 },
  { zone: 'Zone B', count: 192 },
  { zone: 'Zone C', count: 176 },
  { zone: 'Zone D', count: 148 },
];

export const ATTENDANCE_ROWS = WORKERS.map((w, i) => ({
  worker: w.name,
  workerId: w.id,
  entry: `0${6 + (i % 3)}:${(10 + i * 3) % 60 < 10 ? '0' : ''}${(10 + i * 3) % 60}`,
  exit: i % 4 === 0 ? '—' : `1${4 + (i % 3)}:${(5 + i * 7) % 60 < 10 ? '0' : ''}${(5 + i * 7) % 60}`,
  ppe: w.ppeScore >= 90 ? 'VERIFIED' : 'FLAGGED',
  location: ZONES[i % ZONES.length].zone,
  status: i % 4 === 0 ? 'UNDERGROUND' : 'SURFACE',
}));

export const KPI = {
  workersUnderground: 734,
  todaysEntries: 1248,
  ppeCompliance: 93.1,
  violations: 86,
  entryDenied: 23,
  highRiskWorkers: 41,
};

export const VERIFICATION_STEPS = [
  { key: 'scan', label: 'SCANNING…' },
  { key: 'face', label: 'FACE DETECTED' },
  { key: 'identity', label: 'IDENTITY VERIFIED' },
  { key: 'rfid', label: 'RFID VERIFIED' },
  { key: 'ppe', label: 'CHECKING PPE…' },
  { key: 'helmet', label: 'HELMET' },
  { key: 'capLamp', label: 'CAP LAMP' },
  { key: 'safetyBoots', label: 'SAFETY BOOTS' },
  { key: 'reflectiveVest', label: 'REFLECTIVE VEST' },
  { key: 'gasDetector', label: 'GAS DETECTOR' },
  { key: 'selfRescuer', label: 'SELF-RESCUER' },
  { key: 'compliance', label: 'COMPLIANCE CHECK' },
  { key: 'decision', label: 'DECISION' },
];

export const VERIFICATION_RESULT = {
  worker: 'Ramesh Kumar',
  workerId: 'WK10234',
  ppe: {
    helmet: true,
    capLamp: true,
    safetyBoots: false,
    reflectiveVest: true,
    gasDetector: true,
    selfRescuer: true,
  },
  aiConfidence: 96.4,
  decision: 'ENTRY DENIED',
  missing: ['Safety Boots'],
};
