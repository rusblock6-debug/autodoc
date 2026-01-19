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
  const imageRef = useRef(null)

  useEffect(() => { fetchGuide() }, [guideId])

  const fetchGuide = async () => {
    try {
      let data
      try { data = await guidesApi.getByUuid(guideId) } 
      catch { data = await guidesApi.getById(guideId) }
      setGuide(data)
      setSteps(data.steps || [])
      if (data.steps?.length > 0) setSelectedStep(data.steps[0])
    } catch (error) { console.error('Failed to fetch guide:', error) }
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

  const handleMarkerDrag = useCallback(async (stepId, newX, newY) => {
    setSteps(prev => prev.map(s => s.id === stepId ? { ...s, click_x: newX, click_y: newY } : s))
    if (selectedStep?.id === stepId) setSelectedStep(prev => ({ ...prev, click_x: newX, click_y: newY }))
    try { await stepsApi.update(stepId, { click_x: newX, click_y: newY }) } catch {}
  }, [selectedStep])

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
      console.error(`Failed to export ${format}:`, error)
      alert(`Ошибка экспорта в ${format.toUpperCase()}`)
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
          <h1 style={{ fontFamily: 'Montserrat, sans-serif', fontSize: '16px', fontWeight: 600, color: '#333', margin: 0 }}>{guide.title}</h1>
          <p style={{ fontFamily: 'Roboto, sans-serif', fontSize: '12px', color: '#999', marginTop: '2px' }}>{steps.length} шагов</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {saving && <span style={{ fontSize: '12px', color: '#999' }}>Сохранение...</span>}
          <button onClick={() => navigate('/')} style={{ padding: '8px 16px', fontFamily: 'Montserrat, sans-serif', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.3px', backgroundColor: '#fff', color: '#666', border: '1px solid #e0e0e0', borderRadius: '4px', cursor: 'pointer' }}>
            ← Назад
          </button>
          <button onClick={() => handleExport('pdf')} style={{ padding: '8px 16px', fontFamily: 'Montserrat, sans-serif', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.3px', backgroundColor: '#e53e3e', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
            PDF
          </button>
          <button onClick={() => handleExport('json')} style={{ padding: '8px 16px', fontFamily: 'Montserrat, sans-serif', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.3px', backgroundColor: '#3b82f6', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
            JSON
          </button>
          <button onClick={handleSaveGuide} style={{ padding: '8px 16px', fontFamily: 'Montserrat, sans-serif', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.3px', backgroundColor: '#4caf50', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
            ✓ Сохранить
          </button>
          <button onClick={handleReadyForShorts} style={{ padding: '8px 16px', fontFamily: 'Montserrat, sans-serif', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.3px', backgroundColor: '#ed8d48', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
            Shorts →
          </button>
        </div>
      </div>

      {/* Main */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        {/* Steps sidebar - light */}
        <div style={{ width: '280px', backgroundColor: '#fff', borderRight: '1px solid #e0e0e0', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid #e0e0e0' }}>
            <span style={{ fontFamily: 'Montserrat, sans-serif', fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: '#999' }}>Шаги</span>
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {steps.map((step, index) => (
              <StepCard key={step.id} step={step} index={index} isSelected={selectedStep?.id === step.id} isFirst={index === 0} isLast={index === steps.length - 1} isEditing={editingText === step.id}
                onSelect={() => setSelectedStep(step)} onEdit={() => setEditingText(step.id)} onSave={(text) => handleTextUpdate(step.id, text)} onCancel={() => setEditingText(null)}
                onDelete={() => handleDeleteStep(step.id)} onMoveUp={() => handleMoveStep(step.id, 'up')} onMoveDown={() => handleMoveStep(step.id, 'down')} />
            ))}
          </div>
        </div>

        {/* Preview */}
        <div style={{ flex: 1, backgroundColor: '#fafafa', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '12px 20px', backgroundColor: '#fff', borderBottom: '1px solid #e0e0e0' }}>
            <span style={{ fontFamily: 'Roboto, sans-serif', fontSize: '12px', color: '#666' }}>
              Шаг {selectedStep?.step_number || '-'} — перетащите маркер
            </span>
          </div>
          <div style={{ flex: 1, overflow: 'auto', padding: '20px', display: 'flex', alignItems: 'flex-start', justifyContent: 'center' }}>
            {selectedStep?.screenshot_path ? (
              <div style={{ position: 'relative', display: 'inline-block' }}>
                <img ref={imageRef} src={storageApi.getScreenshotUrl(selectedStep.screenshot_path)} alt="" style={{ maxWidth: '100%', maxHeight: 'calc(100vh - 200px)', borderRadius: '4px', boxShadow: '0 2px 12px rgba(0,0,0,0.1)' }} draggable={false} />
                <DraggableMarker x={selectedStep.click_x} y={selectedStep.click_y} imageRef={imageRef} onDragEnd={(x, y) => handleMarkerDrag(selectedStep.id, x, y)} />
              </div>
            ) : (
              <div style={{ color: '#999', padding: '48px' }}>Нет скриншота</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function DraggableMarker({ x, y, imageRef, onDragEnd }) {
  const [isDragging, setIsDragging] = useState(false)
  const [position, setPosition] = useState({ x: x || 0, y: y || 0 })

  useEffect(() => { setPosition({ x: x || 0, y: y || 0 }) }, [x, y])

  const handleMouseDown = (e) => {
    e.preventDefault()
    setIsDragging(true)
    const handleMouseMove = (moveEvent) => {
      if (!imageRef.current) return
      const rect = imageRef.current.getBoundingClientRect()
      setPosition({
        x: Math.max(0, Math.min(imageRef.current.naturalWidth, Math.round((moveEvent.clientX - rect.left) * (imageRef.current.naturalWidth / rect.width)))),
        y: Math.max(0, Math.min(imageRef.current.naturalHeight, Math.round((moveEvent.clientY - rect.top) * (imageRef.current.naturalHeight / rect.height))))
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
    const dw = imageRef.current.clientWidth || 1, nw = imageRef.current.naturalWidth || dw
    const dh = imageRef.current.clientHeight || 1, nh = imageRef.current.naturalHeight || dh
    return { left: ((position.x || 0) / nw) * dw, top: ((position.y || 0) / nh) * dh }
  }

  const pos = getPos()
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

export default StepEditor
