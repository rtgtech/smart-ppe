import { apiRequest, filterQuery } from './api';

export function listAlerts(filters) {
  return apiRequest(`/alerts${filterQuery(filters)}`);
}

export function updateAlert(alertId, payload) {
  return apiRequest(`/alerts/${alertId}`, { method: 'PATCH', body: JSON.stringify(payload) });
}
