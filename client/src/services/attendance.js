import { apiRequest, filterQuery } from './api';

export function listAttendance(filters) {
  return apiRequest(`/attendance${filterQuery(filters)}`);
}

export function getZones(filters) {
  return apiRequest(`/attendance/zones${filterQuery(filters)}`);
}

export function getAttendanceKpi(filters) {
  return apiRequest(`/attendance/kpi${filterQuery(filters)}`);
}
