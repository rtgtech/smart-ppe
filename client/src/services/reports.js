import { resolveMock } from './api';
import { REPORTS, RECENT_REPORTS } from '../data/mockData';

export function listReports() {
  return resolveMock(REPORTS);
}

export function listRecentReports() {
  return resolveMock(RECENT_REPORTS);
}
