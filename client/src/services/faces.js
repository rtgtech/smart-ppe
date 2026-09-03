const VISION_BASE_URL = (import.meta.env?.VITE_VISION_HTTP_URL || '').replace(/\/$/, '');

function formatErrorDetail(detail, fallback) {
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (!Array.isArray(detail)) return fallback;

  const messages = detail.map((issue) => {
    if (!issue || typeof issue !== 'object') return null;
    const field = Array.isArray(issue.loc) ? issue.loc.at(-1) : null;
    const message = typeof issue.msg === 'string' ? issue.msg : null;
    if (!message) return null;
    return field ? `${field}: ${message}` : message;
  }).filter(Boolean);

  return messages.length ? messages.join('; ') : fallback;
}

async function faceRequest(path, options) {
  const response = await fetch(`${VISION_BASE_URL}${path}`, options);

  if (!response.ok) {
    let detail = `Face registration failed (${response.status}).`;
    try {
      const body = await response.json();
      detail = formatErrorDetail(body.detail, detail);
    } catch {
    }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }

  return response.status === 204 ? null : response.json();
}

function buildFaceForm(personId, name, images) {
  const normalizedId = personId?.trim();
  const normalizedName = name?.trim();
  if (!normalizedId) throw new Error('A worker ID is required for face registration.');
  if (name != null && !normalizedName) throw new Error('A worker name is required for face registration.');
  if (!Array.isArray(images) || images.length !== 5) {
    throw new Error('Face registration requires exactly five captures.');
  }
  if (images.some((image) => !(image instanceof Blob) || image.size === 0)) {
    throw new Error('One or more face captures are empty or invalid. Retake all five photos.');
  }

  const form = new FormData();
  if (name != null) {
    form.append('person_id', normalizedId);
    form.append('name', normalizedName);
  }
  images.forEach((image, index) => {
    form.append('images', image, `${normalizedId}-face-${index + 1}.jpg`);
  });
  return form;
}

export async function registerFace(personId, name, images) {
  return faceRequest('/api/faces', {
    method: 'POST',
    body: buildFaceForm(personId, name, images),
  });
}

export function deleteFace(personId) {
  return faceRequest(`/api/faces/${encodeURIComponent(personId.trim())}`, {
    method: 'DELETE',
  });
}
