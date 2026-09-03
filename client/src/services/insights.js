import { apiRequest } from './api';

export function getInsights() {
  return apiRequest('/insights');
}
