import { apiRequest } from './api';

export function listWorkers() {
  return apiRequest('/workers');
}

export function getWorker(id) {
  const value = String(id);
  const path = /^\d+$/.test(value) ? `/workers/${value}` : `/workers/by-code/${encodeURIComponent(value)}`;
  return apiRequest(path);
}

export function listWorkerDepartments() {
  return apiRequest('/workers/departments');
}

export function createWorker(payload) {
  return apiRequest('/workers', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function createWorkerWithFace(payload, images) {
  const form = new FormData();
  form.append('worker', JSON.stringify(payload));
  images.forEach((image, index) => {
    form.append('images', image, `${payload.employee_code}-face-${index + 1}.jpg`);
  });
  return apiRequest('/workers/with-face', {
    method: 'POST',
    body: form,
  });
}

export function updateWorker(workerId, payload) {
  return apiRequest(`/workers/${workerId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function deleteWorker(workerId) {
  return apiRequest(`/workers/${workerId}`, {
    method: 'DELETE',
  });
}
