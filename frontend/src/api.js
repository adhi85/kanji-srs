const BASE = '/api';

function getToken() {
  return localStorage.getItem('token');
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const resp = await fetch(`${BASE}${path}`, { headers, ...options });
  if (resp.status === 401) {
    localStorage.removeItem('token');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export const api = {
  register: (username, password) => request('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  }),
  login: (username, password) => request('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  }),
  me: () => request('/auth/me'),
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
  getSubjectsByType: (type) => request(`/subjects/by-type/${type}`),
  getSubject: (id) => request(`/subjects/${id}`),
  getSettings: () => request('/settings'),
  updateSettings: (updates) => request('/settings', {
    method: 'PUT',
    body: JSON.stringify(updates),
  }),
  getLevels: () => request('/levels'),
  getLevelDetail: (level) => request(`/levels/${level}`),
  getForecast: () => request('/forecast'),
  getExtraStudySummary: () => request('/extra-study/summary'),
  getExtraStudy: (mode) => request(`/extra-study?mode=${mode}`),
  submitExtraStudy: (subjectId, answerType, answer) => request(`/extra-study/${subjectId}`, {
    method: 'POST',
    body: JSON.stringify({ answer_type: answerType, answer }),
  }),
  getCriticalItems: () => request('/critical-items'),
  getSubjectSynonyms: (id) => request(`/subjects/${id}/synonyms`),
  addSubjectSynonym: (id, meaning) => request(`/subjects/${id}/synonyms`, {
    method: 'POST',
    body: JSON.stringify({ meaning }),
  }),
  deleteSubjectSynonym: (subjectId, synonymId) => request(`/subjects/${subjectId}/synonyms/${synonymId}`, {
    method: 'DELETE',
  }),
  getRecentlyUnlocked: () => request('/recently-unlocked'),
  getLevelHistory: () => request('/level-history'),
  resetSubject: (id) => request(`/subjects/${id}/reset`, { method: 'POST' }),
  resurrectSubject: (id) => request(`/subjects/${id}/resurrect`, { method: 'POST' }),
};
