import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { guidesApi, shortsApi } from '../services/api'

function ShortsPreview() {
  const { guideId } = useParams()
  const navigate = useNavigate()
  const [guide, setGuide] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [taskId, setTaskId] = useState(null)
  const [progress, setProgress] = useState(0)
  const [progressMessage, setProgressMessage] = useState('')
  const [videoUrl, setVideoUrl] = useState(null)
  const [error, setError] = useState(null)
  
  // Настройки генерации
  const [settings, setSettings] = useState({
    voice: 'ru-RU-SvetlanaNeural',
    markerColor: '#FFEB3B',
    platform: 'tiktok',
  })

  useEffect(() => {
    fetchGuide()
  }, [guideId])

  useEffect(() => {
    let interval
    if (taskId && generating) {
      interval = setInterval(checkProgress, 1500)
    }
    return () => clearInterval(interval)
  }, [taskId, generating])

  const fetchGuide = async () => {
    try {
      const data = await guidesApi.getById(guideId)
      setGuide(data)
      
      // Если Shorts уже сгенерирован, показываем его
      if (data.shorts_video_path) {
        const preview = await shortsApi.getPreview(guideId)
        setVideoUrl(preview.url)
      }
    } catch (error) {
      console.error('Failed to fetch guide:', error)
    } finally {
      setLoading(false)
    }
  }

  const checkProgress = async () => {
    try {
      const status = await shortsApi.getStatus(taskId)
      setProgress(status.progress || 0)
      setProgressMessage(status.message || '')
      
      if (status.status === 'completed') {
        setGenerating(false)
        setTaskId(null)
        // Получаем URL видео
        const preview = await shortsApi.getPreview(guideId)
        setVideoUrl(preview.url)
        // Обновляем гайд
        fetchGuide()
      } else if (status.status === 'failed') {
        setGenerating(false)
        setTaskId(null)
        setError(status.error || 'Ошибка генерации')
      }
    } catch (error) {
      console.error('Failed to check progress:', error)
    }
  }

  const handleGenerate = async () => {
    setGenerating(true)
    setError(null)
    setProgress(0)
    setProgressMessage('Запуск генерации...')
    
    try {
      const response = await shortsApi.generate(guideId, {
        voice: settings.voice,
        marker_color: settings.markerColor,
        target_platform: settings.platform,
      })
      setTaskId(response.task_id)
    } catch (error) {
      console.error('Failed to start generation:', error)
      setError('Не удалось запустить генерацию')
      setGenerating(false)
    }
  }

  const handleDownload = async () => {
    try {
      const blob = await shortsApi.download(guideId)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${guide.title.replace(/[^a-z0-9]/gi, '_')}_shorts.mp4`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      console.error('Download failed:', error)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-yellow-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  if (!guide) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-400">Гайд не найден</p>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <button
            onClick={() => navigate(`/guide/${guideId}/edit`)}
            className="text-gray-400 hover:text-white text-sm mb-2 flex items-center"
          >
            <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Назад к редактору
          </button>
          <h1 className="text-2xl font-bold">{guide.title}</h1>
          <p className="text-gray-400 text-sm mt-1">
            Генерация вертикального видео для TikTok / Reels / YouTube Shorts
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Preview / Video */}
        <div className="bg-gray-800 rounded-xl overflow-hidden">
          <div className="aspect-[9/16] bg-gray-900 flex items-center justify-center">
            {videoUrl ? (
              <video
                src={videoUrl}
                controls
                className="w-full h-full object-contain"
              />
            ) : generating ? (
              <div className="text-center p-8">
                <div className="w-16 h-16 mx-auto mb-4 relative">
                  <svg className="w-16 h-16 transform -rotate-90">
                    <circle
                      cx="32"
                      cy="32"
                      r="28"
                      stroke="currentColor"
                      strokeWidth="4"
                      fill="none"
                      className="text-gray-700"
                    />
                    <circle
                      cx="32"
                      cy="32"
                      r="28"
                      stroke="currentColor"
                      strokeWidth="4"
                      fill="none"
                      strokeDasharray={176}
                      strokeDashoffset={176 - (176 * progress) / 100}
                      className="text-yellow-500 transition-all duration-300"
                      strokeLinecap="round"
                    />
                  </svg>
                  <span className="absolute inset-0 flex items-center justify-center text-sm font-bold">
                    {progress}%
                  </span>
                </div>
                <p className="text-yellow-400 font-medium mb-1">Генерация...</p>
                <p className="text-gray-400 text-sm">{progressMessage}</p>
              </div>
            ) : (
              <div className="text-center p-8">
                <div className="w-20 h-20 bg-gray-800 rounded-full flex items-center justify-center mx-auto mb-4">
                  <svg className="w-10 h-10 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <p className="text-gray-400">
                  Нажмите "Сгенерировать" для создания видео
                </p>
              </div>
            )}
          </div>
          
          {/* Video actions */}
          {videoUrl && (
            <div className="p-4 border-t border-gray-700 flex items-center justify-between">
              <div className="text-sm text-gray-400">
                {guide.shorts_duration_seconds && (
                  <span>{Math.round(guide.shorts_duration_seconds)} сек</span>
                )}
              </div>
              <button
                onClick={handleDownload}
                className="px-4 py-2 bg-green-600 hover:bg-green-500 rounded-lg font-medium transition-colors flex items-center"
              >
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Скачать
              </button>
            </div>
          )}
        </div>

        {/* Settings */}
        <div className="space-y-4">
          <div className="bg-gray-800 rounded-xl p-4">
            <h3 className="font-medium mb-4">Настройки генерации</h3>
            
            {/* Voice */}
            <div className="mb-4">
              <label className="block text-sm text-gray-400 mb-2">Голос озвучки</label>
              <select
                value={settings.voice}
                onChange={(e) => setSettings(s => ({ ...s, voice: e.target.value }))}
                disabled={generating}
                className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg focus:ring-1 focus:ring-yellow-500 outline-none"
              >
                <option value="ru-RU-SvetlanaNeural">Светлана (женский)</option>
                <option value="ru-RU-DmitryNeural">Дмитрий (мужской)</option>
                <option value="en-US-JennyNeural">Jenny (English)</option>
                <option value="en-US-GuyNeural">Guy (English)</option>
              </select>
            </div>

            {/* Platform */}
            <div className="mb-4">
              <label className="block text-sm text-gray-400 mb-2">Платформа</label>
              <div className="grid grid-cols-3 gap-2">
                {['tiktok', 'instagram', 'youtube'].map((platform) => (
                  <button
                    key={platform}
                    onClick={() => setSettings(s => ({ ...s, platform }))}
                    disabled={generating}
                    className={`
                      px-3 py-2 rounded-lg text-sm font-medium transition-colors
                      ${settings.platform === platform
                        ? 'bg-yellow-500 text-black'
                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                      }
                    `}
                  >
                    {platform === 'tiktok' && 'TikTok'}
                    {platform === 'instagram' && 'Reels'}
                    {platform === 'youtube' && 'Shorts'}
                  </button>
                ))}
              </div>
            </div>

            {/* Marker color */}
            <div className="mb-4">
              <label className="block text-sm text-gray-400 mb-2">Цвет маркера</label>
              <div className="flex items-center space-x-2">
                <input
                  type="color"
                  value={settings.markerColor}
                  onChange={(e) => setSettings(s => ({ ...s, markerColor: e.target.value }))}
                  disabled={generating}
                  className="w-10 h-10 rounded border border-gray-700 cursor-pointer"
                />
                <input
                  type="text"
                  value={settings.markerColor}
                  onChange={(e) => setSettings(s => ({ ...s, markerColor: e.target.value }))}
                  disabled={generating}
                  className="flex-1 px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm"
                />
              </div>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
              <p className="text-red-400">{error}</p>
            </div>
          )}

          {/* Generate button */}
          <button
            onClick={handleGenerate}
            disabled={generating}
            className={`
              w-full py-3 rounded-xl font-medium transition-all flex items-center justify-center
              ${generating
                ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
                : 'bg-yellow-500 hover:bg-yellow-400 text-black'
              }
            `}
          >
            {generating ? (
              <>
                <div className="w-5 h-5 border-2 border-gray-500 border-t-transparent rounded-full animate-spin mr-2" />
                Генерация...
              </>
            ) : videoUrl ? (
              'Перегенерировать'
            ) : (
              'Сгенерировать Shorts'
            )}
          </button>

          {/* Info */}
          <div className="bg-gray-800/50 rounded-xl p-4">
            <h4 className="font-medium mb-3">Что будет создано:</h4>
            <ul className="space-y-2 text-sm text-gray-400">
              <li className="flex items-start">
                <svg className="w-4 h-4 text-green-400 mr-2 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Вертикальное видео 1080×1920 (9:16)
              </li>
              <li className="flex items-start">
                <svg className="w-4 h-4 text-green-400 mr-2 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                TTS озвучка каждого шага
              </li>
              <li className="flex items-start">
                <svg className="w-4 h-4 text-green-400 mr-2 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Анимированные маркеры на элементах
              </li>
              <li className="flex items-start">
                <svg className="w-4 h-4 text-green-400 mr-2 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Плавные переходы между шагами
              </li>
            </ul>
          </div>

          {/* Steps preview */}
          <div className="bg-gray-800 rounded-xl p-4">
            <h4 className="font-medium mb-3">Шаги ({guide.steps?.length || 0})</h4>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {guide.steps?.map((step, index) => (
                <div key={step.id} className="flex items-start space-x-2 text-sm">
                  <span className="w-5 h-5 bg-gray-700 rounded-full flex items-center justify-center text-xs flex-shrink-0">
                    {index + 1}
                  </span>
                  <span className="text-gray-300 line-clamp-1">
                    {step.edited_text || step.normalized_text}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ShortsPreview
