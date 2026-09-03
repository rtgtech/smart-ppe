
export const USE_MOCK = true;

export const BASE_URL = import.meta.env?.VITE_SURAKSHA_API_URL || '/api/v1';

export function resolveMock(value, delay = 220) {
  return new Promise((resolve) => setTimeout(() => resolve(value), delay));
}


export async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) throw new Error(`SURAKSHA API error ${res.status}: ${path}`);
  return res.json();
}

export async function apiRequest(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });

  if (!res.ok) {
    let detail = `SURAKSHA API error ${res.status}: ${path}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
    }
    throw new Error(detail);
  }

  if (res.status === 204) return null;
  return res.json();
}

export function getConnectionState() {
  return typeof navigator !== 'undefined' && navigator.onLine === false ? 'OFFLINE' : 'ONLINE';
}
