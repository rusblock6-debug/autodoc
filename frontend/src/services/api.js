import axios from 'axios'

// Use relative path to work with Vite proxy in Docker
// In Docker, Vite proxy will forward /api to http://autodoc-ai:8000
export const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'
const API_BASE_URL_INTERNAL = API_BASE_URL

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL_INTERNAL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response) => {
    // Log successful responses in development
    if (import.meta.env.DEV) {
      console.log('API Response:', response.config.method?.toUpperCase(), response.config.url, response.data);
    }
    return response.data;
  },
  (error) => {
    // Enhanced error logging
    console.error('API Error:', {
      method: error.config?.method?.toUpperCase(),
      url: error.config?.url,
      status: error.response?.status,
      statusText: error.response?.statusText,
      data: error.response?.data,
      message: error.message
    });
    
    if (error.response?.status === 401) {
      // Handle unauthorized
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    
    // Return error with full details for better debugging
    return Promise.reject(error)
  }
)

// ===== Guides API =====
export const guidesApi = {
  getAll: (params = {}) => api.get('/guides', { params }),
  
  getById: (id) => api.get(`/guides/${id}`),
  
  create: (data) => api.post('/guides', data),
  
  update: (id, data) => api.patch(`/guides/${id}`, data),
  
  delete: (id) => api.delete(`/guides/${id}`),
  
  export: (id, format = 'markdown') => 
    api.get(`/guides/${id}/export/${format}`),
}

// ===== Sessions API =====
export const sessionsApi = {
  upload: (formData) => 
    api.post('/sessions/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  
  getById: (id) => api.get(`/sessions/${id}`),
  
  process: (id) => api.post(`/sessions/${id}/process`),
  
  getStatus: (id) => api.get(`/sessions/${id}/status`),
}

// ===== Steps API =====
export const stepsApi = {
  getByGuideId: (guideId) => api.get(`/guides/${guideId}/steps`),
  
  getById: (id) => api.get(`/steps/${id}`),
  
  create: (data) => api.post('/steps', data),
  
  update: (id, data) => api.patch(`/steps/${id}`, data),
  
  updateMarker: (id, data) => api.patch(`/steps/${id}/marker`, data),
  
  delete: (id) => api.delete(`/steps/${id}`),
  
  reorder: (id, newPosition) => 
    api.patch(`/steps/${id}/reorder`, { new_position: newPosition }),
  
  merge: (stepIds, mergedText) => 
    api.post('/steps/merge', { step_ids: stepIds, merged_instruction: mergedText }),
}

// ===== Export API =====
export const exportApi = {
  markdown: (guideId) => 
    api.get(`/export/${guideId}/markdown`, { responseType: 'blob' }),
  
  html: (guideId) => 
    api.get(`/export/${guideId}/html`, { responseType: 'blob' }),
  
  pdf: (guideId) => 
    api.get(`/export/${guideId}/pdf`, { responseType: 'blob' }),
}

// ===== Shorts API =====
export const shortsApi = {
  generate: (guideId, settings) => 
    api.post(`/shorts/${guideId}/generate`, settings),
  
  getStatus: (taskId) => api.get(`/shorts/${taskId}/status`),
  
  download: (taskId) => 
    api.get(`/shorts/${taskId}/download`, { responseType: 'blob' }),
}

// ===== Storage API =====
export const storageApi = {
  getPresignedUrl: (fileName, contentType) => 
    api.post('/storage/presigned-url', { file_name: fileName, content_type: contentType }),
  
  getDownloadUrl: (fileKey) => 
    api.get(`/storage/download-url/${fileKey}`),
}

// ===== Auth API =====
export const authApi = {
  login: (email, password) => 
    api.post('/auth/login', { email, password }),
  
  register: (data) => api.post('/auth/register', data),
  
  logout: () => api.post('/auth/logout'),
  
  getCurrentUser: () => api.get('/auth/me'),
}

// ===== Processing API =====
export const processingApi = {
  startProcessing: (guideId, options = {}) => 
    api.post(`/processing/${guideId}/start`, options),
  
  getStatus: (jobId) => api.get(`/processing/jobs/${jobId}`),
  
  cancelJob: (jobId) => api.post(`/processing/jobs/${jobId}/cancel`),
}

export default api
