import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { guidesApi } from '../services/api'

function Dashboard() {
  const [guides, setGuides] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchGuides()
    
    // Автообновление каждые 5 секунд для новых гайдов
    const interval = setInterval(fetchGuides, 5000)
    return () => clearInterval(interval)
  }, [])

  const fetchGuides = async () => {
    try {
      const response = await guidesApi.getAll()
      setGuides(response.items || response || [])
    } catch (error) {
      console.error('Failed to fetch guides:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (guideId) => {
    if (!confirm('Удалить этот гайд?')) return
    
    try {
      await guidesApi.delete(guideId)
      fetchGuides()
    } catch (error) {
      console.error('Failed to delete:', error)
    }
  }

  const getStatusBadge = (status) => {
    const styles = {
      draft: 'bg-gray-600 text-gray-200',
      ready: 'bg-blue-600 text-blue-100',
      generating: 'bg-yellow-600 text-yellow-100',
      completed: 'bg-green-600 text-green-100',
      failed: 'bg-red-600 text-red-100',
    }
    const labels = {
      draft: 'Черновик',
      ready: 'Готов к генерации',
      generating: 'Генерация...',
      completed: 'Готов',
      failed: 'Ошибка',
    }
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${styles[status] || styles.draft}`}>
        {labels[status] || status}
      </span>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-yellow-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Мои гайды</h1>
          <p className="text-gray-400 text-sm mt-1">
            Автоматически сгенерированные из записей экрана
          </p>
        </div>
      </div>

      {guides.length === 0 ? (
        <div className="bg-gray-800 rounded-xl p-12 text-center">
          <div className="w-20 h-20 bg-gray-700 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-10 h-10 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
          </div>
          <h3 className="text-xl font-medium mb-2">Нет гайдов</h3>
          <p className="text-gray-400 mb-6 max-w-md mx-auto">
            Установите Chrome Extension и начните запись экрана.<br />
            После остановки записи гайд появится здесь автоматически.
          </p>
          
          <div className="bg-gray-900/50 rounded-lg p-6 max-w-lg mx-auto mb-6">
            <h4 className="font-medium mb-3">Как это работает:</h4>
            <ol className="text-left space-y-2 text-sm text-gray-400">
              <li className="flex items-start">
                <span className="w-6 h-6 bg-yellow-500 text-black rounded-full flex items-center justify-center text-xs font-bold mr-3 flex-shrink-0">1</span>
                <span>Установите расширение для Chrome</span>
              </li>
              <li className="flex items-start">
                <span className="w-6 h-6 bg-yellow-500 text-black rounded-full flex items-center justify-center text-xs font-bold mr-3 flex-shrink-0">2</span>
                <span>Нажмите "Начать запись" в расширении</span>
              </li>
              <li className="flex items-start">
                <span className="w-6 h-6 bg-yellow-500 text-black rounded-full flex items-center justify-center text-xs font-bold mr-3 flex-shrink-0">3</span>
                <span>Говорите и кликайте по интерфейсу</span>
              </li>
              <li className="flex items-start">
                <span className="w-6 h-6 bg-yellow-500 text-black rounded-full flex items-center justify-center text-xs font-bold mr-3 flex-shrink-0">4</span>
                <span>Остановите запись — гайд создастся автоматически!</span>
              </li>
            </ol>
          </div>
          
          <a
            href="https://chrome.google.com/webstore"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center px-6 py-3 bg-yellow-500 hover:bg-yellow-400 text-black rounded-lg font-medium transition-colors"
          >
            <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
            </svg>
            Установить расширение
          </a>
        </div>
      ) : (
        <div className="space-y-3">
          {guides.map((guide) => (
            <div
              key={guide.id || guide.uuid}
              className="bg-gray-800 rounded-lg p-4 hover:bg-gray-750 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-3">
                    <h3 className="font-medium truncate">{guide.title}</h3>
                    {getStatusBadge(guide.status)}
                  </div>
                  <div className="flex items-center space-x-4 mt-1 text-sm text-gray-400">
                    <span>{guide.steps?.length || 0} шагов</span>
                    <span>•</span>
                    <span>{new Date(guide.created_at).toLocaleDateString('ru-RU')}</span>
                  </div>
                </div>
                
                <div className="flex items-center space-x-2 ml-4">
                  {guide.status === 'draft' && (
                    <Link
                      to={`/guide/${guide.uuid}/edit`}
                      className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 rounded text-sm font-medium transition-colors"
                    >
                      Редактировать
                    </Link>
                  )}
                  {guide.status === 'ready' && (
                    <Link
                      to={`/guide/${guide.uuid}/shorts`}
                      className="px-3 py-1.5 bg-yellow-500 hover:bg-yellow-400 text-black rounded text-sm font-medium transition-colors"
                    >
                      Создать Shorts
                    </Link>
                  )}
                  {guide.status === 'completed' && (
                    <Link
                      to={`/guide/${guide.uuid}/shorts`}
                      className="px-3 py-1.5 bg-green-600 hover:bg-green-500 rounded text-sm font-medium transition-colors"
                    >
                      Смотреть Shorts
                    </Link>
                  )}
                  <button
                    onClick={() => handleDelete(guide.id)}
                    className="p-1.5 text-gray-400 hover:text-red-400 transition-colors"
                    title="Удалить"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default Dashboard
