import { apiRequest, filterQuery } from './api';

export function getInsights(filters) {
  return apiRequest(`/insights${filterQuery(filters)}`);
}
