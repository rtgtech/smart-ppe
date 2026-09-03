import { apiRequest } from './api';

import { filterQuery } from './api';
export function getPpeSummary(filters) {
  return apiRequest(`/ppe/summary${filterQuery(filters)}`);
}

export function getPpeTrend(filters) {
  return apiRequest(`/ppe/trend${filterQuery(filters)}`);
}

export function getCommonViolations(filters) {
  return apiRequest(`/ppe/violations${filterQuery(filters)}`);
}

export function getMandatoryPpeConfig() {
  return apiRequest('/ppe/config');
}
