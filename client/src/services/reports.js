import { apiRequest, filterQuery, BASE_URL } from './api';

export function listReports(filters) {
  return apiRequest(`/reports${filterQuery(filters)}`);
}

export function listRecentReports() {
  return apiRequest('/reports');
}

export async function downloadReportFile(url, fallbackFilename = 'SURAKSHA_Report.pdf') {
  const fullUrl = url.startsWith('http') ? url : `${BASE_URL}${url}`;
  const response = await fetch(fullUrl);
  if (!response.ok) {
    let errMsg = `Failed to generate report (HTTP ${response.status})`;
    try {
      const errJson = await response.json();
      if (errJson?.detail) errMsg = errJson.detail;
    } catch {
      // ignore
    }
    throw new Error(errMsg);
  }

  const blob = await response.blob();
  let filename = fallbackFilename;
  const disposition = response.headers.get('content-disposition');
  if (disposition && disposition.includes('filename=')) {
    const match = disposition.match(/filename=["']?([^"';]+)["']?/i);
    if (match && match[1]) {
      filename = match[1].trim();
    }
  }

  const blobUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(blobUrl);
  return filename;
}

export function downloadEmployeeReportPdf({ workerId, period = 'WEEKLY', date = '', month = '', shift = 'ALL', gateId = 'ALL' }) {
  const params = new URLSearchParams();
  params.set('period', period);
  if (date) params.set('date', date);
  if (month) params.set('month', month);
  if (shift && shift !== 'ALL') params.set('shift', shift);
  if (gateId && gateId !== 'ALL') params.set('gate_id', gateId);

  const fallback = `SURAKSHA_Employee_${period}_${workerId}.pdf`;
  return downloadReportFile(`/reports/pdf/employee/${encodeURIComponent(workerId)}?${params.toString()}`, fallback);
}

export function downloadAllEmployeesReportPdf({ period = 'WEEKLY', date = '', month = '', shift = 'ALL', gateId = 'ALL' }) {
  const params = new URLSearchParams();
  params.set('period', period);
  if (date) params.set('date', date);
  if (month) params.set('month', month);
  if (shift && shift !== 'ALL') params.set('shift', shift);
  if (gateId && gateId !== 'ALL') params.set('gate_id', gateId);

  const fallback = `SURAKSHA_All_Employees_${period}.pdf`;
  return downloadReportFile(`/reports/pdf/all?${params.toString()}`, fallback);
}
