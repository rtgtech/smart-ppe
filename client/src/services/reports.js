import { apiRequest, filterQuery } from './api';

export function listReports(filters) {
  return apiRequest(`/reports${filterQuery(filters)}`);
}

export function listRecentReports() {
  return apiRequest('/reports');
}
