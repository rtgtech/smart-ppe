import { apiRequest } from './api';

export function getDashboard() {
  return apiRequest('/dashboard');
}
