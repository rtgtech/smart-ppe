import { apiRequest } from './api';

export function listAttendance() {
  return apiRequest('/attendance');
}

export function getZones() {
  return apiRequest('/attendance/zones');
}

export function getAttendanceKpi() {
  return apiRequest('/attendance/kpi');
}
