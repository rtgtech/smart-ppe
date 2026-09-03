import { apiRequest } from './api';

export function getPpeSummary() {
  return apiRequest('/ppe/summary');
}

export function getPpeTrend() {
  return apiRequest('/ppe/trend');
}

export function getCommonViolations() {
  return apiRequest('/ppe/violations');
}

export function getMandatoryPpeConfig() {
  return apiRequest('/ppe/config');
}
