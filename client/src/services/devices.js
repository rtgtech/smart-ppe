import { resolveMock } from './api';
import { DEVICES, SYNC_QUEUE } from '../data/mockData';

export function listDevices() {
  return resolveMock(DEVICES);
}

export function getSyncQueue() {
  return resolveMock(SYNC_QUEUE);
}
