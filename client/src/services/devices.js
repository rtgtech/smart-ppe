import { apiRequest } from './api';

export function listDevices() {
  return apiRequest('/devices');
}

export function getSyncQueue() {
  return apiRequest('/entry/sync/status');
}
