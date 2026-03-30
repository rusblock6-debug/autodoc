import axios from 'axios'

const API_BASE = '/api/v1'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
})

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    // Логируем только детали ошибки
    if (error.response?.data?.detail) {
      console.error('API Error:', error.response.data.detail)
    }
    return Promise.reject(error)
  }
)

// === Sessions API ===
export const sessionsApi = {
  // Список сессий
  getAll: (params = {}) => api.get('/sessions', { params }),
  
  // Загрузить запись (видео + аудио + лог кликов)
  upload: async (videoFile, audioFile, clicksLog, title) => {
    const formData = new FormData()
    if (videoFile) formData.append('video', videoFile)
    if (audioFile) formData.append('audio', audioFile)
    if (clicksLog) formData.append('clicks_log', clicksLog)
    if (title) formData.append('title', title)
    
    return api.post('/sessions/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  
  // Получить статус сессии
  getStatus: (sessionId) => api.get(`/sessions/${sessionId}`),
  
  // Получить транскрипцию
  getTranscription: (sessionId) => api.get(`/sessions/${sessionId}/transcription`),
  
  // Удалить сессию
  delete: (sessionId) => api.delete(`/sessions/${sessionId}`),
}

// === Guides API ===
export const guidesApi = {
  // Список гайдов
  getAll: (params = {}) => api.get('/guides', { params }),
  
  // Получить гайд по ID
  getById: (guideId) => api.get(`/guides/${guideId}`),
  
  // Получить гайд по UUID
  getByUuid: (uuid) => api.get(`/guides/uuid/${uuid}`),
  
  // Создать гайд
  create: (data) => api.post('/guides', data),
  
  // Обновить гайд
  update: (guideId, data) => api.patch(`/guides/${guideId}`, data),
  
  // Удалить гайд
  delete: (guideId) => api.delete(`/guides/${guideId}`),
}

// === Steps API ===
export const stepsApi = {
  // Получить шаги гайда
  getByGuideId: (guideId) => api.get(`/guides/${guideId}/steps`),
  
  // Обновить шаг (текст, координаты маркера)
  update: (stepId, data) => api.patch(`/steps/${stepId}`, data),
  
  // Изменить порядок шагов
  reorder: (guideId, stepIds) => api.post(`/guides/${guideId}/steps/reorder`, { step_ids: stepIds }),
  
  // Удалить шаг
  delete: (stepId) => api.delete(`/steps/${stepId}`),
  
  // Объединить шаги
  merge: (guideId, stepIds) => api.post(`/guides/${guideId}/steps/merge`, { step_ids: stepIds }),
}

// === Video API (NEW) ===
export const videoApi = {
  // Запустить генерацию видео
  generate: (guideId, options = {}) => api.post(`/video/generate/${guideId}`, options),
  
  // Получить статус генерации по task_id
  getStatus: (guideId, taskId) => api.get(`/video/status/${guideId}/${taskId}`),
  
  // Получить статус видео гайда
  getGuideStatus: (guideId) => api.get(`/video/status/${guideId}`),
  
  // Скачать готовое видео
  download: (guideId) => api.get(`/video/download/${guideId}`, { responseType: 'blob' }),
}

// === Shorts API (DEPRECATED - use videoApi) ===
export const shortsApi = {
  // Запустить генерацию Shorts
  generate: (guideId, options = {}) => api.post(`/shorts/generate/${guideId}`, options),
  
  // Получить статус генерации
  getStatus: (guideId, taskId = null) => {
    const params = taskId ? { task_id: taskId } : {}
    return api.get(`/shorts/status/${guideId}`, { params })
  },
  
  // Скачать готовое видео
  download: (guideId) => api.get(`/shorts/download/${guideId}`, { responseType: 'blob' }),
  
  // Получить превью (URL видео)
  getPreview: (guideId) => api.get(`/guides/${guideId}/shorts/preview`),
}

// === Export API ===
export const exportApi = {
  // Экспорт в Markdown
  markdown: (guideId) => api.get(`/export/${guideId}/markdown`, { responseType: 'blob' }),
  
  // Экспорт в HTML
  html: (guideId) => api.get(`/export/${guideId}/html`, { responseType: 'blob' }),
  
  // Экспорт в PDF
  pdf: (guideId) => api.get(`/export/${guideId}/pdf`, { responseType: 'blob' }),
  
  // Экспорт в JSON
  json: (guideId) => api.get(`/export/${guideId}/json`, { responseType: 'blob' }),
}

// === Storage API ===
export const storageApi = {
  // Получить URL для скачивания файла
  getDownloadUrl: (fileKey) => api.get(`/storage/download-url`, { params: { key: fileKey } }),
  
  // Получить URL скриншота (теперь через guides endpoint)
  getScreenshotUrl: (path) => {
    // Убираем начальный слэш если есть, чтобы не было дублирования
    const cleanPath = path.startsWith('/') ? path.slice(1) : path;
    return `${API_BASE}/guides/screenshots/${cleanPath}`;
  },
}

export default api
