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

export function checkInWorker(data) {
  return apiRequest('/attendance/check-in', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function checkOutWorker(attendanceId) {
  return apiRequest(`/attendance/${attendanceId}/checkout`, {
    method: 'POST',
  });
}

export function deleteAttendance(attendanceId) {
  return apiRequest(`/attendance/${attendanceId}`, {
    method: 'DELETE',
  });
}
