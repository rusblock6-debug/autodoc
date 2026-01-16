import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { sessionsApi } from '../services/api'

function SessionStatus() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchStatus()
    
    // Polling каждые 2 секунды пока обрабатывается
    const interval = setInterval(() => {
      fetchStatus()
    }, 2000)
    
    return () => clearInterval(interval)
  }, [sessionId])

  const fetchStatus = async () => {
    try {
      console.log('[SessionStatus] Fetching session:', sessionId)
      const data = await sessionsApi.getStatus(sessionId)
      console.log('[SessionStatus] Got data:', data)
      setSession(data)
      setLoading(false)
      
      // Если обработка завершена, переходим к редактору
      if (data.status === 'completed' && data.guide_id) {
        console.log('[SessionStatus] Redirecting to guide:', data.guide_id)
        navigate(`/guide/${data.guide_id}/edit`)
      }
    } catch (error) {
      console.error('[SessionStatus] Failed to fetch status:', error)
      console.error('[SessionStatus] Session ID was:', sessionId)
      setLoading(false)
    }
  }

  const getStatusInfo = (status) => {
    const info = {
      uploaded: {
        label: 'Загружено',
        description: 'Файлы загружены, ожидание обработки...',
        color: 'text-blue-400',
        progress: 10,
      },
      processing: {
        label: 'Обработка',
        description: 'Распознавание речи, извлечение скриншотов, генерация текста...',
        color: 'text-yellow-400',
        progress: 50,
      },
      completed: {
        label: 'Готово',
        description: 'Гайд создан! Переход к редактору...',
        color: 'text-green-400',
        progress: 100,
      },
      failed: {
        label: 'Ошибка',
        description: 'Произошла ошибка при обработке',
        color: 'text-red-400',
        progress: 0,
      },
    }
    return info[status] || info.uploaded
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-yellow-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  if (!session) {
    return (
      <div className="max-w-lg mx-auto text-center py-12">
        <p className="text-gray-400">Сессия не найдена</p>
      </div>
    )
  }

  const statusInfo = getStatusInfo(session.status)

  return (
    <div className="max-w-lg mx-auto">
      <div className="bg-gray-800 rounded-xl p-8 text-center">
        {/* Анимированный индикатор */}
        <div className="relative w-24 h-24 mx-auto mb-6">
          <svg className="w-24 h-24 transform -rotate-90">
            <circle
              cx="48"
              cy="48"
              r="44"
              stroke="currentColor"
              strokeWidth="8"
              fill="none"
              className="text-gray-700"
            />
            <circle
              cx="48"
              cy="48"
              r="44"
              stroke="currentColor"
              strokeWidth="8"
              fill="none"
              strokeDasharray={276}
              strokeDashoffset={276 - (276 * statusInfo.progress) / 100}
              className={`${statusInfo.color} transition-all duration-500`}
              strokeLinecap="round"
            />
          </svg>
          
          {session.status === 'processing' && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-12 h-12 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin" />
            </div>
          )}
          
          {session.status === 'completed' && (
            <div className="absolute inset-0 flex items-center justify-center">
              <svg className="w-10 h-10 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
          )}
          
          {session.status === 'failed' && (
            <div className="absolute inset-0 flex items-center justify-center">
              <svg className="w-10 h-10 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
          )}
        </div>

        {/* Статус */}
        <h2 className={`text-xl font-bold mb-2 ${statusInfo.color}`}>
          {statusInfo.label}
        </h2>
        <p className="text-gray-400 mb-6">
          {statusInfo.description}
        </p>

        {/* Детали */}
        <div className="bg-gray-900/50 rounded-lg p-4 text-left space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-400">Название:</span>
            <span>{session.title}</span>
          </div>
          {session.duration_seconds && (
            <div className="flex justify-between">
              <span className="text-gray-400">Длительность:</span>
              <span>{Math.round(session.duration_seconds)} сек</span>
            </div>
          )}
          {session.click_count > 0 && (
            <div className="flex justify-between">
              <span className="text-gray-400">Кликов:</span>
              <span>{session.click_count}</span>
            </div>
          )}
        </div>

        {/* Ошибка */}
        {session.status === 'failed' && session.error_message && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-left">
            <p className="text-sm text-red-400">{session.error_message}</p>
          </div>
        )}

        {/* Кнопки */}
        {session.status === 'failed' && (
          <button
            onClick={() => navigate('/upload')}
            className="mt-6 px-6 py-2 bg-yellow-500 hover:bg-yellow-400 text-black rounded-lg font-medium transition-colors"
          >
            Попробовать снова
          </button>
        )}
      </div>

      {/* Этапы обработки */}
      <div className="mt-6 space-y-3">
        <ProcessingStep
          label="Загрузка файлов"
          done={['processing', 'completed'].includes(session.status)}
          active={session.status === 'uploaded'}
        />
        <ProcessingStep
          label="Распознавание речи (ASR)"
          done={session.status === 'completed'}
          active={session.status === 'processing'}
        />
        <ProcessingStep
          label="Извлечение скриншотов"
          done={session.status === 'completed'}
          active={session.status === 'processing'}
        />
        <ProcessingStep
          label="Генерация инструкций (LLM)"
          done={session.status === 'completed'}
          active={session.status === 'processing'}
        />
        <ProcessingStep
          label="Создание гайда"
          done={session.status === 'completed'}
          active={false}
        />
      </div>
    </div>
  )
}

function ProcessingStep({ label, done, active }) {
  return (
    <div className="flex items-center space-x-3">
      <div className={`
        w-6 h-6 rounded-full flex items-center justify-center
        ${done ? 'bg-green-500' : active ? 'bg-yellow-500' : 'bg-gray-700'}
      `}>
        {done ? (
          <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        ) : active ? (
          <div className="w-3 h-3 bg-black rounded-full animate-pulse" />
        ) : (
          <div className="w-2 h-2 bg-gray-500 rounded-full" />
        )}
      </div>
      <span className={done ? 'text-white' : active ? 'text-yellow-400' : 'text-gray-500'}>
        {label}
      </span>
    </div>
  )
}

export default SessionStatus
