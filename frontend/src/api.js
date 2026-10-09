/**
 * API Client with automatic Bearer token injection and relative endpoint routing.
 */

// If running on port 8501 (Nginx proxy) or port 8100, use relative paths to avoid CORS
export const API_BASE = '';

export function getToken() {
  return localStorage.getItem('rag_jwt_token') || '';
}

export function setToken(token) {
  if (token) {
    localStorage.setItem('rag_jwt_token', token);
  } else {
    localStorage.removeItem('rag_jwt_token');
  }
}

export function getUser() {
  try {
    return JSON.parse(localStorage.getItem('rag_user_data') || 'null');
  } catch {
    return null;
  }
}

export function setUser(user) {
  if (user) {
    localStorage.setItem('rag_user_data', JSON.stringify(user));
  } else {
    localStorage.removeItem('rag_user_data');
  }
}

export async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const headers = options.headers || {};

  const token = getToken();
  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(url, { ...options, headers });
  if (res.status === 401 && !path.includes('/v1/auth/')) {
    // Token expired or invalid
    setToken(null);
    setUser(null);
    window.dispatchEvent(new CustomEvent('auth:expired'));
    throw new Error('Session expired. Please sign in again.');
  }

  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error((data && data.detail) || `Request failed with status ${res.status}`);
  }
  return data;
}

// Authentication APIs
export async function login(email, password) {
  return request('/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
}

export async function getMe() {
  return request('/v1/auth/me');
}

// Documents APIs
export async function listDocuments() {
  return request('/v1/documents');
}

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append('file', file);
  return request('/v1/documents', {
    method: 'POST',
    body: formData,
  });
}

export async function updateDocument(documentId, file) {
  const formData = new FormData();
  formData.append('file', file);
  return request(`/v1/documents/${documentId}`, {
    method: 'PUT',
    body: formData,
  });
}

export async function deleteDocument(documentId) {
  return request(`/v1/documents/${documentId}`, {
    method: 'DELETE',
  });
}

export async function getDocumentVersions(documentId) {
  return request(`/v1/documents/${documentId}/versions`);
}

// Query APIs
export async function askQuestion(question, documentId = null) {
  return request('/v1/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, document_id: documentId }),
  });
}

// Usage & History APIs
export async function getUsage() {
  return request('/v1/usage');
}

export async function getHistory() {
  return request('/v1/history');
}

// System Health
export async function getHealth() {
  return request('/health');
}
