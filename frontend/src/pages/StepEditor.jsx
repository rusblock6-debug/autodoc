import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { guidesApi, stepsApi, storageApi, exportApi, dataJsonApi } from '../services/api'
import {
  useToast, useConfirm,
  SquareIcon, CircleIcon, ArrowRightIcon, TargetIcon,
  SparklesIcon, EditIcon, TrashIcon, DownloadIcon,
} from '../ui'

// Палитра цветов для выделений (легенды)
const ANN_COLORS = ['#ed8d48', '#e53e3e', '#22c55e', '#3b82f6', '#a855f7']
// Режимы выделения: spotlight (затемнить фон), outline (только рамка), glow (свечение)
const ANN_MODES = [
  { id: 'spotlight', icon: <TargetIcon size={15} />, label: 'Затемнить фон' },
  { id: 'outline', icon: <SquareIcon size={15} />, label: 'Только рамка' },
  { id: 'glow', icon: <SparklesIcon size={15} />, label: 'Свечение' },
]
const SHAPE_TOOLS = [
  { id: 'rect', icon: <SquareIcon size={15} />, label: 'Прямоугольник' },
  { id: 'circle', icon: <CircleIcon size={15} />, label: 'Овал' },
  { id: 'arrow', icon: <ArrowRightIcon size={15} />, label: 'Стрелка' },
]

function StepEditor() {
  const { guideId } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()
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
  // Текущие настройки инструмента выделения + выбранная аннотация
  const [annColor, setAnnColor] = useState(ANN_COLORS[0])
  const [annMode, setAnnMode] = useState('spotlight')
  const [selectedAnnId, setSelectedAnnId] = useState(null)
  const imageRef = useRef(null)
  
  // Компактный вид шагов
  const [compactView, setCompactView] = useState(true)
  
  // AI Enhancement state
  const [aiModal, setAiModal] = useState({ open: false, progress: 0, total: 0, message: '', status: 'idle' })
  // Радиальное меню выбора режима AI (появляется при зажатии кнопки AI)
  const [radial, setRadial] = useState({ open: false, x: 0, y: 0 })
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
    ttsEngine: 'silero',
    ttsVoice: 'xenia',
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
    // Стрелка хранит начало в (x,y) и конец в (x+width, y+height)
    const geom = type === 'arrow'
      ? { x: 120, y: 200, width: 180, height: 0 }
      : { x: 100, y: 100, width: 200, height: 100 }
    const newAnnotation = {
      id: Date.now(),
      type,
      ...geom,
      color: annColor,
      mode: annMode,
      label: '',
    }
    const updated = [...annotations, newAnnotation]
    setAnnotations(updated)
    setSelectedAnnId(newAnnotation.id)
    saveAnnotations(selectedStep.id, updated)
  }

  // Применить цвет: к выбранной аннотации, иначе запомнить для новых
  const applyColor = (color) => {
    setAnnColor(color)
    if (selectedAnnId) handleUpdateAnnotation(selectedAnnId, { color })
  }

  // Применить режим выделения: к выбранной аннотации, иначе запомнить для новых
  const applyMode = (mode) => {
    setAnnMode(mode)
    if (selectedAnnId) handleUpdateAnnotation(selectedAnnId, { mode })
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
    if (!(await confirm({ title: 'Удалить шаг', message: 'Удалить этот шаг?', danger: true, confirmText: 'Удалить' }))) return
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
      
      // fetch не бросает на 4xx/5xx — проверяем сами, иначе реальная причина
      // (напр. «No steps have screenshots») подменяется на «Не получен ID задачи».
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `HTTP ${response.status}`)
      }

      const data = await response.json()

      if (data.task_id) {
        setTaskId(data.task_id)
        setProgressMessage('Задача в очереди...')
      } else {
        setVideoError('Не получен ID задачи')
        setGenerating(false)
      }

    } catch (error) {
      setVideoError(error.message || 'Не удалось запустить генерацию')
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
      toast.error(`Ошибка экспорта в ${format.toUpperCase()}`)
    }
  }

  // Зажатие кнопки AI — раскрываем радиальное меню в точке курсора.
  // Выбор режима происходит перетаскиванием мыши в сектор без отпускания кнопки.
  const openRadial = (e) => {
    if (!guide?.id) return
    e.preventDefault()
    setRadial({ open: true, x: e.clientX, y: e.clientY })
  }

  // Пользователь дотянул до сектора и отпустил кнопку мыши
  const handleRadialSelect = (mode) => {
    setRadial(r => ({ ...r, open: false }))
    startEnhance(mode)
  }

  // Отпустил в центре / вне секторов — отмена
  const closeRadial = () => {
    setRadial(r => ({ ...r, open: false }))
  }

  // Запуск выбранного режима: 'regenerate' (с нуля) | 'improve' (улучшить текст)
  const startEnhance = async (mode) => {
    if (!guide?.id) return

    try {
      const response = await guidesApi.enhanceWithAI(guide.id, mode)

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
      toast.error('Ошибка запуска AI обработки')
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
          
          // Если завершено / ошибка / отменено - останавливаем polling
          if (status.status === 'completed' || status.status === 'error' || status.status === 'cancelled') {
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

  // Отмена выполняющейся AI обработки
  const cancelEnhance = async () => {
    if (!guide?.id) return
    // Останавливаем polling сразу, чтобы прогресс не мигал
    if (aiPollingRef.current) {
      clearInterval(aiPollingRef.current)
      aiPollingRef.current = null
    }
    setAiModal(prev => ({ ...prev, status: 'cancelled', message: 'Отменяем обработку...' }))
    try {
      await guidesApi.cancelAI(guide.id)
      setAiModal(prev => ({ ...prev, status: 'cancelled', message: 'Обработка отменена' }))
      // Подтягиваем то, что успело обновиться до отмены
      setTimeout(() => { fetchGuide() }, 1000)
    } catch (error) {
      toast.error('Не удалось отменить обработку')
    }
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

      if (exportType === 'descriptive') {
        await dataJsonApi.addToDescriptive({
          guide_id: guideId,
          title: exportData.title,
          subtitle: exportData.subtitle,
          description: exportData.description,
          items: itemsArray
        })
      } else { // instruction
        await dataJsonApi.addToInstruction({
          guide_id: guideId,
          title: exportData.title,
          nav_title: exportData.nav_title || exportData.title,
          description: exportData.description,
          items: itemsArray,
          steps: steps.map(step => ({
            text: step.annotation || `Шаг ${step.step_number}`,
            image: step.screenshot_path || ''
          }))
        })
      }

      toast.success('Успешно экспортировано')
      setShowExportModal(false)
    } catch (error) {
      const detail = error.response?.data?.detail || error.message || 'Не удалось экспортировать'
      toast.error(`Ошибка экспорта: ${detail}`)
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
          
          {/* AI Enhancement Button — зажать и выбрать режим в радиальном меню */}
          <AIButton onMouseDown={openRadial} title="Зажмите и выберите: Улучшить или Написать" />
          
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
        {/* Steps sidebar - документация стиль */}
        <div style={{ width: '380px', backgroundColor: '#fff', borderRight: '1px solid #ddd', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '18px 20px', borderBottom: '1px solid #ddd', display: 'flex', alignItems: 'center', justifyContent: 'flex-end' }}>
            {/* Toggle */}
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', userSelect: 'none' }}>
              <span style={{ fontSize: '12px', color: '#888', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
                Свернуть
              </span>
              <div 
                onClick={(e) => { e.preventDefault(); setCompactView(!compactView); }}
                style={{
                  width: '38px',
                  height: '20px',
                  backgroundColor: compactView ? '#ed8d48' : '#ccc',
                  borderRadius: '10px',
                  position: 'relative',
                  transition: 'background-color 0.2s',
                  cursor: 'pointer'
                }}
              >
                <div style={{
                  width: '16px',
                  height: '16px',
                  backgroundColor: '#fff',
                  borderRadius: '50%',
                  position: 'absolute',
                  top: '2px',
                  left: compactView ? '20px' : '2px',
                  transition: 'left 0.2s',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.2)'
                }} />
              </div>
            </label>
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {steps.map((step, index) => (
              <StepCard key={step.id} step={step} index={index} isSelected={selectedStep?.id === step.id && activeTab === 'steps'} isFirst={index === 0} isLast={index === steps.length - 1} isEditing={editingText === step.id} compactView={compactView}
                onSelect={() => { setActiveTab('steps'); setSelectedStep(step); setAnnotations(step.annotations || []); setSelectedAnnId(null) }} onEdit={() => setEditingText(step.id)} onSave={(text) => handleTextUpdate(step.id, text)} onCancel={() => setEditingText(null)}
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
                
                {/* Фигуры выделения */}
                {SHAPE_TOOLS.map(tool => (
                  <button
                    key={tool.id}
                    onClick={() => handleAddAnnotation(tool.id)}
                    title={`Добавить: ${tool.label}`}
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
                      color: annColor
                    }}
                  >
                    {tool.icon}
                  </button>
                ))}

                {/* Разделитель */}
                <div style={{ width: '1px', height: '20px', backgroundColor: '#e0e0e0', margin: '0 2px' }} />

                {/* Палитра цветов */}
                {ANN_COLORS.map(color => (
                  <button
                    key={color}
                    onClick={() => applyColor(color)}
                    title="Цвет выделения"
                    style={{
                      width: '20px',
                      height: '20px',
                      backgroundColor: color,
                      border: annColor === color ? '2px solid #333' : '2px solid #fff',
                      boxShadow: '0 0 0 1px #e0e0e0',
                      borderRadius: '50%',
                      cursor: 'pointer',
                      padding: 0
                    }}
                  />
                ))}

                {/* Разделитель */}
                <div style={{ width: '1px', height: '20px', backgroundColor: '#e0e0e0', margin: '0 2px' }} />

                {/* Режим выделения */}
                {ANN_MODES.map(m => (
                  <button
                    key={m.id}
                    onClick={() => applyMode(m.id)}
                    title={m.label}
                    style={{
                      width: '28px',
                      height: '28px',
                      backgroundColor: annMode === m.id ? '#fff5e6' : 'transparent',
                      border: annMode === m.id ? '1px solid #ed8d48' : '1px solid #e0e0e0',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '13px'
                    }}
                  >
                    {m.icon}
                  </button>
                ))}

                {/* Очистить все */}
                {annotations.length > 0 && (
                  <button 
                    onClick={() => { setAnnotations([]); setSelectedAnnId(null); saveAnnotations(selectedStep.id, []) }}
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
                    <TrashIcon size={14} />
                  </button>
                )}
              </div>
            )}
          </div>
          <div style={{ flex: 1, overflow: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px' }}>
            {selectedStep?.screenshot_path ? (
              <div style={{ position: 'relative', display: 'inline-block' }}>
                <img ref={imageRef} src={storageApi.getScreenshotUrl(selectedStep.screenshot_path)} alt="" style={{ maxWidth: '100%', maxHeight: 'calc(100vh - 300px)', borderRadius: '4px', boxShadow: '0 2px 12px rgba(0,0,0,0.1)' }} draggable={false} />
                
                {/* Серый оверлей с вырезами только под spotlight-выделения (rect/circle) */}
                {annotations.some(a => (a.mode || 'spotlight') === 'spotlight' && a.type !== 'arrow') && (
                  <DarkOverlay
                    annotations={annotations.filter(a => (a.mode || 'spotlight') === 'spotlight' && a.type !== 'arrow')}
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
                {annotations.map((ann, idx) => (
                  ann.type === 'arrow' ? (
                    <DraggableArrow
                      key={ann.id}
                      annotation={ann}
                      number={idx + 1}
                      isSelected={selectedAnnId === ann.id}
                      imageRef={imageRef}
                      viewportWidth={selectedStep.screenshot_width}
                      viewportHeight={selectedStep.screenshot_height}
                      onSelect={() => setSelectedAnnId(ann.id)}
                      onUpdate={(updates) => handleUpdateAnnotation(ann.id, updates)}
                      onDelete={() => { handleDeleteAnnotation(ann.id); setSelectedAnnId(null) }}
                    />
                  ) : (
                    <DraggableAnnotation
                      key={ann.id}
                      annotation={ann}
                      number={idx + 1}
                      isSelected={selectedAnnId === ann.id}
                      imageRef={imageRef}
                      viewportWidth={selectedStep.screenshot_width}
                      viewportHeight={selectedStep.screenshot_height}
                      onSelect={() => setSelectedAnnId(ann.id)}
                      onUpdate={(updates) => handleUpdateAnnotation(ann.id, updates)}
                      onDelete={() => { handleDeleteAnnotation(ann.id); setSelectedAnnId(null) }}
                    />
                  )
                ))}
              </div>
            ) : (
              <div style={{ color: '#999', padding: '48px' }}>Нет скриншота</div>
            )}

            {/* Блок-легенда: расшифровка подписанных выделений */}
            {selectedStep?.screenshot_path && annotations.some(a => (a.label || '').trim()) && (
              <AnnotationLegend annotations={annotations} />
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
      
      {/* Радиальное меню выбора режима AI */}
      {radial.open && (
        <RadialMenu
          x={radial.x}
          y={radial.y}
          onSelect={handleRadialSelect}
          onCancel={closeRadial}
        />
      )}

      {/* AI Enhancement Modal (прогресс / результат) */}
      {aiModal.open && (
        <AIModal
          progress={aiModal.progress}
          total={aiModal.total}
          message={aiModal.message}
          status={aiModal.status}
          onClose={closeAIModal}
          onCancel={cancelEnhance}
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
          
          {/* Черные фигуры = вырезы (прозрачные области) */}
          {annotations.map(ann => {
            const pos = convertToDisplayCoords(ann)
            if (ann.type === 'circle') {
              return (
                <ellipse
                  key={ann.id}
                  cx={pos.x + pos.width / 2}
                  cy={pos.y + pos.height / 2}
                  rx={pos.width / 2}
                  ry={pos.height / 2}
                  fill="black"
                />
              )
            }
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

function DraggableAnnotation({ annotation, number, isSelected, imageRef, viewportWidth, viewportHeight, onSelect, onUpdate, onDelete }) {
  const [isDragging, setIsDragging] = useState(false)
  const [isResizing, setIsResizing] = useState(false)
  const [localPos, setLocalPos] = useState({ x: annotation.x, y: annotation.y, width: annotation.width, height: annotation.height })
  const [labelDraft, setLabelDraft] = useState(annotation.label || '')
  // Смещение блока «номер + подпись» относительно угла фигуры (в координатах вьюпорта)
  const [labelOffset, setLabelOffset] = useState({ dx: annotation.labelDx || 0, dy: annotation.labelDy || 0 })
  const isMountedRef = useRef(true)
  const prevAnnotationIdRef = useRef(annotation.id)

  useEffect(() => {
    // Обновляем localPos при монтировании или при смене аннотации (переключение шагов)
    if (prevAnnotationIdRef.current !== annotation.id) {
      setLocalPos({ x: annotation.x, y: annotation.y, width: annotation.width, height: annotation.height })
      setLabelOffset({ dx: annotation.labelDx || 0, dy: annotation.labelDy || 0 })
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

  // Перетаскивание блока «номер + подпись» (ручка — сам бейдж)
  const startLabelDrag = (e) => {
    e.preventDefault(); e.stopPropagation()
    onSelect && onSelect()
    if (!imageRef.current) return
    const rect = imageRef.current.getBoundingClientRect()
    const vw = viewportWidth || imageRef.current.naturalWidth
    const vh = viewportHeight || imageRef.current.naturalHeight
    const m0 = { x: e.clientX, y: e.clientY }
    const o0 = { ...labelOffset }
    let cur = { ...o0 }
    const move = (ev) => {
      const dx = (ev.clientX - m0.x) * (vw / rect.width)
      const dy = (ev.clientY - m0.y) * (vh / rect.height)
      cur = { dx: o0.dx + dx, dy: o0.dy + dy }
      setLabelOffset(cur)
    }
    const up = () => {
      document.removeEventListener('mousemove', move)
      document.removeEventListener('mouseup', up)
      if (isMountedRef.current) onUpdate({ labelDx: Math.round(cur.dx), labelDy: Math.round(cur.dy) })
    }
    document.addEventListener('mousemove', move)
    document.addEventListener('mouseup', up)
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
  const color = annotation.color || '#ed8d48'
  const mode = annotation.mode || 'spotlight'
  const isCircle = annotation.type === 'circle'
  // Масштаб вьюпорт→экран для смещения блока подписи
  const lblScale = (() => {
    const el = imageRef.current
    const dw = el?.clientWidth || 1, dh = el?.clientHeight || 1
    const vw = viewportWidth || el?.naturalWidth || dw
    const vh = viewportHeight || el?.naturalHeight || dh
    return { sx: dw / vw, sy: dh / vh }
  })()

  return (
    <div
      onMouseDown={(e) => { onSelect && onSelect(); handleMouseDown(e, 'move') }}
      style={{
        position: 'absolute',
        left: pos.left,
        top: pos.top,
        width: pos.width,
        height: pos.height,
        border: `3px solid ${color}`,
        borderRadius: isCircle ? '50%' : '4px',
        backgroundColor: 'transparent',
        boxShadow: mode === 'glow'
          ? `0 0 16px 4px ${color}, 0 0 5px 1px ${color}`
          : (isSelected ? '0 0 0 2px rgba(0,0,0,0.35)' : 'none'),
        cursor: isDragging ? 'grabbing' : 'grab',
        boxSizing: 'border-box',
        transition: isDragging || isResizing ? 'none' : 'all 0.1s'
      }}
    >
      {/* Номерной бейдж + поле подписи (легенда). Блок можно перетаскивать за бейдж. */}
      <div
        onMouseDown={(e) => e.stopPropagation()}
        style={{
          position: 'absolute',
          top: '-13px',
          left: '-3px',
          transform: `translate(${labelOffset.dx * lblScale.sx}px, ${labelOffset.dy * lblScale.sy}px)`,
          display: 'flex',
          alignItems: 'flex-start',
          gap: '4px',
          zIndex: 4
        }}
      >
        <span
          onMouseDown={startLabelDrag}
          title="Перетащите, чтобы сдвинуть подпись"
          style={{
            minWidth: '22px', height: '22px', padding: '0 6px',
            borderRadius: '11px', backgroundColor: color, color: '#fff',
            fontSize: '12px', fontWeight: 700, fontFamily: 'Montserrat, sans-serif',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            border: '2px solid #fff', boxShadow: '0 1px 3px rgba(0,0,0,0.25)',
            cursor: 'move', flexShrink: 0
          }}>{number}</span>
        {(isSelected || labelDraft) && (
          <AnnotationLabelInput
            value={labelDraft}
            onChange={setLabelDraft}
            onCommit={() => onUpdate({ label: labelDraft })}
            color={color}
          />
        )}
      </div>

      <button
        onClick={(e) => { e.stopPropagation(); onDelete() }}
        style={{
          position: 'absolute',
          top: '-18px',
          right: '-18px',
          width: '36px',
          height: '36px',
          borderRadius: '50%',
          backgroundColor: color,
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
          backgroundColor: color,
          border: '2px solid #fff',
          borderRadius: '50%',
          cursor: 'nwse-resize'
        }}
      />
    </div>
  )
}

// Стрелка-указатель: хранит начало (x,y) и смещение конца (width,height)
function DraggableArrow({ annotation, number, isSelected, imageRef, viewportWidth, viewportHeight, onSelect, onUpdate, onDelete }) {
  const [start, setStart] = useState({ x: annotation.x, y: annotation.y })
  const [end, setEnd] = useState({ x: annotation.x + annotation.width, y: annotation.y + annotation.height })
  const [labelDraft, setLabelDraft] = useState(annotation.label || '')
  const [labelOffset, setLabelOffset] = useState({ dx: annotation.labelDx || 0, dy: annotation.labelDy || 0 })
  const isMountedRef = useRef(true)
  useEffect(() => { isMountedRef.current = true; return () => { isMountedRef.current = false } }, [])

  const color = annotation.color || '#ed8d48'
  const glow = (annotation.mode || 'spotlight') === 'glow'
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v))

  const dims = () => {
    const dw = imageRef.current?.clientWidth || 1
    const dh = imageRef.current?.clientHeight || 1
    const vw = viewportWidth || imageRef.current?.naturalWidth || dw
    const vh = viewportHeight || imageRef.current?.naturalHeight || dh
    return { dw, dh, vw, vh }
  }
  const toDisplay = (p) => { const { dw, dh, vw, vh } = dims(); return { x: (p.x / vw) * dw, y: (p.y / vh) * dh } }
  const commit = (s, e) => onUpdate({ x: Math.round(s.x), y: Math.round(s.y), width: Math.round(e.x - s.x), height: Math.round(e.y - s.y) })

  const startDrag = (e, which) => {
    e.preventDefault(); e.stopPropagation(); onSelect && onSelect()
    if (!imageRef.current) return
    const rect = imageRef.current.getBoundingClientRect()
    const { vw, vh } = dims()
    const m0 = { x: e.clientX, y: e.clientY }
    const s0 = { ...start }, e0 = { ...end }
    let cs = { ...s0 }, ce = { ...e0 }
    const move = (ev) => {
      const dx = (ev.clientX - m0.x) * (vw / rect.width)
      const dy = (ev.clientY - m0.y) * (vh / rect.height)
      if (which === 'start') { cs = { x: clamp(s0.x + dx, 0, vw), y: clamp(s0.y + dy, 0, vh) }; setStart(cs) }
      else if (which === 'end') { ce = { x: clamp(e0.x + dx, 0, vw), y: clamp(e0.y + dy, 0, vh) }; setEnd(ce) }
      else {
        cs = { x: clamp(s0.x + dx, 0, vw), y: clamp(s0.y + dy, 0, vh) }
        ce = { x: clamp(e0.x + dx, 0, vw), y: clamp(e0.y + dy, 0, vh) }
        setStart(cs); setEnd(ce)
      }
    }
    const up = () => {
      document.removeEventListener('mousemove', move)
      document.removeEventListener('mouseup', up)
      if (isMountedRef.current) commit(cs, ce)
    }
    document.addEventListener('mousemove', move)
    document.addEventListener('mouseup', up)
  }

  // Перетаскивание блока «номер + подпись» (ручка — сам бейдж)
  const startLabelDrag = (e) => {
    e.preventDefault(); e.stopPropagation(); onSelect && onSelect()
    if (!imageRef.current) return
    const rect = imageRef.current.getBoundingClientRect()
    const { vw, vh } = dims()
    const m0 = { x: e.clientX, y: e.clientY }
    const o0 = { ...labelOffset }
    let cur = { ...o0 }
    const move = (ev) => {
      const dx = (ev.clientX - m0.x) * (vw / rect.width)
      const dy = (ev.clientY - m0.y) * (vh / rect.height)
      cur = { dx: o0.dx + dx, dy: o0.dy + dy }
      setLabelOffset(cur)
    }
    const up = () => {
      document.removeEventListener('mousemove', move)
      document.removeEventListener('mouseup', up)
      if (isMountedRef.current) onUpdate({ labelDx: Math.round(cur.dx), labelDy: Math.round(cur.dy) })
    }
    document.addEventListener('mousemove', move)
    document.addEventListener('mouseup', up)
  }

  const ds = toDisplay(start)
  const de = toDisplay(end)
  const { dw: _dw, dh: _dh, vw: _vw, vh: _vh } = dims()
  const lblScale = { sx: _dw / _vw, sy: _dh / _vh }
  const markerId = `arrowhead-${annotation.id}`

  const handleStyle = (left, top) => ({
    position: 'absolute', left, top, width: '12px', height: '12px',
    marginLeft: '-6px', marginTop: '-6px', borderRadius: '50%',
    backgroundColor: '#fff', border: `2px solid ${color}`,
    cursor: 'move', pointerEvents: 'auto', zIndex: 5
  })

  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 3 }}>
      <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', overflow: 'visible' }}>
        <defs>
          <marker id={markerId} markerWidth="10" markerHeight="10" refX="7" refY="3.5" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L7,3.5 L0,7 Z" fill={color} />
          </marker>
        </defs>
        {/* Невидимая толстая линия — цель для перетаскивания всей стрелки */}
        <line x1={ds.x} y1={ds.y} x2={de.x} y2={de.y} stroke="transparent" strokeWidth="16"
          style={{ pointerEvents: 'stroke', cursor: 'move' }} onMouseDown={(e) => startDrag(e, 'body')} />
        <line x1={ds.x} y1={ds.y} x2={de.x} y2={de.y} stroke={color} strokeWidth={isSelected ? 5 : 3.5}
          strokeLinecap="round" markerEnd={`url(#${markerId})`}
          style={{ filter: glow ? `drop-shadow(0 0 5px ${color})` : 'none', pointerEvents: 'none' }} />
      </svg>

      {/* Ручки концов */}
      <div style={handleStyle(ds.x, ds.y)} onMouseDown={(e) => startDrag(e, 'start')} />
      <div style={handleStyle(de.x, de.y)} onMouseDown={(e) => startDrag(e, 'end')} />

      {/* Бейдж + подпись у начала. Блок можно перетаскивать за бейдж. */}
      <div
        onMouseDown={(e) => e.stopPropagation()}
        style={{
          position: 'absolute', left: ds.x + 10, top: ds.y - 12,
          transform: `translate(${labelOffset.dx * lblScale.sx}px, ${labelOffset.dy * lblScale.sy}px)`,
          display: 'flex', alignItems: 'flex-start', gap: '4px', pointerEvents: 'auto', zIndex: 6
        }}
      >
        <span
          onMouseDown={startLabelDrag}
          title="Перетащите, чтобы сдвинуть подпись"
          style={{
            minWidth: '22px', height: '22px', padding: '0 6px', borderRadius: '11px',
            backgroundColor: color, color: '#fff', fontSize: '12px', fontWeight: 700,
            fontFamily: 'Montserrat, sans-serif', display: 'flex', alignItems: 'center',
            justifyContent: 'center', border: '2px solid #fff', boxShadow: '0 1px 3px rgba(0,0,0,0.25)',
            cursor: 'move', flexShrink: 0
          }}>{number}</span>
        {(isSelected || labelDraft) && (
          <AnnotationLabelInput
            value={labelDraft}
            onChange={setLabelDraft}
            onCommit={() => onUpdate({ label: labelDraft })}
            color={color}
          />
        )}
        <button
          onClick={(e) => { e.stopPropagation(); onDelete() }}
          title="Удалить"
          style={{
            width: '20px', height: '20px', borderRadius: '50%', backgroundColor: color,
            color: '#fff', border: '2px solid #fff', cursor: 'pointer', fontSize: '11px',
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 0
          }}
        >×</button>
      </div>
    </div>
  )
}

// Поле подписи к выделению. Растёт по высоте и переносит строки, чтобы
// влезал не только один короткий ярлык, но и фраза из нескольких слов.
function AnnotationLabelInput({ value, onChange, onCommit, color }) {
  const ref = useRef(null)
  const autosize = (el) => {
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }
  useEffect(() => { autosize(ref.current) }, [value])
  return (
    <textarea
      ref={ref}
      value={value}
      rows={1}
      maxLength={200}
      onChange={(e) => onChange(e.target.value)}
      onInput={(e) => autosize(e.currentTarget)}
      onBlur={onCommit}
      onKeyDown={(e) => {
        // Не пускаем клавиши к горячим клавишам редактора — внутри ячейки работают
        // обычные текстовые шорткаты (Ctrl+Z/Y, Ctrl+A, стрелки и т.д.).
        e.stopPropagation()
        // Enter — перенос строки (нативно). Esc — подтвердить и выйти.
        if (e.key === 'Escape') { e.preventDefault(); e.currentTarget.blur() }
      }}
      onClick={(e) => e.stopPropagation()}
      onMouseDown={(e) => e.stopPropagation()}
      style={{
        fontSize: '12px', fontFamily: 'system-ui, sans-serif',
        padding: '3px 6px', borderRadius: '4px',
        border: `1px solid ${color}`, backgroundColor: 'rgba(255,255,255,0.96)',
        color: '#333', outline: 'none',
        width: '170px', maxWidth: '260px',
        resize: 'none', overflow: 'hidden',
        lineHeight: '1.3', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
        display: 'block', boxSizing: 'border-box',
      }}
    />
  )
}

// Блок-легенда под скриншотом: расшифровка подписанных выделений
function AnnotationLegend({ annotations }) {
  const items = (annotations || [])
    .map((a, i) => ({ n: i + 1, ...a }))
    .filter(a => (a.label || '').trim())
  if (items.length === 0) return null
  return (
    <div style={{ width: '100%', maxWidth: '820px', backgroundColor: '#fff', border: '1px solid #e0e0e0', borderRadius: '8px', padding: '14px 18px' }}>
      <div style={{ fontFamily: 'Montserrat, sans-serif', fontSize: '11px', fontWeight: 600, color: '#999', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '10px' }}>
        Легенда
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {items.map(a => (
          <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{
              minWidth: '22px', height: '22px', borderRadius: '11px', backgroundColor: a.color || '#ed8d48',
              color: '#fff', fontSize: '12px', fontWeight: 700, fontFamily: 'Montserrat, sans-serif',
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
            }}>{a.n}</span>
            <span style={{ fontSize: '14px', color: '#333', fontFamily: 'system-ui, sans-serif' }}>{a.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function StepCard({ step, index, isSelected, isFirst, isLast, isEditing, compactView, onSelect, onEdit, onSave, onCancel, onDelete, onMoveUp, onMoveDown }) {
  const [editText, setEditText] = useState(step.edited_text || step.normalized_text || `Шаг ${index + 1}`)
  const [isHovered, setIsHovered] = useState(false)
  const textareaRef = useRef(null)

  useEffect(() => { if (isEditing && textareaRef.current) { textareaRef.current.focus(); textareaRef.current.select() } }, [isEditing])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && e.ctrlKey) onSave(editText)
    else if (e.key === 'Escape') { setEditText(step.edited_text || step.normalized_text || `Шаг ${index + 1}`); onCancel() }
  }

  const displayText = step.edited_text || step.normalized_text || `Шаг ${index + 1}`
  const shouldTruncate = compactView && !isSelected

  return (
    <div 
      onClick={onSelect} 
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        padding: '16px 20px',
        cursor: 'pointer',
        backgroundColor: isSelected ? '#fffbf5' : (isHovered ? '#fafafa' : '#fff'),
        borderLeft: isSelected ? '3px solid #ed8d48' : '3px solid transparent',
        borderBottom: '1px solid #efefef',
        transition: 'all 0.15s ease',
        position: 'relative'
      }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px' }}>
        {/* Элегантный номер */}
        <div style={{
          minWidth: '28px',
          height: '28px',
          borderRadius: '6px',
          border: isSelected ? '2px solid #ed8d48' : '1px solid #e0e0e0',
          backgroundColor: isSelected ? '#fff' : '#fafafa',
          color: isSelected ? '#ed8d48' : '#999',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '14px',
          fontFamily: 'system-ui, -apple-system, sans-serif',
          fontWeight: 600,
          flexShrink: 0,
          transition: 'all 0.15s ease'
        }}>
          {index + 1}
        </div>
        
        {/* Контент */}
        <div style={{ flex: 1, minWidth: 0, paddingTop: '2px' }}>
          {isEditing ? (
            <div>
              <textarea 
                ref={textareaRef} 
                value={editText} 
                onChange={(e) => setEditText(e.target.value)} 
                onKeyDown={handleKeyDown}
                style={{ 
                  width: '100%', 
                  padding: '12px', 
                  fontSize: '15px', 
                  fontFamily: 'system-ui, -apple-system, sans-serif',
                  border: '2px solid #ed8d48', 
                  borderRadius: '6px', 
                  backgroundColor: '#fff', 
                  color: '#2c3e50', 
                  resize: 'vertical', 
                  outline: 'none',
                  minHeight: '90px',
                  lineHeight: '1.6'
                }} 
              />
              <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
                <button 
                  onClick={(e) => { e.stopPropagation(); onSave(editText) }} 
                  style={{ 
                    padding: '8px 16px', 
                    fontSize: '14px', 
                    fontWeight: 500,
                    fontFamily: 'system-ui, -apple-system, sans-serif',
                    backgroundColor: '#ed8d48', 
                    color: '#fff', 
                    border: 'none', 
                    borderRadius: '5px', 
                    cursor: 'pointer',
                    transition: 'background-color 0.15s'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#dc7a37'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#ed8d48'}
                >
                  Сохранить
                </button>
                <button 
                  onClick={(e) => { e.stopPropagation(); onCancel() }} 
                  style={{ 
                    padding: '8px 16px', 
                    fontSize: '14px', 
                    fontWeight: 500,
                    fontFamily: 'system-ui, -apple-system, sans-serif',
                    backgroundColor: '#f5f5f5', 
                    color: '#666', 
                    border: '1px solid #ddd',
                    borderRadius: '5px', 
                    cursor: 'pointer',
                    transition: 'all 0.15s'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#eee'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#f5f5f5'}
                >
                  Отмена
                </button>
              </div>
            </div>
          ) : (
            <p style={{ 
              fontFamily: 'system-ui, -apple-system, sans-serif', 
              fontSize: '15px',
              color: isSelected ? '#2c3e50' : '#555', 
              margin: 0, 
              lineHeight: '1.65',
              fontWeight: 400,
              ...(shouldTruncate ? {
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
                textOverflow: 'ellipsis'
              } : {})
            }}>
              {displayText}
            </p>
          )}
        </div>
        
        {/* Кнопки - появляются при hover */}
        {(isHovered || isSelected) && !isEditing && (
          <div style={{ 
            display: 'flex', 
            gap: '4px', 
            flexShrink: 0,
            opacity: (isHovered || isSelected) ? 1 : 0,
            transition: 'opacity 0.15s'
          }}>
            <button
              onClick={(e) => { e.stopPropagation(); onEdit() }}
              style={{
                width: '32px',
                height: '32px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: '1px solid #e0e0e0',
                backgroundColor: '#fff',
                borderRadius: '5px',
                cursor: 'pointer',
                color: '#666',
                transition: 'all 0.15s'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#ed8d48'
                e.currentTarget.style.color = '#ed8d48'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = '#e0e0e0'
                e.currentTarget.style.color = '#666'
              }}
              title="Редактировать"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
            </button>
            
            {!isFirst && (
              <button
                onClick={(e) => { e.stopPropagation(); onMoveUp() }}
                style={{
                  width: '32px',
                  height: '32px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  border: '1px solid #e0e0e0',
                  backgroundColor: '#fff',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  color: '#666',
                  transition: 'all 0.15s'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = '#ed8d48'
                  e.currentTarget.style.color = '#ed8d48'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = '#e0e0e0'
                  e.currentTarget.style.color = '#666'
                }}
                title="Переместить вверх"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="18 15 12 9 6 15" />
                </svg>
              </button>
            )}
            
            {!isLast && (
              <button
                onClick={(e) => { e.stopPropagation(); onMoveDown() }}
                style={{
                  width: '32px',
                  height: '32px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  border: '1px solid #e0e0e0',
                  backgroundColor: '#fff',
                  borderRadius: '5px',
                  cursor: 'pointer',
                  color: '#666',
                  transition: 'all 0.15s'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = '#ed8d48'
                  e.currentTarget.style.color = '#ed8d48'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = '#e0e0e0'
                  e.currentTarget.style.color = '#666'
                }}
                title="Переместить вниз"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>
            )}
            
            <button
              onClick={(e) => { e.stopPropagation(); onDelete() }}
              style={{
                width: '32px',
                height: '32px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: '1px solid #e0e0e0',
                backgroundColor: '#fff',
                borderRadius: '5px',
                cursor: 'pointer',
                color: '#666',
                transition: 'all 0.15s'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#dc2626'
                e.currentTarget.style.color = '#dc2626'
                e.currentTarget.style.backgroundColor = '#fef2f2'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = '#e0e0e0'
                e.currentTarget.style.color = '#666'
                e.currentTarget.style.backgroundColor = '#fff'
              }}
              title="Удалить"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
            </button>
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
    silero: [
      { value: 'xenia', label: 'Ксения (жен.)' },
      { value: 'baya', label: 'Бая (жен.)' },
      { value: 'kseniya', label: 'Ксения 2 (жен.)' },
      { value: 'eugene', label: 'Евгений (муж.)' },
      { value: 'aidar', label: 'Айдар (муж.)' },
    ],
    edge: [
      { value: 'ru-RU-SvetlanaNeural', label: 'Светлана' },
      { value: 'ru-RU-DmitryNeural', label: 'Дмитрий' },
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
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '8px' }}>
                <button
                  onClick={() => setTtsSettings(s => ({ ...s, ttsEngine: 'silero', ttsVoice: 'xenia' }))}
                  disabled={generating}
                  style={{
                    padding: '10px',
                    fontFamily: 'Montserrat, sans-serif',
                    fontSize: '11px',
                    fontWeight: 600,
                    backgroundColor: ttsSettings.ttsEngine === 'silero' ? '#ed8d48' : '#fff',
                    color: ttsSettings.ttsEngine === 'silero' ? '#fff' : '#666',
                    border: '1px solid #e0e0e0',
                    borderRadius: '4px',
                    cursor: generating ? 'not-allowed' : 'pointer',
                    transition: 'all 0.2s'
                  }}
                >
                  Silero
                </button>
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
                  transition: 'all 0.2s',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px'
                }}
              >
                <DownloadIcon size={14} /> Скачать видео
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

// Быстрое меню выбора режима AI. Появляется в точке зажатия кнопки AI;
// выбор — перетаскиванием мыши в половину без отпускания кнопки.
// Левая половина (искра) — «Улучшить», правая (карандаш) — «Написать».
// Отпускание в центре или вне меню = отмена.
function RadialMenu({ x, y, onSelect, onCancel }) {
  const W = 104       // ширина меню
  const H = 38        // высота меню
  const DEAD = 9      // полуширина центральной зоны отмены
  const [hovered, setHovered] = useState(null)

  // Колбэки держим в ref, чтобы слушатели вешались один раз и не теряли событий
  const cbRef = useRef({ onSelect, onCancel })
  cbRef.current = { onSelect, onCancel }

  const sectorAt = useCallback((cx, cy) => {
    const dx = cx - x
    const dy = cy - y
    if (Math.abs(dx) > W / 2 || Math.abs(dy) > H / 2) return null  // вне меню
    if (Math.abs(dx) < DEAD) return null                          // центр — отмена
    return dx < 0 ? 'improve' : 'regenerate'
  }, [x, y])

  useEffect(() => {
    const onMove = (e) => setHovered(sectorAt(e.clientX, e.clientY))
    const onUp = (e) => {
      const sel = sectorAt(e.clientX, e.clientY)
      if (sel) cbRef.current.onSelect(sel)
      else cbRef.current.onCancel()
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [sectorAt])

  const half = (id) => ({
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: hovered === id ? '#ed8d48' : '#ffffff',
    color: hovered === id ? '#ffffff' : '#666',
    transition: 'background-color 0.1s',
  })

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 2000, pointerEvents: 'none' }}>
      <div style={{
        position: 'absolute',
        left: x - W / 2,
        top: y - H / 2,
        width: W,
        height: H,
        display: 'flex',
        borderRadius: 8,
        overflow: 'hidden',
        border: '1px solid #e0e0e0',
        boxShadow: '0 6px 16px rgba(0,0,0,0.25)',
      }}>
        <div style={half('improve')} title="Улучшить">
          <SparklesIcon size={16} />
        </div>
        <div style={{ width: 1, backgroundColor: '#eee' }} />
        <div style={half('regenerate')} title="Написать">
          <EditIcon size={16} />
        </div>
      </div>
    </div>
  )
}

// AI Button Component
function AIButton({ onMouseDown, title }) {
  const [hover, setHover] = useState(false)

  return (
    <button
      onMouseDown={onMouseDown}
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

// AI Modal Component (прогресс обработки / результат)
function AIModal({ progress, total, message, status, onClose, onCancel }) {
  const progressPercent = total > 0 ? Math.round((progress / total) * 100) : 0

  const titleText = {
    completed: 'Готово',
    error: 'Ошибка',
    cancelled: 'Отменено',
  }[status] || 'Обработка AI...'

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
          {titleText}
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
        {status !== 'choose' && (
          <div style={{
            fontFamily: 'Roboto, sans-serif',
            fontSize: '13px',
            color: '#666',
            textAlign: 'center',
            marginBottom: '20px'
          }}>
            {message}
          </div>
        )}

        {/* Cancel button (while processing) */}
        {status === 'processing' && (
          <button
            onClick={onCancel}
            style={{
              width: '100%',
              padding: '10px',
              backgroundColor: '#fff',
              color: '#d9534f',
              border: '1px solid #d9534f',
              borderRadius: '4px',
              fontFamily: 'Montserrat, sans-serif',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'background-color 0.15s'
            }}
            onMouseOver={(e) => { e.target.style.backgroundColor = '#d9534f'; e.target.style.color = '#fff' }}
            onMouseOut={(e) => { e.target.style.backgroundColor = '#fff'; e.target.style.color = '#d9534f' }}
          >
            Отмена
          </button>
        )}

        {/* Close button (when completed / error / cancelled) */}
        {(status === 'completed' || status === 'error' || status === 'cancelled') && (
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
