import { apiRequest } from './api';

const SESSION_KEY = 'suraksha_gate_session';

export function readGateSession() {
  try {
    return JSON.parse(sessionStorage.getItem(SESSION_KEY) || '{}');
  } catch {
    return {};
  }
}

export function writeGateSession(update) {
  const next = { ...readGateSession(), ...update };
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(next));
  return next;
}

export function resetGateSession() {
  sessionStorage.removeItem(SESSION_KEY);
}

export function createEntryAttempt(idempotencyKey) {
  return apiRequest('/entry/attempts', { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey } });
}

export function getEntryAttempt(eventId) {
  return apiRequest(`/entry/attempts/${encodeURIComponent(eventId)}`);
}

export function finalizeEntryAttempt(eventId) {
  return apiRequest(`/entry/attempts/${encodeURIComponent(eventId)}/finalize`, { method: 'POST' });
}

export function resetEntrySession() {
  sessionStorage.removeItem(SESSION_KEY);
}
