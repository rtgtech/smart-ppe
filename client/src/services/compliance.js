import { apiRequest } from './api';

export function listCompliance(workerId) {
  const query = workerId ? `?worker_id=${encodeURIComponent(workerId)}` : '';
  return apiRequest(`/compliance${query}`);
}
