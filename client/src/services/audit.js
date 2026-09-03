import { apiRequest } from './api';

export function listAudit() {
  return apiRequest('/audit');
}
