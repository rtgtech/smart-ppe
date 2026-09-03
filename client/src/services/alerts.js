import { resolveMock } from './api';
import { ALERTS } from '../data/mockData';

export function listAlerts() {
  return resolveMock(ALERTS);
}
