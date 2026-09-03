import { resolveMock } from './api';
import { PPE_ITEMS, PPE_TREND_30D, MOST_COMMON_VIOLATIONS, MANDATORY_PPE } from '../data/mockData';

export function getPpeSummary() {
  return resolveMock(PPE_ITEMS);
}

export function getPpeTrend() {
  return resolveMock(PPE_TREND_30D);
}

export function getCommonViolations() {
  return resolveMock(MOST_COMMON_VIOLATIONS);
}

export function getMandatoryPpeConfig() {
  return resolveMock(MANDATORY_PPE);
}
