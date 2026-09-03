const VISION_BASE_URL = (import.meta.env?.VITE_VISION_HTTP_URL || '').replace(/\/$/, '');

async function faceRequest(path, options) {
  const response = await fetch(`${VISION_BASE_URL}${path}`, options);

  if (!response.ok) {
    let detail = `Face registration failed (${response.status}).`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
    }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }

  return response.status === 204 ? null : response.json();
}

function buildFaceForm(personId, name, images) {
  const form = new FormData();
  if (personId) form.append('person_id', personId);
  if (name) form.append('name', name);
  images.forEach((image, index) => {
    form.append('images', image, `${personId}-face-${index + 1}.jpg`);
  });
  return form;
}

export async function registerFace(personId, name, images) {
  try {
    return await faceRequest('/api/faces', {
      method: 'POST',
      body: buildFaceForm(personId, name, images),
    });
  } catch (error) {
    // A previous request may have completed even if its response was lost. Replacing
    // that template makes the form retry safe without creating duplicate profiles.
    if (error.status !== 409) throw error;
    return faceRequest(`/api/faces/${encodeURIComponent(personId)}`, {
      method: 'PUT',
      body: buildFaceForm(personId, null, images),
    });
  }
}
