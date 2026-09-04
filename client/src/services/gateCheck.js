import { apiRequest } from './api';

export const createEntryAttempt = (id) => apiRequest('/entry/attempts', { method: 'POST', headers: { 'Idempotency-Key': id } });
export const getEntryAttempt = (id) => apiRequest(`/entry/attempts/${encodeURIComponent(id)}`);
export const discardEntryAttempt = (id) => apiRequest(`/entry/attempts/${encodeURIComponent(id)}`, { method: 'DELETE' });
