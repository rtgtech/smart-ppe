import { apiRequest } from './api';

export function listChampions() {
  return apiRequest('/champions');
}
