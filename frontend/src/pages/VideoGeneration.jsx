import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { guidesApi } from '../services/api'

function VideoGeneration() {
  const { guideId } = useParams()
  const navigate = useNavigate()
  const [guide, setGuide] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [progress, setProgress] = useState(0)
  const [progressMessage, setProgressMessage] = useState('')
  const [videoUrl, setVideoUrl] = useState(null)
  const [error, setError] = useState(null)
  const [taskId, setTaskId] = useState(null)
  
  // Настройки TTS
  const [settings, setSettings] = useState({
    ttsEngine: 'silero',
    ttsVoice: 'xenia',
    ttsSpeed: 1.0,
    ttsPitch: 0,
  })

  // Доступные голоса
  const voices = {
    silero: [
      { value: 'xenia', label: 'Ксения (женский)' },
      { value: 'baya', label: 'Бая (женский)' },
      { value: 'kseniya', label: 'Ксения 2 (женский)' },
      { value: 'eugene', label: 'Евгений (мужской)' },
      { value: 'aidar', label: 'Айдар (мужской)' },
    ],
    edge: [
      { value: 'ru-RU-SvetlanaNeural', label: 'Светлана (женский)' },
      { value: 'ru-RU-DmitryNeural', label: 'Дмитрий (мужской)' },
    ],
    chatterbox: [
      { value: 'neutral', label: 'Нейтральный' },
    ]
  }

  useEffect(() => {
    fetchGuide()
  }, [guideId])
  
  // Polling статуса задачи
  useEffect(() => {
    if (!taskId || !generating) return
    
    const pollInterval = setInterval(async () => {
      try {
        const response = await fetch(`/api/v1/video/status/${guide.id}/${taskId}`)
        const status = await response.json()
        
        setProgress(status.progress || 0)
        setProgressMessage(status.current_step || '')
        
        if (status.task_status === 'SUCCESS') {
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
    }, 1000)  // Проверяем каждую секунду
    
    return () => clearInterval(pollInterval)
  }, [taskId, generating, guide?.id])

  const fetchGuide = async () => {
    try {
      const data = await guidesApi.getByUuid(guideId)
      setGuide(data)
      
      // Если видео уже сгенерировано, показываем его
      if (data.shorts_video_path && data.id) {
        const videoUrl = `/api/v1/video/download/${data.id}`
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
    setProgress(0)
    setProgressMessage('Запуск генерации...')
    
    try {
      const response = await fetch(`/api/v1/video/generate/${guide.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tts_engine: settings.ttsEngine,
          tts_voice: settings.ttsVoice,
          tts_speed: settings.ttsSpeed,
          tts_pitch: settings.ttsPitch,
        })
      })
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        const errorMessage = errorData.detail || `HTTP error! status: ${response.status}`
        throw new Error(errorMessage)
      }
      
      const data = await response.json()
      
      if (data.success && data.task_id) {
        setTaskId(data.task_id)
        setProgressMessage('Задача в очереди...')
      } else {
        const errorMsg = data.error || 'Не получен ID задачи. Проверьте, что Celery worker запущен.'
        setError(errorMsg)
        setGenerating(false)
      }
      
    } catch (error) {
      setError(error.message || 'Не удалось запустить генерацию')
      setGenerating(false)
    }
  }

  const handleDownload = async () => {
    if (!guide?.id) return
    
    try {
      const response = await fetch(`/api/v1/video/download/${guide.id}`)
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${guide.title.replace(/[^a-z0-9]/gi, '_')}_video.mp4`
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
    <div className="max-w-6xl mx-auto">
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
            Генерация видео-гайда с озвучкой
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Preview / Video */}
        <div className="bg-gray-800 rounded-xl overflow-hidden">
          <div className="aspect-video bg-gray-900 flex items-center justify-center">
            {videoUrl ? (
              <video
                src={videoUrl}
                controls
                className="w-full h-full object-contain"
              />
            ) : generating ? (
              <div className="text-center p-8 w-full">
                <div className="w-16 h-16 mx-auto mb-4">
                  <div className="w-16 h-16 border-4 border-yellow-500 border-t-transparent rounded-full animate-spin" />
                </div>
                <p className="text-yellow-400 font-medium mb-2">Генерация видео...</p>
                
                {/* Progress bar */}
                <div className="w-full bg-gray-700 rounded-full h-2 mb-2">
                  <div 
                    className="bg-yellow-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                
                <p className="text-gray-400 text-sm">{progressMessage}</p>
                <p className="text-gray-500 text-xs mt-1">{progress}%</p>
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
                  Нажмите "Сгенерировать видео" для создания
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
            <h3 className="font-medium mb-4">Настройки озвучки</h3>
            
            {/* TTS Engine selector */}
            <div className="mb-4">
              <label className="block text-sm text-gray-400 mb-2">Движок озвучки</label>
              <div className="grid grid-cols-3 gap-2">
                <button
                  onClick={() => setSettings(s => ({ ...s, ttsEngine: 'silero', ttsVoice: 'xenia' }))}
                  disabled={generating}
                  className={`
                    px-3 py-3 rounded-lg text-sm transition-colors text-left
                    ${settings.ttsEngine === 'silero'
                      ? 'bg-yellow-500 text-black'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }
                  `}
                >
                  <div className="font-medium">Silero</div>
                </button>
                <button
                  onClick={() => setSettings(s => ({ ...s, ttsEngine: 'edge', ttsVoice: 'ru-RU-SvetlanaNeural' }))}
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
                </button>
                <button
                  onClick={() => setSettings(s => ({ ...s, ttsEngine: 'chatterbox', ttsVoice: 'neutral' }))}
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
                </button>
              </div>
            </div>

            {/* Voice selector */}
            <div className="mb-4">
              <label className="block text-sm text-gray-400 mb-2">Голос</label>
              <select
                value={settings.ttsVoice}
                onChange={(e) => setSettings(s => ({ ...s, ttsVoice: e.target.value }))}
                disabled={generating}
                className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm"
              >
                {voices[settings.ttsEngine].map(voice => (
                  <option key={voice.value} value={voice.value}>
                    {voice.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Speed slider */}
            <div className="mb-4">
              <label className="block text-sm text-gray-400 mb-2">
                Скорость: {settings.ttsSpeed.toFixed(1)}x
              </label>
              <input
                type="range"
                min="0.5"
                max="2.0"
                step="0.1"
                value={settings.ttsSpeed}
                onChange={(e) => setSettings(s => ({ ...s, ttsSpeed: parseFloat(e.target.value) }))}
                disabled={generating}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>0.5x</span>
                <span>1.0x</span>
                <span>2.0x</span>
              </div>
            </div>

            {/* Pitch slider (только для Edge TTS) */}
            {settings.ttsEngine === 'edge' && (
              <div className="mb-4">
                <label className="block text-sm text-gray-400 mb-2">
                  Тембр: {settings.ttsPitch > 0 ? '+' : ''}{settings.ttsPitch}
                </label>
                <input
                  type="range"
                  min="-20"
                  max="20"
                  step="1"
                  value={settings.ttsPitch}
                  onChange={(e) => setSettings(s => ({ ...s, ttsPitch: parseInt(e.target.value) }))}
                  disabled={generating}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>Низкий</span>
                  <span>Норма</span>
                  <span>Высокий</span>
                </div>
              </div>
            )}
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
              'Сгенерировать видео'
            )}
          </button>

          {/* Steps preview */}
          <div className="bg-gray-800 rounded-xl p-6">
            <h4 className="font-semibold text-lg mb-4 text-white">
              Шаги ({guide.steps?.length || 0})
            </h4>
            <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2 custom-scrollbar">
              {guide.steps?.map((step, index) => (
                <div 
                  key={step.id} 
                  className="bg-gray-700/50 hover:bg-gray-700 transition-all duration-200 rounded-lg p-4 border border-gray-600/50 hover:border-orange-500/50 group"
                >
                  <div className="flex items-start space-x-3">
                    <span className="w-8 h-8 bg-gradient-to-br from-orange-500 to-orange-600 rounded-full flex items-center justify-center text-sm font-bold text-white flex-shrink-0 shadow-lg group-hover:scale-110 transition-transform">
                      {index + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-gray-100 text-base leading-relaxed break-words">
                        {step.edited_text || step.normalized_text || 'Нет описания'}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          <style jsx>{`
            .custom-scrollbar::-webkit-scrollbar {
              width: 8px;
            }
            .custom-scrollbar::-webkit-scrollbar-track {
              background: rgba(55, 65, 81, 0.3);
              border-radius: 4px;
            }
            .custom-scrollbar::-webkit-scrollbar-thumb {
              background: rgba(249, 115, 22, 0.5);
              border-radius: 4px;
            }
            .custom-scrollbar::-webkit-scrollbar-thumb:hover {
              background: rgba(249, 115, 22, 0.7);
            }
          `}</style>
        </div>
      </div>
    </div>
  )
}

export default VideoGeneration
