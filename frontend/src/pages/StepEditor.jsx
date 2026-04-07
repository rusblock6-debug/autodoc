import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { guidesApi, stepsApi, storageApi, exportApi } from '../services/api'
function StepEditor() {
  const { guideId } = useParams()
  const navigate = useNavigate()
  const [guide, setGuide] = useState(null)
  const [steps, setSteps] = useState([])
  const [selectedStep, setSelectedStep] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [editingText, setEditingText] = useState(null)
  const [editingTitle, setEditingTitle] = useState(false)
  const [titleValue, setTitleValue] = useState('')
  const [showAnnotations, setShowAnnotations] = useState(false)
  const [annotations, setAnnotations] = useState([])
  const [drawingAnnotation, setDrawingAnnotation] = useState(null)
  const imageRef = useRef(null)
  
  // AI Enhancement state
  const [aiModal, setAiModal] = useState({ open: false, progress: 0, total: 0, message: '', status: 'idle' })
  const aiPollingRef = useRef(null)
  
  // Вкладки: 'steps' или 'video'
  const [activeTab, setActiveTab] = useState('steps')
  
  // Состояние генерации видео
  const [generating, setGenerating] = useState(false)
  const [progress, setProgress] = useState(0)
  const [progressMessage, setProgressMessage] = useState('')
  const [videoUrl, setVideoUrl] = useState(null)
  const [videoError, setVideoError] = useState(null)
  const [taskId, setTaskId] = useState(null)
  
  // Настройки TTS
  const [ttsSettings, setTtsSettings] = useState({
    ttsEngine: 'edge',
    ttsVoice: 'ru-RU-SvetlanaNeural',
    ttsSpeed: 1.0,
    ttsPitch: 0,
  })

  useEffect(() => { fetchGuide() }, [guideId])
  
  // Polling статуса задачи генерации видео
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
          setVideoError(status.error_message || 'Генерация не удалась')
          setGenerating(false)
          setTaskId(null)
          clearInterval(pollInterval)
        }
      } catch (err) {
        console.error('Failed to poll task status:', err)
      }
    }, 1000)
    
    return () => clearInterval(pollInterval)
  }, [taskId, generating, guide?.id])

  const fetchGuide = async () => {
    try {
      let data
      try { data = await guidesApi.getByUuid(guideId) } 
      catch { data = await guidesApi.getById(guideId) }
      setGuide(data)
      setSteps(data.steps || [])
      setTitleValue(data.title || '')
      if (data.steps?.length > 0) {
        setSelectedStep(data.steps[0])
        setAnnotations(data.steps[0].annotations || [])
      }
      
      // Проверяем наличие видео
      if (data.shorts_video_path && data.id) {
        setVideoUrl(`/api/v1/video/download/${data.id}`)
      }
    } catch (error) {
      // Игнорируем ошибки
    }
    finally { setLoading(false) }
  }

  const handleTextUpdate = async (stepId, newText) => {
    setSaving(true)
    try {
      await stepsApi.update(stepId, { edited_text: newText })
      setSteps(prev => prev.map(s => s.id === stepId ? { ...s, edited_text: newText } : s))
      if (selectedStep?.id === stepId) setSelectedStep(prev => ({ ...prev, edited_text: newText }))
    } catch {}
    finally { setSaving(false); setEditingText(null) }
  }

  const handleTitleUpdate = async () => {
    if (!titleValue.trim()) {
      setTitleValue(guide.title)
      setEditingTitle(false)
      return
    }
    
    setSaving(true)
    try {
      await guidesApi.update(guide.id, { title: titleValue.trim() })
      setGuide(prev => ({ ...prev, title: titleValue.trim() }))
    } catch (error) {
      setTitleValue(guide.title)
    } finally {
      setSaving(false)
      setEditingTitle(false)
    }
  }

  const handleTitleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleTitleUpdate()
    } else if (e.key === 'Escape') {
      setTitleValue(guide.title)
      setEditingTitle(false)
    }
  }

  const handleMarkerDrag = useCallback(async (stepId, newX, newY) => {
    setSteps(prev => prev.map(s => s.id === stepId ? { ...s, click_x: newX, click_y: newY } : s))
    if (selectedStep?.id === stepId) setSelectedStep(prev => ({ ...prev, click_x: newX, click_y: newY }))
    try { await stepsApi.update(stepId, { click_x: newX, click_y: newY }) } catch {}
  }, [selectedStep])

  const handleAddAnnotation = (type) => {
    const newAnnotation = {
      id: Date.now(),
      type,
      x: 100,
      y: 100,
      width: 200,
      height: 100,
      color: '#ed8d48'
    }
    const updated = [...annotations, newAnnotation]
    setAnnotations(updated)
    saveAnnotations(selectedStep.id, updated)
  }

  const handleUpdateAnnotation = (id, updates) => {
    const updated = annotations.map(a => a.id === id ? { ...a, ...updates } : a)
    setAnnotations(updated)
    saveAnnotations(selectedStep.id, updated)
  }

  const handleDeleteAnnotation = (id) => {
    const updated = annotations.filter(a => a.id !== id)
    setAnnotations(updated)
    saveAnnotations(selectedStep.id, updated)
  }

  const saveAnnotations = async (stepId, annotationsData) => {
    try {
      await stepsApi.update(stepId, { annotations: annotationsData })
      setSteps(prev => prev.map(s => s.id === stepId ? { ...s, annotations: annotationsData } : s))
    } catch (error) {
      // Игнорируем ошибки сохранения аннотаций
    }
  }

  const handleDeleteStep = async (stepId) => {
    if (!confirm('Удалить этот шаг?')) return
    try {
      await stepsApi.delete(stepId)
      const newSteps = steps.filter(s => s.id !== stepId)
      setSteps(newSteps)
      if (selectedStep?.id === stepId) setSelectedStep(newSteps[0] || null)
    } catch {}
  }

  const handleMoveStep = async (stepId, direction) => {
    const index = steps.findIndex(s => s.id === stepId)
    if (index === -1) return
    const newIndex = direction === 'up' ? index - 1 : index + 1
    if (newIndex < 0 || newIndex >= steps.length) return
    const newSteps = [...steps]
    const [moved] = newSteps.splice(index, 1)
    newSteps.splice(newIndex, 0, moved)
    setSteps(newSteps.map((s, i) => ({ ...s, step_number: i + 1 })))
    try { await stepsApi.reorder(guideId, newSteps.map(s => s.id)) } catch {}
  }

  const handleSaveGuide = async () => {
    setSaving(true)
    try { await guidesApi.update(guide.id, { status: 'draft' }) } catch {}
    finally { setSaving(false); navigate('/') }
  }

  const handleReadyForShorts = async () => {
    try { await guidesApi.update(guide.id, { status: 'ready' }); navigate(`/guide/${guideId}/shorts`) } catch {}
  }
  
  const handleGenerateVideo = async () => {
    if (!guide?.id) {
      setVideoError('Гайд не загружен')
      return
    }
    
    setGenerating(true)
    setVideoError(null)
    setProgress(0)
    setProgressMessage('Запуск генерации...')
    
    try {
      const response = await fetch(`/api/v1/video/generate/${guide.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tts_engine: ttsSettings.ttsEngine,
          tts_voice: ttsSettings.ttsVoice,
          tts_speed: ttsSettings.ttsSpeed,
          tts_pitch: ttsSettings.ttsPitch,
        })
      })
      
      const data = await response.json()
      
      if (data.task_id) {
        setTaskId(data.task_id)
        setProgressMessage('Задача в очереди...')
      } else {
        setVideoError('Не получен ID задачи')
        setGenerating(false)
      }
      
    } catch (error) {
      setVideoError(error.response?.data?.detail || 'Не удалось запустить генерацию')
      setGenerating(false)
    }
  }
  
  const handleDownloadVideo = async () => {
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
      setVideoError('Не удалось скачать видео')
    }
  }

  const handleExport = async (format) => {
    try {
      let blob, filename
      
      switch (format) {
        case 'pdf':
          blob = await exportApi.pdf(guide.id)
          filename = `${guide.title}.pdf`
          break
        case 'json':
          blob = await exportApi.json(guide.id)
          filename = `${guide.title}.json`
          break
        default:
          return
      }
      
      // Скачиваем файл
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      
    } catch (error) {
      alert(`Ошибка экспорта в ${format.toUpperCase()}`)
    }
  }

  const handleEnhanceWithAI = async () => {
    if (!guide?.id) return
    
    try {
      // Запускаем AI обработку
      const response = await guidesApi.enhanceWithAI(guide.id)
      
      // Открываем модалку
      setAiModal({
        open: true,
        progress: 0,
        total: response.total_steps || 0,
        message: 'Начинаем обработку...',
        status: 'processing'
      })
      
      // Начинаем polling статуса
      startAIPolling()
      
    } catch (error) {
      alert('Ошибка запуска AI обработки')
    }
  }

  const startAIPolling = () => {
    // Очищаем предыдущий polling если есть
    if (aiPollingRef.current) {
      clearInterval(aiPollingRef.current)
    }
    
    // Небольшая задержка перед первым запросом (даем Celery время записать в Redis)
    setTimeout(() => {
      // Polling каждые 2 секунды
      aiPollingRef.current = setInterval(async () => {
        try {
          const status = await guidesApi.getAIStatus(guide.id)
          
          setAiModal(prev => ({
            ...prev,
            progress: status.current || 0,
            total: status.total || prev.total,
            message: status.message || '',
            status: status.status
          }))
          
          // Если завершено или ошибка - останавливаем polling
          if (status.status === 'completed' || status.status === 'error') {
            clearInterval(aiPollingRef.current)
            aiPollingRef.current = null
            
            // Обновляем гайд
            setTimeout(() => {
              fetchGuide()
            }, 2000)
          }
          
        } catch (error) {
          console.error('AI status polling error:', error)
        }
      }, 2000)
    }, 1000) // Ждем 1 секунду перед первым запросом
  }

  const closeAIModal = () => {
    if (aiPollingRef.current) {
      clearInterval(aiPollingRef.current)
      aiPollingRef.current = null
    }
    setAiModal({ open: false, progress: 0, total: 0, message: '', status: 'idle' })
  }

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (aiPollingRef.current) {
        clearInterval(aiPollingRef.current)
      }
    }
  }, [])

  // Экспорт в data.json
  const [showExportModal, setShowExportModal] = useState(false)
  const [exportType, setExportType] = useState('descriptive') // 'descriptive' | 'instruction'
  
  // Формы для экспорта
  const [exportData, setExportData] = useState({
    title: '',
    subtitle: '',
    description: '',
    items: '',
    nav_title: ''
  })

  const openExportModal = (type) => {
    setExportType(type)
    setExportData({
      title: guide?.title || '',
      subtitle: '',
      description: '',
      items: '',
      nav_title: ''
    })
    setShowExportModal(true)
  }

  const handleExportSubmit = async () => {
    try {
      const itemsArray = exportData.items.split('\n').filter(line => line.trim())
      
      let endpoint, body
      
      if (exportType === 'descriptive') {
        endpoint = '/api/v1/data-json/add-to-descriptive'
        body = {
          guide_id: guideId,
          title: exportData.title,
          subtitle: exportData.subtitle,
          description: exportData.description,
          items: itemsArray
        }
      } else { // instruction
        endpoint = '/api/v1/data-json/add-to-instruction'
        body = {
          guide_id: guideId,
          title: exportData.title,
          nav_title: exportData.nav_title || exportData.title,
          description: exportData.description,
          items: itemsArray,
          steps: steps.map(step => ({
            text: step.annotation || `Шаг ${step.step_number}`,
            image: step.screenshot_path || ''
          }))
        }
      }
      
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })
      
      if (response.ok) {
        alert('✅ Успешно экспортировано!')
        setShowExportModal(false)
      } else {
        const error = await response.json()
        alert(`❌ Ошибка: ${error.detail || 'Не удалось экспортировать'}`)
      }
    } catch (error) {
      alert('❌ Ошибка экспорта: ' + error.message)
    }
  }

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px' }}>
      <div style={{ width: '24px', height: '24px', border: '2px solid #e0e0e0', borderTopColor: '#ed8d48', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )

  if (!guide) return <div style={{ padding: '48px', textAlign: 'center', color: '#666' }}>Гайд не найден</div>

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ 
        padding: '16px 24px', 
        backgroundColor: '#fff', 
        borderBottom: '1px solid #e0e0e0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <div>
          {editingTitle ? (
            <input
              type="text"
              value={titleValue}
              onChange={(e) => setTitleValue(e.target.value)}
              onBlur={handleTitleUpdate}
              onKeyDown={handleTitleKeyPress}
              autoFocus
              style={{
                fontFamily: 'Montserrat, sans-serif',
                fontSize: '16px',
                fontWeight: 600,
                color: '#333',
                margin: 0,
                padding: '4px 8px',
                border: '1px solid #ed8d48',
                borderRadius: '4px',
                backgroundColor: '#fff',
                outline: 'none',
                minWidth: '200px'
              }}
            />
          ) : (
            <h1 
              onClick={() => setEditingTitle(true)}
              style={{ 
                fontFamily: 'Montserrat, sans-serif', 
                fontSize: '16px', 
                fontWeight: 600, 
                color: '#333', 
                margin: 0,
                cursor: 'pointer',
                padding: '4px 8px',
                borderRadius: '4px',
                transition: 'background-color 0.15s'
              }}
              onMouseOver={(e) => e.target.style.backgroundColor = '#f5f5f5'}
              onMouseOut={(e) => e.target.style.backgroundColor = 'transparent'}
              title="Нажмите для редактирования"
            >
              {guide.title}
            </h1>
          )}
          <p style={{ fontFamily: 'Roboto, sans-serif', fontSize: '12px', color: '#999', marginTop: '2px' }}>{steps.length} шагов</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {saving && <span style={{ fontSize: '12px', color: '#999' }}>Сохранение...</span>}
          
          {/* AI Enhancement Button */}
          <AIButton onClick={handleEnhanceWithAI} title="Улучшить с помощью AI" />
          
          {/* Кнопки экспорта в data.json - строгие черно-белые */}
          <button 
            onClick={() => openExportModal('descriptive')} 
            style={{ 
              padding: '6px 12px', 
              fontFamily: 'Montserrat, sans-serif', 
              fontSize: '11px', 
              fontWeight: 600, 
              textTransform: 'uppercase', 
              letterSpacing: '0.5px', 
              backgroundColor: '#fff', 
              color: '#333', 
              border: '1px solid #ddd', 
              borderRadius: '4px', 
              cursor: 'pointer'
            }}
            title="Экспорт в Обзор"
          >
            Обзор
          </button>
          
          <button 
            onClick={() => openExportModal('instruction')} 
            style={{ 
              padding: '6px 12px', 
              fontFamily: 'Montserrat, sans-serif', 
              fontSize: '11px', 
              fontWeight: 600, 
              textTransform: 'uppercase', 
              letterSpacing: '0.5px', 
              backgroundColor: '#fff', 
              color: '#333', 
              border: '1px solid #ddd', 
              borderRadius: '4px', 
              cursor: 'pointer'
            }}
            title="Экспорт в Инструкции"
          >
            Инструкции
          </button>
          
          <button onClick={() => navigate('/')} style={{ padding: '8px 16px', fontFamily: 'Montserrat, sans-serif', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.3px', backgroundColor: '#fff', color: '#666', border: '1px solid #e0e0e0', borderRadius: '4px', cursor: 'pointer' }}>
            ← Назад
          </button>
          <button onClick={() => handleExport('pdf')} style={{ padding: '8px 16px', fontFamily: 'Montserrat, sans-serif', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.3px', backgroundColor: '#e53e3e', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
            PDF
          </button>
          <button onClick={() => handleExport('json')} style={{ padding: '8px 16px', fontFamily: 'Montserrat, sans-serif', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.3px', backgroundColor: '#3b82f6', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
            JSON
          </button>
        </div>
      </div>

      {/* Main */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        {/* Steps sidebar - light */}
        <div style={{ width: '320px', backgroundColor: '#fff', borderRight: '1px solid #e0e0e0', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid #e0e0e0' }}>
            <span style={{ fontFamily: 'Montserrat, sans-serif', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: '#999' }}>Шаги</span>
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {steps.map((step, index) => (
              <StepCard key={step.id} step={step} index={index} isSelected={selectedStep?.id === step.id && activeTab === 'steps'} isFirst={index === 0} isLast={index === steps.length - 1} isEditing={editingText === step.id}
                onSelect={() => { setActiveTab('steps'); setSelectedStep(step); setAnnotations(step.annotations || []) }} onEdit={() => setEditingText(step.id)} onSave={(text) => handleTextUpdate(step.id, text)} onCancel={() => setEditingText(null)}
                onDelete={() => handleDeleteStep(step.id)} onMoveUp={() => handleMoveStep(step.id, 'up')} onMoveDown={() => handleMoveStep(step.id, 'down')} />
            ))}
            
            {/* ВИДЕО - последний элемент списка */}
            <div
              onClick={() => setActiveTab('video')}
              style={{
                padding: '16px 20px',
                borderBottom: '1px solid #e0e0e0',
                cursor: 'pointer',
                backgroundColor: activeTab === 'video' ? '#fff5e6' : '#fff',
                borderLeft: activeTab === 'video' ? '3px solid #ed8d48' : '3px solid transparent',
                transition: 'all 0.15s'
              }}
              onMouseOver={(e) => { if (activeTab !== 'video') e.currentTarget.style.backgroundColor = '#fafafa' }}
              onMouseOut={(e) => { if (activeTab !== 'video') e.currentTarget.style.backgroundColor = '#fff' }}
            >
              <div style={{
                fontFamily: 'Montserrat, sans-serif',
                fontSize: '13px',
                fontWeight: 600,
                color: activeTab === 'video' ? '#ed8d48' : '#333'
              }}>
                ВИДЕО
              </div>
            </div>
          </div>
        </div>

        {/* Preview / Video Panel */}
        <div style={{ flex: 1, backgroundColor: '#fafafa', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {activeTab === 'video' ? (
            <VideoPanel
              guide={guide}
              generating={generating}
              progress={progress}
              progressMessage={progressMessage}
              videoUrl={videoUrl}
              videoError={videoError}
              ttsSettings={ttsSettings}
              setTtsSettings={setTtsSettings}
              onGenerate={handleGenerateVideo}
              onDownload={handleDownloadVideo}
            />
          ) : (
            <>
              <div style={{ padding: '12px 20px', backgroundColor: '#fff', borderBottom: '1px solid #e0e0e0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontFamily: 'Roboto, sans-serif', fontSize: '12px', color: '#666' }}>
                  Шаг {selectedStep?.step_number || '-'}
                </span>
                {/* Toolbar - right side */}
                {selectedStep && (
              <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                {/* Маркер */}
                {selectedStep.click_x > 0 && selectedStep.click_y > 0 ? (
                  <button
                    onClick={() => handleMarkerDrag(selectedStep.id, 0, 0)}
                    title="Убрать маркер"
                    style={{
                      width: '28px',
                      height: '28px',
                      backgroundColor: '#ed8d48',
                      border: 'none',
                      borderRadius: '50%',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '10px',
                      fontWeight: 600,
                      color: '#fff',
                      fontFamily: 'Montserrat, sans-serif'
                    }}
                  >
                    {selectedStep.step_number}
                  </button>
                ) : (
                  <button
                    onClick={() => {
                      const centerX = Math.floor((selectedStep?.screenshot_width || 1920) / 2)
                      const centerY = Math.floor((selectedStep?.screenshot_height || 1080) / 2)
                      handleMarkerDrag(selectedStep.id, centerX, centerY)
                    }}
                    title="Добавить маркер"
                    style={{
                      width: '28px',
                      height: '28px',
                      backgroundColor: 'transparent',
                      border: '2px dashed #ed8d48',
                      borderRadius: '50%',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '10px',
                      fontWeight: 600,
                      color: '#ed8d48',
                      fontFamily: 'Montserrat, sans-serif'
                    }}
                  >
                    {selectedStep.step_number}
                  </button>
                )}
                
                {/* Прямоугольник */}
                <button 
                  onClick={() => handleAddAnnotation('rect')} 
                  title="Добавить прямоугольник"
                  style={{ 
                    width: '28px',
                    height: '28px',
                    backgroundColor: 'transparent',
                    border: '1px solid #e0e0e0',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '14px',
                    color: '#ed8d48'
                  }}
                >
                  ▭
                </button>
                
                {/* Очистить все */}
                {annotations.length > 0 && (
                  <button 
                    onClick={() => { setAnnotations([]); saveAnnotations(selectedStep.id, []) }} 
                    title="Очистить все аннотации"
                    style={{ 
                      width: '28px',
                      height: '28px',
                      backgroundColor: 'transparent',
                      border: '1px solid #e0e0e0',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '12px',
                      color: '#999'
                    }}
                  >
                    🗑
                  </button>
                )}
              </div>
            )}
          </div>
          <div style={{ flex: 1, overflow: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
            {selectedStep?.screenshot_path ? (
              <div style={{ position: 'relative', display: 'inline-block' }}>
                <img ref={imageRef} src={storageApi.getScreenshotUrl(selectedStep.screenshot_path)} alt="" style={{ maxWidth: '100%', maxHeight: 'calc(100vh - 300px)', borderRadius: '4px', boxShadow: '0 2px 12px rgba(0,0,0,0.1)' }} draggable={false} />
                
                {/* Серый оверлей с вырезами под аннотации */}
                {annotations.length > 0 && (
                  <DarkOverlay 
                    annotations={annotations}
                    imageRef={imageRef}
                    viewportWidth={selectedStep.screenshot_width}
                    viewportHeight={selectedStep.screenshot_height}
                  />
                )}
                
                <DraggableMarker 
                  x={selectedStep.click_x} 
                  y={selectedStep.click_y} 
                  viewportWidth={selectedStep.screenshot_width}
                  viewportHeight={selectedStep.screenshot_height}
                  imageRef={imageRef} 
                  onDragEnd={(x, y) => handleMarkerDrag(selectedStep.id, x, y)} 
                />
                {annotations.map(ann => (
                  <DraggableAnnotation
                    key={ann.id}
                    annotation={ann}
                    imageRef={imageRef}
                    viewportWidth={selectedStep.screenshot_width}
                    viewportHeight={selectedStep.screenshot_height}
                    onUpdate={(updates) => handleUpdateAnnotation(ann.id, updates)}
                    onDelete={() => handleDeleteAnnotation(ann.id)}
                  />
                ))}
              </div>
            ) : (
              <div style={{ color: '#999', padding: '48px' }}>Нет скриншота</div>
            )}
          </div>
            </>
          )}
        </div>
      </div>
      
      {/* Модальное окно экспорта */}
      <ExportModal
        show={showExportModal}
        onClose={() => setShowExportModal(false)}
        type={exportType}
        data={exportData}
        setData={setExportData}
        onSubmit={handleExportSubmit}
      />
      
      {/* AI Enhancement Modal */}
      {aiModal.open && (
        <AIModal 
          progress={aiModal.progress}
          total={aiModal.total}
          message={aiModal.message}
          status={aiModal.status}
          onClose={closeAIModal}
        />
      )}
    </div>
  )
}

// Компонент серого оверлея с вырезами под аннотации
function DarkOverlay({ annotations, imageRef, viewportWidth, viewportHeight }) {
  const getImageDimensions = () => {
    if (!imageRef.current) return { width: 0, height: 0 }
    return {
      width: imageRef.current.clientWidth || 0,
      height: imageRef.current.clientHeight || 0
    }
  }

  const convertToDisplayCoords = (annotation) => {
    if (!imageRef.current) return { x: 0, y: 0, width: 0, height: 0 }
    
    const dw = imageRef.current.clientWidth || 1
    const dh = imageRef.current.clientHeight || 1
    const vw = viewportWidth || imageRef.current.naturalWidth || dw
    const vh = viewportHeight || imageRef.current.naturalHeight || dh
    
    return {
      x: (annotation.x / vw) * dw,
      y: (annotation.y / vh) * dh,
      width: (annotation.width / vw) * dw,
      height: (annotation.height / vh) * dh
    }
  }

  const { width: imgWidth, height: imgHeight } = getImageDimensions()
  
  if (imgWidth === 0 || imgHeight === 0) return null

  return (
    <svg
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        borderRadius: '4px',
        overflow: 'hidden'
      }}
      viewBox={`0 0 ${imgWidth} ${imgHeight}`}
      preserveAspectRatio="none"
    >
      <defs>
        <mask id="cutout-mask">
          {/* Белый фон = видимая область */}
          <rect x="0" y="0" width={imgWidth} height={imgHeight} fill="white" />
          
          {/* Черные прямоугольники = вырезы (прозрачные области) */}
          {annotations.map(ann => {
            const pos = convertToDisplayCoords(ann)
            return (
              <rect
                key={ann.id}
                x={pos.x}
                y={pos.y}
                width={pos.width}
                height={pos.height}
                fill="black"
              />
            )
          })}
        </mask>
      </defs>
      
      {/* Серый оверлей с маской */}
      <rect
        x="0"
        y="0"
        width={imgWidth}
        height={imgHeight}
        fill="rgba(0, 0, 0, 0.4)"
        mask="url(#cutout-mask)"
      />
    </svg>
  )
}

function DraggableMarker({ x, y, viewportWidth, viewportHeight, imageRef, onDragEnd }) {
  const [isDragging, setIsDragging] = useState(false)
  const [position, setPosition] = useState({ x: x || 0, y: y || 0 })

  useEffect(() => { setPosition({ x: x || 0, y: y || 0 }) }, [x, y])

  const handleMouseDown = (e) => {
    e.preventDefault()
    setIsDragging(true)
    const handleMouseMove = (moveEvent) => {
      if (!imageRef.current) return
      const rect = imageRef.current.getBoundingClientRect()
      const vw = viewportWidth || imageRef.current.naturalWidth
      const vh = viewportHeight || imageRef.current.naturalHeight
      setPosition({
        x: Math.max(0, Math.min(vw, Math.round((moveEvent.clientX - rect.left) * (vw / rect.width)))),
        y: Math.max(0, Math.min(vh, Math.round((moveEvent.clientY - rect.top) * (vh / rect.height))))
      })
    }
    const handleMouseUp = () => {
      setIsDragging(false)
      onDragEnd(position.x, position.y)
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }

  const getPos = () => {
    if (!imageRef.current) return { left: 0, top: 0 }
    const dw = imageRef.current.clientWidth || 1
    const dh = imageRef.current.clientHeight || 1
    const vw = viewportWidth || imageRef.current.naturalWidth || dw
    const vh = viewportHeight || imageRef.current.naturalHeight || dh
    return { left: ((position.x || 0) / vw) * dw, top: ((position.y || 0) / vh) * dh }
  }

  const pos = getPos()
  
  // Не показываем маркер если координаты 0,0 (удалён)
  if ((x === 0 && y === 0) || !x || !y) {
    return null
  }
  
  return (
    <div onMouseDown={handleMouseDown} style={{
      position: 'absolute', left: pos.left, top: pos.top,
      width: '36px', height: '36px', marginLeft: '-18px', marginTop: '-18px',
      cursor: 'move', transform: isDragging ? 'scale(1.1)' : 'scale(1)', transition: 'transform 0.1s'
    }}>
      <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', border: '3px solid #ed8d48', backgroundColor: 'rgba(237, 141, 72, 0.2)', animation: 'pulse 2s infinite' }} />
      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#ed8d48' }} />
      </div>
      <style>{`@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.6; } }`}</style>
    </div>
  )
}

function DraggableAnnotation({ annotation, imageRef, viewportWidth, viewportHeight, onUpdate, onDelete }) {
  const [isDragging, setIsDragging] = useState(false)
  const [isResizing, setIsResizing] = useState(false)
  const [localPos, setLocalPos] = useState({ x: annotation.x, y: annotation.y, width: annotation.width, height: annotation.height })
  const isMountedRef = useRef(true)
  const prevAnnotationIdRef = useRef(annotation.id)

  useEffect(() => {
    // Обновляем localPos при монтировании или при смене аннотации (переключение шагов)
    if (prevAnnotationIdRef.current !== annotation.id) {
      setLocalPos({ x: annotation.x, y: annotation.y, width: annotation.width, height: annotation.height })
      prevAnnotationIdRef.current = annotation.id
    }
  }, [annotation.id, annotation.x, annotation.y, annotation.width, annotation.height])

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
    }
  }, [])

  const handleMouseDown = (e, action) => {
    e.preventDefault()
    e.stopPropagation()
    
    if (action === 'resize') {
      setIsResizing(true)
    } else {
      setIsDragging(true)
    }
    
    const startMousePos = {
      x: e.clientX,
      y: e.clientY
    }
    const startAnnotationPos = { ...localPos }
    let currentPos = { ...localPos }
    
    const handleMouseMove = (moveEvent) => {
      if (!imageRef.current) return
      const rect = imageRef.current.getBoundingClientRect()
      const vw = viewportWidth || imageRef.current.naturalWidth
      const vh = viewportHeight || imageRef.current.naturalHeight
      
      const deltaX = (moveEvent.clientX - startMousePos.x) * (vw / rect.width)
      const deltaY = (moveEvent.clientY - startMousePos.y) * (vh / rect.height)
      
      if (action === 'resize') {
        const newWidth = Math.max(30, startAnnotationPos.width + deltaX)
        const newHeight = Math.max(30, startAnnotationPos.height + deltaY)
        currentPos = { ...currentPos, width: newWidth, height: newHeight }
        setLocalPos(currentPos)
      } else {
        const newX = Math.max(0, Math.min(vw - startAnnotationPos.width, startAnnotationPos.x + deltaX))
        const newY = Math.max(0, Math.min(vh - startAnnotationPos.height, startAnnotationPos.y + deltaY))
        currentPos = { ...currentPos, x: newX, y: newY }
        setLocalPos(currentPos)
      }
    }
    
    const handleMouseUp = () => {
      setIsDragging(false)
      setIsResizing(false)
      if (isMountedRef.current) {
        onUpdate(currentPos)
      }
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
    
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }

  const getPos = () => {
    if (!imageRef.current) return { left: 0, top: 0, width: 0, height: 0 }
    const dw = imageRef.current.clientWidth || 1
    const dh = imageRef.current.clientHeight || 1
    const vw = viewportWidth || imageRef.current.naturalWidth || dw
    const vh = viewportHeight || imageRef.current.naturalHeight || dh
    return {
      left: (localPos.x / vw) * dw,
      top: (localPos.y / vh) * dh,
      width: (localPos.width / vw) * dw,
      height: (localPos.height / vh) * dh
    }
  }

  const pos = getPos()

  return (
    <div
      onMouseDown={(e) => handleMouseDown(e, 'move')}
      style={{
        position: 'absolute',
        left: pos.left,
        top: pos.top,
        width: pos.width,
        height: pos.height,
        border: `3px solid ${annotation.color}`,
        borderRadius: '4px',
        backgroundColor: 'transparent',
        cursor: isDragging ? 'grabbing' : 'grab',
        boxSizing: 'border-box',
        transition: isDragging || isResizing ? 'none' : 'all 0.1s'
      }}
    >
      <button
        onClick={(e) => { e.stopPropagation(); onDelete() }}
        style={{
          position: 'absolute',
          top: '-18px',
          right: '-18px',
          width: '36px',
          height: '36px',
          borderRadius: '50%',
          backgroundColor: '#ed8d48',
          color: '#fff',
          border: '3px solid #fff',
          cursor: 'pointer',
          fontSize: '11px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontWeight: 600,
          fontFamily: 'Montserrat, sans-serif',
          boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
        }}
      >
        ×
      </button>
      <div
        onMouseDown={(e) => handleMouseDown(e, 'resize')}
        style={{
          position: 'absolute',
          bottom: '-5px',
          right: '-5px',
          width: '10px',
          height: '10px',
          backgroundColor: '#ed8d48',
          border: '2px solid #fff',
          borderRadius: '50%',
          cursor: 'nwse-resize'
        }}
      />
    </div>
  )
}

function StepCard({ step, index, isSelected, isFirst, isLast, isEditing, onSelect, onEdit, onSave, onCancel, onDelete, onMoveUp, onMoveDown }) {
  const [editText, setEditText] = useState(step.edited_text || step.normalized_text || `Шаг ${index + 1}`)
  const textareaRef = useRef(null)

  useEffect(() => { if (isEditing && textareaRef.current) { textareaRef.current.focus(); textareaRef.current.select() } }, [isEditing])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && e.ctrlKey) onSave(editText)
    else if (e.key === 'Escape') { setEditText(step.edited_text || step.normalized_text || `Шаг ${index + 1}`); onCancel() }
  }

  const displayText = step.edited_text || step.normalized_text || `Шаг ${index + 1}`

  return (
    <div onClick={onSelect} style={{
      padding: '10px 16px',
      borderBottom: '1px solid #f0f0f0',
      cursor: 'pointer',
      backgroundColor: isSelected ? 'rgba(237, 141, 72, 0.08)' : '#fff',
      borderLeft: isSelected ? '3px solid #ed8d48' : '3px solid transparent',
      transition: 'all 0.15s'
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
        <div style={{
          width: '22px', height: '22px', borderRadius: '50%',
          backgroundColor: isSelected ? '#ed8d48' : '#e0e0e0',
          color: isSelected ? '#fff' : '#666',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '11px', fontFamily: 'Montserrat, sans-serif', fontWeight: 600, flexShrink: 0
        }}>
          {index + 1}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          {isEditing ? (
            <div>
              <textarea ref={textareaRef} value={editText} onChange={(e) => setEditText(e.target.value)} onKeyDown={handleKeyDown}
                style={{ width: '100%', padding: '6px 8px', fontSize: '12px', border: '1px solid #e0e0e0', borderRadius: '4px', backgroundColor: '#fff', color: '#333', resize: 'none', outline: 'none' }} rows={2} />
              <div style={{ display: 'flex', gap: '6px', marginTop: '6px' }}>
                <button onClick={(e) => { e.stopPropagation(); onSave(editText) }} style={{ padding: '4px 10px', fontSize: '10px', fontWeight: 600, backgroundColor: '#4caf50', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>OK</button>
                <button onClick={(e) => { e.stopPropagation(); onCancel() }} style={{ padding: '4px 10px', fontSize: '10px', fontWeight: 600, backgroundColor: '#e0e0e0', color: '#666', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>Отмена</button>
              </div>
            </div>
          ) : (
            <p style={{ fontFamily: 'Roboto, sans-serif', fontSize: '12px', color: '#333', margin: 0, lineHeight: 1.4, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{displayText}</p>
          )}
        </div>
        {isSelected && !isEditing && (
          <div style={{ display: 'flex', gap: '2px' }}>
            <SmallBtn onClick={onEdit} icon="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
            {!isFirst && <SmallBtn onClick={onMoveUp} icon="M5 15l7-7 7 7" />}
            {!isLast && <SmallBtn onClick={onMoveDown} icon="M19 9l-7 7-7-7" />}
            <SmallBtn onClick={onDelete} icon="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" danger />
          </div>
        )}
      </div>
    </div>
  )
}

// Модальное окно для экспорта в data.json
function ExportModal({ show, onClose, type, data, setData, onSubmit }) {
  if (!show) return null
  
  const titles = {
    descriptive: { title: 'Обзор', color: '#ed8d48' },
    instruction: { title: 'Инструкции', color: '#ed8d48' }
  }
  
  const config = titles[type]
  
  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(0,0,0,0.75)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999,
      padding: '20px'
    }} onClick={onClose}>
      <div style={{
        backgroundColor: '#fff',
        borderRadius: '12px',
        maxWidth: '600px',
        width: '100%',
        maxHeight: '90vh',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column'
      }} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div style={{
          backgroundColor: config.color,
          color: '#333',
          padding: '20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '2px solid #333'
        }}>
          <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 600 }}>
            Экспорт: {config.title}
          </h2>
          <button onClick={onClose} style={{
            background: 'none',
            border: 'none',
            color: '#333',
            fontSize: '28px',
            cursor: 'pointer',
            lineHeight: 1,
            padding: 0,
            width: '30px',
            height: '30px'
          }}>×</button>
        </div>
        
        {/* Body */}
        <div style={{ padding: '20px', overflowY: 'auto', flex: 1 }}>
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: 600, color: '#333', fontSize: '14px' }}>Заголовок *</label>
            <input
              type="text"
              value={data.title}
              onChange={e => setData({ ...data, title: e.target.value })}
              style={{ width: '100%', padding: '10px', border: '1px solid #ddd', borderRadius: '6px', fontSize: '14px' }}
              placeholder="Введите заголовок"
            />
          </div>
      
          {type === 'descriptive' && (
            <>
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: 600, color: '#333', fontSize: '14px' }}>Подзаголовок</label>
                <input
                  type="text"
                  value={data.subtitle}
                  onChange={e => setData({ ...data, subtitle: e.target.value })}
                  style={{ width: '100%', padding: '10px', border: '1px solid #ddd', borderRadius: '6px', fontSize: '14px' }}
                  placeholder="Введите подзаголовок"
                />
              </div>
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: 600, color: '#333', fontSize: '14px' }}>Подробное описание *</label>
                <textarea
                  value={data.description}
                  onChange={e => setData({ ...data, description: e.target.value })}
                  rows={4}
                  style={{ width: '100%', padding: '10px', border: '1px solid #ddd', borderRadius: '6px', fontSize: '14px', resize: 'vertical' }}
                  placeholder="Опишите особенности раздела"
                />
              </div>
            </>
          )}
          
          {type === 'instruction' && (
            <>
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: 600, color: '#333', fontSize: '14px' }}>Название для навигации</label>
                <input
                  type="text"
                  value={data.nav_title}
                  onChange={e => setData({ ...data, nav_title: e.target.value })}
                  style={{ width: '100%', padding: '10px', border: '1px solid #ddd', borderRadius: '6px', fontSize: '14px' }}
                  placeholder={data.title}
                />
              </div>
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: 600, color: '#333', fontSize: '14px' }}>Описание *</label>
                <textarea
                  value={data.description}
                  onChange={e => setData({ ...data, description: e.target.value })}
                  rows={4}
                  style={{ width: '100%', padding: '10px', border: '1px solid #ddd', borderRadius: '6px', fontSize: '14px', resize: 'vertical' }}
                  placeholder="Опишите инструкцию"
                />
              </div>
            </>
          )}
        </div>
        
        {/* Footer */}
        <div style={{
          padding: '20px',
          borderTop: '1px solid #e0e0e0',
          display: 'flex',
          gap: '10px',
          justifyContent: 'flex-end'
        }}>
          <button onClick={onClose} style={{
            padding: '12px 24px',
            backgroundColor: '#adb5bd',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '15px',
            fontWeight: 600
          }}>Отмена</button>
          <button onClick={onSubmit} style={{
            padding: '12px 24px',
            backgroundColor: config.color,
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '15px',
            fontWeight: 600
          }}>Экспортировать</button>
        </div>
      </div>
    </div>
  )
}

function SmallBtn({ onClick, icon, danger }) {
  const [hover, setHover] = useState(false)
  return (
    <button onClick={(e) => { e.stopPropagation(); onClick() }}
      onMouseOver={() => setHover(true)} onMouseOut={() => setHover(false)}
      style={{ width: '22px', height: '22px', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'transparent', border: 'none', cursor: 'pointer', color: hover ? (danger ? '#d32f2f' : '#ed8d48') : '#999', transition: 'color 0.15s', borderRadius: '4px' }}>
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d={icon} />
      </svg>
    </button>
  )
}

// Компонент панели генерации видео
function VideoPanel({ guide, generating, progress, progressMessage, videoUrl, videoError, ttsSettings, setTtsSettings, onGenerate, onDownload }) {
  const voices = {
    edge: [
      { value: 'ru-RU-SvetlanaNeural', label: 'Светлана' },
      { value: 'ru-RU-DmitryNeural', label: 'Дмитрий' },
      { value: 'ru-RU-DariyaNeural', label: 'Дарья' },
    ],
    chatterbox: [
      { value: 'neutral', label: 'Нейтральный' },
    ]
  }
  
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '12px 20px', backgroundColor: '#fff', borderBottom: '1px solid #e0e0e0' }}>
        <h3 style={{ fontFamily: 'Montserrat, sans-serif', fontSize: '14px', fontWeight: 600, color: '#333', margin: 0 }}>
          Видео
        </h3>
      </div>
      
      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Превью видео */}
        {videoUrl && !generating && (
          <div style={{ backgroundColor: '#000', borderRadius: '8px', overflow: 'hidden', aspectRatio: '16/9', maxWidth: '800px' }}>
            <video src={videoUrl} controls style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
          </div>
        )}
        
        {/* Прогресс генерации */}
        {generating && (
          <div style={{ backgroundColor: '#fff', border: '1px solid #e0e0e0', borderRadius: '8px', padding: '24px', textAlign: 'center', maxWidth: '600px' }}>
            <div style={{ width: '60px', height: '60px', margin: '0 auto 16px', border: '4px solid #ed8d48', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
            <p style={{ fontFamily: 'Montserrat, sans-serif', fontSize: '14px', fontWeight: 600, color: '#ed8d48', marginBottom: '12px' }}>
              Генерация видео...
            </p>
            <div style={{ width: '100%', height: '6px', backgroundColor: '#f5f5f5', borderRadius: '3px', overflow: 'hidden', marginBottom: '12px' }}>
              <div style={{ width: `${progress}%`, height: '100%', backgroundColor: '#ed8d48', transition: 'width 0.3s' }} />
            </div>
            <p style={{ fontFamily: 'Roboto, sans-serif', fontSize: '12px', color: '#666', marginBottom: '4px' }}>
              {progressMessage}
            </p>
            <p style={{ fontFamily: 'Roboto, sans-serif', fontSize: '11px', color: '#999' }}>
              {progress}%
            </p>
          </div>
        )}
        
        {/* Ошибка */}
        {videoError && (
          <div style={{ backgroundColor: '#fee', border: '1px solid #fcc', borderRadius: '8px', padding: '16px', maxWidth: '600px' }}>
            <p style={{ fontFamily: 'Roboto, sans-serif', fontSize: '12px', color: '#c33', margin: 0 }}>{videoError}</p>
          </div>
        )}
        
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', maxWidth: '800px' }}>
          {/* Настройки TTS */}
          <div style={{ backgroundColor: '#fff', border: '1px solid #e0e0e0', borderRadius: '8px', padding: '16px' }}>
            <h4 style={{ fontFamily: 'Montserrat, sans-serif', fontSize: '12px', fontWeight: 600, marginBottom: '16px', color: '#333' }}>
              Настройки озвучки
            </h4>
            
            {/* Движок */}
            <div style={{ marginBottom: '16px' }}>
              <label style={{ fontFamily: 'Roboto, sans-serif', fontSize: '11px', color: '#666', display: 'block', marginBottom: '8px' }}>
                Движок
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <button
                  onClick={() => setTtsSettings(s => ({ ...s, ttsEngine: 'edge', ttsVoice: 'ru-RU-SvetlanaNeural' }))}
                  disabled={generating}
                  style={{
                    padding: '10px',
                    fontFamily: 'Montserrat, sans-serif',
                    fontSize: '11px',
                    fontWeight: 600,
                    backgroundColor: ttsSettings.ttsEngine === 'edge' ? '#ed8d48' : '#fff',
                    color: ttsSettings.ttsEngine === 'edge' ? '#fff' : '#666',
                    border: '1px solid #e0e0e0',
                    borderRadius: '4px',
                    cursor: generating ? 'not-allowed' : 'pointer',
                    transition: 'all 0.2s'
                  }}
                >
                  Edge TTS
                </button>
                <button
                  onClick={() => setTtsSettings(s => ({ ...s, ttsEngine: 'chatterbox', ttsVoice: 'neutral' }))}
                  disabled={generating}
                  style={{
                    padding: '10px',
                    fontFamily: 'Montserrat, sans-serif',
                    fontSize: '11px',
                    fontWeight: 600,
                    backgroundColor: ttsSettings.ttsEngine === 'chatterbox' ? '#ed8d48' : '#fff',
                    color: ttsSettings.ttsEngine === 'chatterbox' ? '#fff' : '#666',
                    border: '1px solid #e0e0e0',
                    borderRadius: '4px',
                    cursor: generating ? 'not-allowed' : 'pointer',
                    transition: 'all 0.2s'
                  }}
                >
                  Chatterbox
                </button>
              </div>
            </div>
            
            {/* Голос */}
            <div style={{ marginBottom: '16px' }}>
              <label style={{ fontFamily: 'Roboto, sans-serif', fontSize: '11px', color: '#666', display: 'block', marginBottom: '8px' }}>
                Голос
              </label>
              <select
                value={ttsSettings.ttsVoice}
                onChange={(e) => setTtsSettings(s => ({ ...s, ttsVoice: e.target.value }))}
                disabled={generating}
                style={{
                  width: '100%',
                  padding: '10px',
                  fontFamily: 'Roboto, sans-serif',
                  fontSize: '12px',
                  backgroundColor: '#fff',
                  border: '1px solid #e0e0e0',
                  borderRadius: '4px',
                  cursor: generating ? 'not-allowed' : 'pointer'
                }}
              >
                {voices[ttsSettings.ttsEngine].map(voice => (
                  <option key={voice.value} value={voice.value}>{voice.label}</option>
                ))}
              </select>
            </div>
            
            {/* Скорость */}
            <div style={{ marginBottom: '16px' }}>
              <label style={{ fontFamily: 'Roboto, sans-serif', fontSize: '11px', color: '#666', display: 'block', marginBottom: '8px' }}>
                Скорость: {ttsSettings.ttsSpeed.toFixed(1)}x
              </label>
              <input
                type="range"
                min="0.5"
                max="2.0"
                step="0.1"
                value={ttsSettings.ttsSpeed}
                onChange={(e) => setTtsSettings(s => ({ ...s, ttsSpeed: parseFloat(e.target.value) }))}
                disabled={generating}
                style={{ width: '100%' }}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'Roboto, sans-serif', fontSize: '10px', color: '#999', marginTop: '4px' }}>
                <span>0.5x</span>
                <span>1.0x</span>
                <span>2.0x</span>
              </div>
            </div>
            
            {/* Тембр (только для Edge) */}
            {ttsSettings.ttsEngine === 'edge' && (
              <div style={{ marginBottom: '16px' }}>
                <label style={{ fontFamily: 'Roboto, sans-serif', fontSize: '11px', color: '#666', display: 'block', marginBottom: '8px' }}>
                  Тембр: {ttsSettings.ttsPitch > 0 ? '+' : ''}{ttsSettings.ttsPitch}
                </label>
                <input
                  type="range"
                  min="-20"
                  max="20"
                  step="1"
                  value={ttsSettings.ttsPitch}
                  onChange={(e) => setTtsSettings(s => ({ ...s, ttsPitch: parseInt(e.target.value) }))}
                  disabled={generating}
                  style={{ width: '100%' }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'Roboto, sans-serif', fontSize: '10px', color: '#999', marginTop: '4px' }}>
                  <span>Низкий</span>
                  <span>Норма</span>
                  <span>Высокий</span>
                </div>
              </div>
            )}
          </div>
          
          {/* Действия */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <button
              onClick={onGenerate}
              disabled={generating}
              style={{
                padding: '16px',
                fontFamily: 'Montserrat, sans-serif',
                fontSize: '12px',
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
                backgroundColor: generating ? '#ccc' : '#ed8d48',
                color: '#fff',
                border: 'none',
                borderRadius: '4px',
                cursor: generating ? 'not-allowed' : 'pointer',
                transition: 'all 0.2s'
              }}
            >
              {generating ? 'Генерация...' : videoUrl ? 'Перегенерировать' : 'Сгенерировать видео'}
            </button>
            
            {videoUrl && !generating && (
              <button
                onClick={onDownload}
                style={{
                  padding: '14px',
                  fontFamily: 'Montserrat, sans-serif',
                  fontSize: '11px',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                  backgroundColor: '#22c55e',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
              >
                ⬇ Скачать видео
              </button>
            )}
            
            {/* Информация */}
            {guide?.shorts_duration_seconds && (
              <div style={{ padding: '12px', backgroundColor: '#f9f9f9', border: '1px solid #e0e0e0', borderRadius: '4px', textAlign: 'center' }}>
                <p style={{ fontFamily: 'Roboto, sans-serif', fontSize: '11px', color: '#666', margin: 0 }}>
                  Длительность: {Math.round(guide.shorts_duration_seconds)} сек
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// AI Button Component
function AIButton({ onClick, title }) {
  const [hover, setHover] = useState(false)
  
  return (
    <button
      onClick={onClick}
      onMouseOver={() => setHover(true)}
      onMouseOut={() => setHover(false)}
      title={title}
      style={{
        height: '28px',
        padding: '0 12px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: hover ? '#ed8d48' : '#f5f5f5',
        border: '1px solid',
        borderColor: hover ? '#ed8d48' : '#d0d0d0',
        borderRadius: '4px',
        cursor: 'pointer',
        fontFamily: 'Montserrat, sans-serif',
        fontSize: '11px',
        fontWeight: 600,
        color: hover ? '#fff' : '#ed8d48',
        transition: 'all 0.15s',
        textTransform: 'uppercase',
        letterSpacing: '0.5px'
      }}
    >
      AI
    </button>
  )
}

// AI Modal Component
function AIModal({ progress, total, message, status, onClose }) {
  const progressPercent = total > 0 ? Math.round((progress / total) * 100) : 0
  
  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    }}>
      <div style={{
        backgroundColor: '#fff',
        borderRadius: '8px',
        padding: '24px',
        width: '400px',
        maxWidth: '90%',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)'
      }}>
        <h3 style={{
          fontFamily: 'Montserrat, sans-serif',
          fontSize: '16px',
          fontWeight: 600,
          color: '#333',
          marginBottom: '16px',
          textAlign: 'center'
        }}>
          {status === 'completed' ? '✅ Готово!' : status === 'error' ? '❌ Ошибка' : '⏳ Обработка AI...'}
        </h3>
        
        {status === 'processing' && (
          <>
            {/* Progress bar */}
            <div style={{
              width: '100%',
              height: '8px',
              backgroundColor: '#f0f0f0',
              borderRadius: '4px',
              overflow: 'hidden',
              marginBottom: '12px'
            }}>
              <div style={{
                width: `${progressPercent}%`,
                height: '100%',
                backgroundColor: '#ed8d48',
                transition: 'width 0.3s ease'
              }} />
            </div>
            
            {/* Progress text */}
            <div style={{
              fontFamily: 'Montserrat, sans-serif',
              fontSize: '14px',
              fontWeight: 600,
              color: '#ed8d48',
              textAlign: 'center',
              marginBottom: '8px'
            }}>
              {progressPercent}% ({progress}/{total})
            </div>
          </>
        )}
        
        {/* Message */}
        <div style={{
          fontFamily: 'Roboto, sans-serif',
          fontSize: '13px',
          color: '#666',
          textAlign: 'center',
          marginBottom: '20px'
        }}>
          {message}
        </div>
        
        {/* Close button (only when completed or error) */}
        {(status === 'completed' || status === 'error') && (
          <button
            onClick={onClose}
            style={{
              width: '100%',
              padding: '10px',
              backgroundColor: '#ed8d48',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              fontFamily: 'Montserrat, sans-serif',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'background-color 0.15s'
            }}
            onMouseOver={(e) => e.target.style.backgroundColor = '#e67e38'}
            onMouseOut={(e) => e.target.style.backgroundColor = '#ed8d48'}
          >
            Закрыть
          </button>
        )}
      </div>
    </div>
  )
}

export default StepEditor
