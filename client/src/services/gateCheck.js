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

export function getGateContext(employeeCode) {
  return apiRequest(`/gate-checks/context/${encodeURIComponent(employeeCode)}`);
}

export function resolvePpeItem(employeeCode, itemId) {
  return apiRequest(`/gate-checks/resolve-item/${encodeURIComponent(employeeCode)}?item_id=${encodeURIComponent(itemId)}`);
}

export function completeGateCheck(payload) {
  return apiRequest('/gate-checks/complete', { method: 'POST', body: JSON.stringify(payload) });
}
