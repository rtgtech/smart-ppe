import { apiRequest, filterQuery } from './api';

export function getDashboard(filters) {
  return apiRequest(`/dashboard${filterQuery(filters)}`);
}
