import axios from 'axios'

const API_BASE_URL = '/api/v1'

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Add auth token if exists
    const token = localStorage.getItem('authToken')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

// Guides API
export const guidesApi = {
  getAll: (params = {}) => api.get('/guides', { params }),
  getById: (id) => api.get(`/guides/${id}`),
  getByUuid: (uuid) => api.get(`/guides/uuid/${uuid}`),
  create: (data) => api.post('/guides', data),
  update: (id, data) => api.patch(`/guides/${id}`, data),
  delete: (id) => api.delete(`/guides/${id}`),
}

// Steps API
export const stepsApi = {
  getByGuideId: (guideId) => api.get(`/steps/guide/${guideId}`),
  update: (id, data) => api.patch(`/steps/${id}`, data),
  reorder: (guideId, stepOrder) => api.post(`/steps/guide/${guideId}/reorder`, { step_order: stepOrder }),
  delete: (id) => api.delete(`/steps/${id}`),
}

// Sessions API
export const sessionsApi = {
  upload: (formData) => api.post('/sessions/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  process: (sessionId) => api.post(`/sessions/${sessionId}/process`),
  getStatus: (sessionId) => api.get(`/sessions/${sessionId}/status`),
}

// Export API
export const exportApi = {
  markdown: (guideId) => api.get(`/export/guide/${guideId}/markdown`, { responseType: 'blob' }),
  html: (guideId) => api.get(`/export/guide/${guideId}/html`, { responseType: 'blob' }),
}

// Shorts API
export const shortsApi = {
  generate: (guideId, options) => api.post(`/shorts/generate/${guideId}`, options),
  getStatus: (taskId) => api.get(`/shorts/status/${taskId}`),
  download: (taskId) => api.get(`/shorts/download/${taskId}`, { responseType: 'blob' }),
}

// Health check
export const healthApi = {
  check: () => api.get('/health'),
}

export default api