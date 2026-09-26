const BASE = '/api';

async function request(path, options = {}) {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export const api = {
  getSummary: () => request('/summary'),
  getLessons: () => request('/lessons'),
  startLessons: (ids) => request('/lessons/start', {
    method: 'POST',
    body: JSON.stringify({ subject_ids: ids }),
  }),
  getReviews: () => request('/reviews'),
  submitReview: (subjectId, answerType, answer) => request(`/reviews/${subjectId}`, {
    method: 'POST',
    body: JSON.stringify({ answer_type: answerType, answer }),
  }),
  getSubjects: (params) => request(`/subjects?${new URLSearchParams(params)}`),
  getSubject: (id) => request(`/subjects/${id}`),
  getSettings: () => request('/settings'),
  updateSettings: (updates) => request('/settings', {
    method: 'PUT',
    body: JSON.stringify(updates),
  }),
};
