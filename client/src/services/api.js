
export const USE_MOCK = false;

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
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
  const headers = {
    ...(!isFormData ? { 'Content-Type': 'application/json' } : {}),
    ...(options.headers || {}),
  };
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let detail = `SURAKSHA API error ${res.status}: ${path}`;
    try {
      const body = await res.json();
      detail = Array.isArray(body.detail)
        ? body.detail.map((issue) => issue?.msg).filter(Boolean).join('; ') || detail
        : body.detail || detail;
    } catch {
    }
    const error = new Error(detail);
    error.status = res.status;
    throw error;
  }

  if (res.status === 204) return null;
  return res.json();
}

export function filterQuery({ period = 'today', date = '', shift = 'ALL', gateId = 'ALL', worker = '' } = {}) {
  const params = new URLSearchParams();
  const selectedDate = period === 'date' && date ? date : (() => { const d = new Date(); if (period === 'yesterday') d.setDate(d.getDate() - 1); return d.toISOString().slice(0, 10); })();
  params.set('date', selectedDate);
  if (shift !== 'ALL') params.set('shift', shift);
  if (gateId !== 'ALL') params.set('gate_id', gateId);
  if (worker.trim()) params.set('worker', worker.trim());
  return `?${params.toString()}`;
}

export function getConnectionState() {
  return typeof navigator !== 'undefined' && navigator.onLine === false ? 'OFFLINE' : 'ONLINE';
}
