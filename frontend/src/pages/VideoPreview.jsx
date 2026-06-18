import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { guidesApi, shortsApi } from '../services/api'
import { VolumeIcon } from '../ui'

function ShortsPreview() {
  const { guideId } = useParams()
  const navigate = useNavigate()
  const [guide, setGuide] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [progressMessage, setProgressMessage] = useState('')
  const [videoUrl, setVideoUrl] = useState(null)
  const [error, setError] = useState(null)
  const [taskId, setTaskId] = useState(null)  // Celery task ID
  
  // Настройки генерации
  const [settings, setSettings] = useState({
    markerColor: '#FFEB3B',
    platform: 'tiktok',
    ttsEngine: 'edge',  // 'edge' или 'chatterbox'
  })

  useEffect(() => {
    fetchGuide()
  }, [guideId])
  
  // Polling статуса задачи
  useEffect(() => {
    if (!taskId || !generating) return
    
    const pollInterval = setInterval(async () => {
      try {
        const status = await shortsApi.getStatus(guide.id, taskId)
        
        // Обновляем сообщение прогресса
        if (status.task_status === 'PENDING') {
          setProgressMessage('Задача в очереди...')
        } else if (status.task_status === 'STARTED') {
          setProgressMessage('Генерация видео...')
        } else if (status.task_status === 'SUCCESS') {
          setProgressMessage('Готово!')
          setGenerating(false)
          setTaskId(null)
          await fetchGuide()
          clearInterval(pollInterval)
        } else if (status.task_status === 'FAILURE') {
          setError(status.error_message || 'Генерация не удалась')
          setGenerating(false)
          setTaskId(null)
          clearInterval(pollInterval)
        }
      } catch (err) {
        console.error('Failed to poll task status:', err)
      }
    }, 2000)  // Проверяем каждые 2 секунды
    
    return () => clearInterval(pollInterval)
  }, [taskId, generating, guide?.id])

  const fetchGuide = async () => {
    try {
      const data = await guidesApi.getByUuid(guideId)
      setGuide(data)
      
      // Если Shorts уже сгенерирован, показываем его
      if (data.shorts_video_path && data.id) {
        const videoUrl = `/api/v1/shorts/download/${data.id}`
        setVideoUrl(videoUrl)
      }
    } catch (error) {
      setError(error.response?.data?.detail || 'Не удалось загрузить гайд')
    } finally {
      setLoading(false)
    }
  }

  const handleGenerate = async () => {
    if (!guide?.id) {
      setError('Гайд не загружен')
      return
    }
    
    setGenerating(true)
    setError(null)
    setProgressMessage('Запуск генерации...')
    
    try {
      const response = await shortsApi.generate(guide.id, {
        marker_color: settings.markerColor,
        target_platform: settings.platform,
        tts_engine: settings.ttsEngine,
      })
      
      // Сохраняем task_id для polling
      if (response.task_id) {
        setTaskId(response.task_id)
        setProgressMessage('Задача в очереди...')
      } else {
        setError('Не получен ID задачи')
        setGenerating(false)
      }
      
    } catch (error) {
      setError(error.response?.data?.detail || 'Не удалось запустить генерацию')
      setGenerating(false)
    }
  }

  const handleDownload = async () => {
    if (!guide?.id) return
    
    try {
      const blob = await shortsApi.download(guide.id)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${guide.title.replace(/[^a-z0-9]/gi, '_')}_shorts.mp4`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      setError('Не удалось скачать видео')
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
                <div className="w-16 h-16 mx-auto mb-4">
                  <div className="w-16 h-16 border-4 border-yellow-500 border-t-transparent rounded-full animate-spin" />
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
            
            {/* TTS Engine selector */}
            <div className="mb-4">
              <label className="block text-sm text-gray-400 mb-2">Движок озвучки</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => setSettings(s => ({ ...s, ttsEngine: 'edge' }))}
                  disabled={generating}
                  className={`
                    px-3 py-3 rounded-lg text-sm transition-colors text-left
                    ${settings.ttsEngine === 'edge'
                      ? 'bg-yellow-500 text-black'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }
                  `}
                >
                  <div className="font-medium">Edge TTS</div>
                  <div className="text-xs opacity-75 mt-1">Быстро (2-5 сек)</div>
                </button>
                <button
                  onClick={() => setSettings(s => ({ ...s, ttsEngine: 'chatterbox' }))}
                  disabled={generating}
                  className={`
                    px-3 py-3 rounded-lg text-sm transition-colors text-left
                    ${settings.ttsEngine === 'chatterbox'
                      ? 'bg-yellow-500 text-black'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }
                  `}
                >
                  <div className="font-medium">Chatterbox</div>
                  <div className="text-xs opacity-75 mt-1">Медленно, качество выше</div>
                </button>
              </div>
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
                Нейронная TTS озвучка ({settings.ttsEngine === 'edge' ? 'Edge TTS' : 'Chatterbox'})
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
                  <span className="text-gray-300 line-clamp-1 flex-1">
                    {step.edited_text || step.normalized_text}
                  </span>
                  <button
                    onClick={() => {
                      const audio = new Audio(`/api/v1/shorts/test-tts/${step.id}`)
                      audio.play()
                    }}
                    className="px-2 py-1 bg-blue-600 hover:bg-blue-500 rounded text-xs flex items-center"
                    title="Прослушать озвучку"
                  >
                    <VolumeIcon size={14} />
                  </button>
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
