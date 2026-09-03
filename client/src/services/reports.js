import { apiRequest } from './api';

export function listReports() {
  return apiRequest('/reports');
}

export function listRecentReports() {
  return apiRequest('/reports');
}
