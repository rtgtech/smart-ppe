import { resolveMock } from './api';
import { GATES, GATE_VIOLATIONS } from '../data/mockData';

export function listGates() {
  return resolveMock(GATES);
}

export function getGateViolations() {
  return resolveMock(GATE_VIOLATIONS);
}
