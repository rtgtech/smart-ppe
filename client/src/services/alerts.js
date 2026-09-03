import { apiRequest } from './api';

export function listAlerts() {
  return apiRequest('/alerts');
}

export function updateAlert(alertId, payload) {
  return apiRequest(`/alerts/${alertId}`, { method: 'PATCH', body: JSON.stringify(payload) });
}
