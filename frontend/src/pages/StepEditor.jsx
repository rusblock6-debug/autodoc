import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { guidesApi, stepsApi, storageApi } from '../services/api'

function StepEditor() {
  const { guideId } = useParams()
  const navigate = useNavigate()
  const [guide, setGuide] = useState(null)
  const [steps, setSteps] = useState([])
  const [selectedStep, setSelectedStep] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [editingText, setEditingText] = useState(null)
  const imageRef = useRef(null)

  useEffect(() => {
    fetchGuide()
  }, [guideId])

  const fetchGuide = async () => {
    try {
      // Пробуем получить по UUID сначала
      let data
      try {
        data = await guidesApi.getByUuid(guideId)
      } catch (e) {
        // Если не получилось, пробуем по ID
        data = await guidesApi.getById(guideId)
      }
      setGuide(data)
      setSteps(data.steps || [])
      if (data.steps?.length > 0) {
        setSelectedStep(data.steps[0])
      }
    } catch (error) {
      console.error('Failed to fetch guide:', error)
    } finally {
      setLoading(false)
    }
  }

  // Обновление текста шага
  const handleTextUpdate = async (stepId, newText) => {
    setSaving(true)
    try {
      await stepsApi.update(stepId, { edited_text: newText })
      setSteps(prev => prev.map(s => 
        s.id === stepId ? { ...s, edited_text: newText } : s
      ))
      if (selectedStep?.id === stepId) {
        setSelectedStep(prev => ({ ...prev, edited_text: newText }))
      }
    } catch (error) {
      console.error('Failed to update step:', error)
    } finally {
      setSaving(false)
      setEditingText(null)
    }
  }

  // Обновление позиции маркера
  const handleMarkerDrag = useCallback(async (stepId, newX, newY) => {
    // Обновляем локально сразу
    setSteps(prev => prev.map(s => 
      s.id === stepId ? { ...s, click_x: newX, click_y: newY } : s
    ))
    if (selectedStep?.id === stepId) {
      setSelectedStep(prev => ({ ...prev, click_x: newX, click_y: newY }))
    }
    
    // Сохраняем на сервер
    try {
      await stepsApi.update(stepId, { click_x: newX, click_y: newY })
    } catch (error) {
      console.error('Failed to update marker:', error)
    }
  }, [selectedStep])

  // Удаление шага
  const handleDeleteStep = async (stepId) => {
    if (!confirm('Удалить этот шаг?')) return
    
    try {
      await stepsApi.delete(stepId)
      const newSteps = steps.filter(s => s.id !== stepId)
      setSteps(newSteps)
      
      if (selectedStep?.id === stepId) {
        setSelectedStep(newSteps[0] || null)
      }
    } catch (error) {
      console.error('Failed to delete step:', error)
    }
  }

  // Перемещение шага
  const handleMoveStep = async (stepId, direction) => {
    const index = steps.findIndex(s => s.id === stepId)
    if (index === -1) return
    
    const newIndex = direction === 'up' ? index - 1 : index + 1
    if (newIndex < 0 || newIndex >= steps.length) return
    
    const newSteps = [...steps]
    const [moved] = newSteps.splice(index, 1)
    newSteps.splice(newIndex, 0, moved)
    
    // Обновляем номера шагов
    const reorderedSteps = newSteps.map((s, i) => ({ ...s, step_number: i + 1 }))
    setSteps(reorderedSteps)
    
    try {
      await stepsApi.reorder(guideId, reorderedSteps.map(s => s.id))
    } catch (error) {
      console.error('Failed to reorder:', error)
    }
  }

  // Сохранить гайд (обновить статус и вернуться на главную)
  const handleSaveGuide = async () => {
    setSaving(true)
    try {
      // Сохраняем гайд со статусом "draft" (готов к редактированию)
      await guidesApi.update(guide.id, { status: 'draft' })
    } catch (error) {
      console.error('Failed to save guide:', error)
      // Игнорируем ошибку - гайд уже сохранён автоматически
    } finally {
      setSaving(false)
      navigate('/')
    }
  }

  // Готово к генерации Shorts
  const handleReadyForShorts = async () => {
    try {
      await guidesApi.update(guide.id, { status: 'ready' })
      navigate(`/guide/${guideId}/shorts`)
    } catch (error) {
      console.error('Failed to update status:', error)
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
    <div className="h-[calc(100vh-120px)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold">{guide.title}</h1>
          <p className="text-sm text-gray-400">{steps.length} шагов</p>
        </div>
        <div className="flex items-center space-x-3">
          {saving && (
            <span className="text-sm text-gray-400">Сохранение...</span>
          )}
          <button
            onClick={handleSaveGuide}
            className="px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg font-medium transition-colors"
          >
            ✓ Сохранить
          </button>
          <button
            onClick={handleReadyForShorts}
            className="px-4 py-2 bg-yellow-500 hover:bg-yellow-400 text-black rounded-lg font-medium transition-colors"
          >
            Создать Shorts →
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex gap-4 min-h-0">
        {/* Preview panel */}
        <div className="flex-1 bg-gray-800 rounded-xl overflow-hidden flex flex-col">
          <div className="p-3 border-b border-gray-700">
            <span className="text-sm text-gray-400">
              Шаг {selectedStep?.step_number || '-'}: Перетащите маркер на нужный элемент
            </span>
          </div>
          
          <div className="flex-1 relative overflow-auto p-4">
            {selectedStep?.screenshot_path ? (
              <div className="relative inline-block">
                <img
                  ref={imageRef}
                  src={storageApi.getScreenshotUrl(selectedStep.screenshot_path)}
                  alt={`Step ${selectedStep.step_number}`}
                  className="max-w-full h-auto rounded-lg"
                  draggable={false}
                />
                
                {/* Маркер клика */}
                <DraggableMarker
                  x={selectedStep.click_x}
                  y={selectedStep.click_y}
                  imageRef={imageRef}
                  onDragEnd={(x, y) => handleMarkerDrag(selectedStep.id, x, y)}
                />
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500">
                Нет скриншота
              </div>
            )}
          </div>
        </div>

        {/* Steps list */}
        <div className="w-96 bg-gray-800 rounded-xl overflow-hidden flex flex-col">
          <div className="p-3 border-b border-gray-700">
            <span className="text-sm font-medium">Шаги инструкции</span>
          </div>
          
          <div className="flex-1 overflow-y-auto">
            {steps.map((step, index) => (
              <StepCard
                key={step.id}
                step={step}
                index={index}
                isSelected={selectedStep?.id === step.id}
                isFirst={index === 0}
                isLast={index === steps.length - 1}
                isEditing={editingText === step.id}
                onSelect={() => setSelectedStep(step)}
                onEdit={() => setEditingText(step.id)}
                onSave={(text) => handleTextUpdate(step.id, text)}
                onCancel={() => setEditingText(null)}
                onDelete={() => handleDeleteStep(step.id)}
                onMoveUp={() => handleMoveStep(step.id, 'up')}
                onMoveDown={() => handleMoveStep(step.id, 'down')}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// Компонент перетаскиваемого маркера
function DraggableMarker({ x, y, imageRef, onDragEnd }) {
  const [isDragging, setIsDragging] = useState(false)
  const [position, setPosition] = useState({ x, y })
  const markerRef = useRef(null)

  useEffect(() => {
    setPosition({ x, y })
  }, [x, y])

  const handleMouseDown = (e) => {
    e.preventDefault()
    setIsDragging(true)
    
    const handleMouseMove = (moveEvent) => {
      if (!imageRef.current) return
      
      const rect = imageRef.current.getBoundingClientRect()
      const newX = Math.max(0, Math.min(
        imageRef.current.naturalWidth,
        Math.round((moveEvent.clientX - rect.left) * (imageRef.current.naturalWidth / rect.width))
      ))
      const newY = Math.max(0, Math.min(
        imageRef.current.naturalHeight,
        Math.round((moveEvent.clientY - rect.top) * (imageRef.current.naturalHeight / rect.height))
      ))
      
      setPosition({ x: newX, y: newY })
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

  // Конвертируем координаты изображения в координаты отображения
  const getDisplayPosition = () => {
    if (!imageRef.current) return { left: 0, top: 0 }
    
    const displayWidth = imageRef.current.clientWidth
    const displayHeight = imageRef.current.clientHeight
    const naturalWidth = imageRef.current.naturalWidth || displayWidth
    const naturalHeight = imageRef.current.naturalHeight || displayHeight
    
    return {
      left: (position.x / naturalWidth) * displayWidth,
      top: (position.y / naturalHeight) * displayHeight,
    }
  }

  const displayPos = getDisplayPosition()

  return (
    <div
      ref={markerRef}
      onMouseDown={handleMouseDown}
      className={`
        absolute w-10 h-10 -ml-5 -mt-5 cursor-move
        ${isDragging ? 'scale-110' : ''}
        transition-transform
      `}
      style={{
        left: displayPos.left,
        top: displayPos.top,
      }}
    >
      {/* Внешний круг */}
      <div className="absolute inset-0 rounded-full border-4 border-yellow-400 bg-yellow-400/20 animate-pulse" />
      
      {/* Внутренняя точка */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="w-3 h-3 bg-yellow-400 rounded-full shadow-lg" />
      </div>
      
      {/* Номер шага */}
      <div className="absolute -top-6 left-1/2 -translate-x-1/2 px-2 py-0.5 bg-yellow-500 text-black text-xs font-bold rounded">
        {/* Номер будет передан через props если нужно */}
      </div>
    </div>
  )
}

// Компонент карточки шага
function StepCard({ 
  step, 
  index, 
  isSelected, 
  isFirst, 
  isLast, 
  isEditing,
  onSelect, 
  onEdit, 
  onSave, 
  onCancel,
  onDelete, 
  onMoveUp, 
  onMoveDown 
}) {
  const [editText, setEditText] = useState(step.edited_text || step.normalized_text)
  const textareaRef = useRef(null)

  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus()
      textareaRef.current.select()
    }
  }, [isEditing])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      onSave(editText)
    } else if (e.key === 'Escape') {
      setEditText(step.edited_text || step.normalized_text)
      onCancel()
    }
  }

  const displayText = step.edited_text || step.normalized_text

  return (
    <div
      onClick={onSelect}
      className={`
        p-3 border-b border-gray-700 cursor-pointer transition-colors
        ${isSelected ? 'bg-gray-700' : 'hover:bg-gray-750'}
      `}
    >
      <div className="flex items-start space-x-3">
        {/* Номер шага */}
        <div className={`
          w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0
          ${isSelected ? 'bg-yellow-500 text-black' : 'bg-gray-600 text-gray-300'}
        `}>
          {index + 1}
        </div>

        {/* Контент */}
        <div className="flex-1 min-w-0">
          {isEditing ? (
            <div>
              <textarea
                ref={textareaRef}
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                onKeyDown={handleKeyDown}
                className="w-full px-2 py-1.5 bg-gray-900 border border-gray-600 rounded text-sm resize-none focus:ring-1 focus:ring-yellow-500 focus:border-transparent outline-none"
                rows={3}
              />
              <div className="flex items-center space-x-2 mt-2">
                <button
                  onClick={(e) => { e.stopPropagation(); onSave(editText); }}
                  className="px-2 py-1 bg-green-600 hover:bg-green-500 rounded text-xs font-medium"
                >
                  Сохранить
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onCancel(); }}
                  className="px-2 py-1 bg-gray-600 hover:bg-gray-500 rounded text-xs font-medium"
                >
                  Отмена
                </button>
                <span className="text-xs text-gray-500">Ctrl+Enter / Esc</span>
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-200 line-clamp-2">{displayText}</p>
          )}

          {/* Оригинальная речь (если отличается) */}
          {!isEditing && step.raw_speech && step.raw_speech !== displayText && (
            <p className="text-xs text-gray-500 mt-1 line-clamp-1">
              Оригинал: {step.raw_speech}
            </p>
          )}
        </div>

        {/* Действия */}
        {isSelected && !isEditing && (
          <div className="flex flex-col space-y-1">
            <button
              onClick={(e) => { e.stopPropagation(); onEdit(); }}
              className="p-1 text-gray-400 hover:text-white"
              title="Редактировать"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
              </svg>
            </button>
            {!isFirst && (
              <button
                onClick={(e) => { e.stopPropagation(); onMoveUp(); }}
                className="p-1 text-gray-400 hover:text-white"
                title="Вверх"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                </svg>
              </button>
            )}
            {!isLast && (
              <button
                onClick={(e) => { e.stopPropagation(); onMoveDown(); }}
                className="p-1 text-gray-400 hover:text-white"
                title="Вниз"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            )}
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(); }}
              className="p-1 text-gray-400 hover:text-red-400"
              title="Удалить"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default StepEditor
