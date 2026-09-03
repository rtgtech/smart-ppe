import { apiRequest } from './api';

export function listGates() {
  return apiRequest('/gates');
}

export function getGateViolations() {
  return apiRequest('/gates/violations');
}
