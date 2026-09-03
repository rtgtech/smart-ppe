import { resolveMock } from './api';
import { ATTENDANCE_ROWS, ZONES, KPI } from '../data/mockData';

export function listAttendance() {
  return resolveMock(ATTENDANCE_ROWS);
}

export function getZones() {
  return resolveMock(ZONES);
}

export function getAttendanceKpi() {
  return resolveMock({
    enteredToday: KPI.todaysEntries,
    exitedToday: 514,
    currentlyUnderground: KPI.workersUnderground,
    missingExitScans: 17,
  });
}
