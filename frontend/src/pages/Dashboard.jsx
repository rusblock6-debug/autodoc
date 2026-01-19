import React, { useState, useEffect, useRef } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { guidesApi, exportApi } from '../services/api'

function Dashboard() {
  const { guides: contextGuides, fetchGuides } = useOutletContext() || {}
  const [guides, setGuides] = useState([])
  const [loading, setLoading] = useState(true)
  const [draggedId, setDraggedId] = useState(null)
  const [dragOverId, setDragOverId] = useState(null)

  useEffect(() => {
    if (contextGuides) {
      setGuides(contextGuides)
      setLoading(false)
    } else {
      loadGuides()
    }
  }, [contextGuides])

  const loadGuides = async () => {
    try {
      const response = await guidesApi.getAll()
      setGuides(response.items || response || [])
    } catch (error) {
      console.error('Failed to fetch guides:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (guideId, e) => {
    e.preventDefault()
    e.stopPropagation()
    if (!confirm('Удалить это руководство?')) return
    try {
      await guidesApi.delete(guideId)
      if (fetchGuides) fetchGuides()
      else loadGuides()
    } catch (error) {
      console.error('Failed to delete:', error)
    }
  }

  const handleDuplicate = async (guide, e) => {
    e.preventDefault()
    e.stopPropagation()
    try {
      // Создаём копию через API
      await guidesApi.create({
        title: `${guide.title} (копия)`,
        language: guide.language || 'ru'
      })
      if (fetchGuides) fetchGuides()
      else loadGuides()
    } catch (error) {
      console.error('Failed to duplicate:', error)
    }
  }

  const handleToggleFavorite = async (guide, e) => {
    e.preventDefault()
    e.stopPropagation()
    try {
      await guidesApi.update(guide.id, { is_favorite: !guide.is_favorite })
      if (fetchGuides) fetchGuides()
      else loadGuides()
    } catch (error) {
      console.error('Failed to toggle favorite:', error)
    }
  }

  const handleExport = async (guide, format, e) => {
    e.preventDefault()
    e.stopPropagation()
    
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

  // Drag and drop
  const handleDragStart = (e, guideId) => {
    setDraggedId(guideId)
    e.dataTransfer.effectAllowed = 'move'
  }

  const handleDragOver = (e, guideId) => {
    e.preventDefault()
    if (guideId !== draggedId) {
      setDragOverId(guideId)
    }
  }

  const handleDragLeave = () => {
    setDragOverId(null)
  }

  const handleDrop = async (e, targetId) => {
    e.preventDefault()
    setDragOverId(null)
    
    if (draggedId && targetId && draggedId !== targetId) {
      const draggedIndex = guides.findIndex(g => g.id === draggedId)
      const targetIndex = guides.findIndex(g => g.id === targetId)
      
      if (draggedIndex !== -1 && targetIndex !== -1) {
        const newGuides = [...guides]
        const [dragged] = newGuides.splice(draggedIndex, 1)
        newGuides.splice(targetIndex, 0, dragged)
        setGuides(newGuides)
        
        // TODO: сохранить порядок на сервере
        // await guidesApi.reorder(newGuides.map(g => g.id))
      }
    }
    setDraggedId(null)
  }

  const handleDragEnd = () => {
    setDraggedId(null)
    setDragOverId(null)
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px' }}>
        <div style={{ width: '24px', height: '24px', border: '2px solid #e0e0e0', borderTopColor: '#ed8d48', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    )
  }

  return (
    <div style={{ padding: '24px 32px' }}>
      {/* Header */}
      <div style={{ marginBottom: '20px' }}>
        <h1 style={{ fontFamily: 'Montserrat, sans-serif', fontSize: '18px', fontWeight: 600, color: '#333', margin: 0 }}>
          Руководства
        </h1>
        <p style={{ fontFamily: 'Roboto, sans-serif', fontSize: '12px', color: '#999', marginTop: '4px' }}>
          {guides.length} документов
        </p>
      </div>

      {guides.length === 0 ? (
        <div style={{ backgroundColor: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', padding: '48px', textAlign: 'center' }}>
          <h3 style={{ fontFamily: 'Montserrat, sans-serif', fontSize: '14px', fontWeight: 600, color: '#333', marginBottom: '8px' }}>
            Нет руководств
          </h3>
          <p style={{ fontFamily: 'Roboto, sans-serif', fontSize: '13px', color: '#666' }}>
            Начните запись через расширение Chrome
          </p>
        </div>
      ) : (
        <div style={{ backgroundColor: '#fff', border: '1px solid #e0e0e0', borderRadius: '4px', overflow: 'hidden' }}>
          {/* Table header */}
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: '40px 1fr 100px 160px', 
            padding: '8px 12px',
            backgroundColor: '#fafafa',
            borderBottom: '1px solid #e0e0e0',
            fontFamily: 'Montserrat, sans-serif',
            fontSize: '10px',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            color: '#999'
          }}>
            <span>№</span>
            <span>Название</span>
            <span>Дата</span>
            <span style={{ textAlign: 'right' }}>Действия</span>
          </div>

          {/* Table rows */}
          {guides.map((guide, index) => (
            <Link
              key={guide.id || guide.uuid}
              to={`/guide/${guide.uuid}/edit`}
              draggable
              onDragStart={(e) => handleDragStart(e, guide.id)}
              onDragOver={(e) => handleDragOver(e, guide.id)}
              onDragLeave={handleDragLeave}
              onDrop={(e) => handleDrop(e, guide.id)}
              onDragEnd={handleDragEnd}
              style={{
                display: 'grid',
                gridTemplateColumns: '40px 1fr 100px 160px',
                padding: '10px 12px',
                borderBottom: '1px solid #f0f0f0',
                textDecoration: 'none',
                color: 'inherit',
                alignItems: 'center',
                backgroundColor: dragOverId === guide.id ? 'rgba(237, 141, 72, 0.1)' : (draggedId === guide.id ? '#f5f5f5' : 'transparent'),
                opacity: draggedId === guide.id ? 0.5 : 1,
                cursor: 'grab',
                transition: 'background-color 0.15s'
              }}
              onMouseOver={(e) => { if (!draggedId) e.currentTarget.style.backgroundColor = '#fafafa' }}
              onMouseOut={(e) => { if (!draggedId && dragOverId !== guide.id) e.currentTarget.style.backgroundColor = 'transparent' }}
            >
              {/* Number */}
              <span style={{
                fontFamily: 'Montserrat, sans-serif',
                fontSize: '11px',
                fontWeight: 600,
                color: '#999'
              }}>
                {String(index + 1).padStart(2, '0')}
              </span>

              {/* Title */}
              <span style={{
                fontFamily: 'Roboto, sans-serif',
                fontSize: '13px',
                color: '#333',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}>
                {guide.title}
              </span>

              {/* Date */}
              <span style={{ fontFamily: 'Roboto, sans-serif', fontSize: '12px', color: '#999' }}>
                {new Date(guide.created_at).toLocaleDateString('ru-RU')}
              </span>

              {/* Actions */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '2px' }}>
                <IconButton 
                  onClick={(e) => handleToggleFavorite(guide, e)} 
                  title={guide.is_favorite ? 'Убрать из избранного' : 'В избранное'} 
                  icon="star" 
                  active={guide.is_favorite}
                />
                <IconButton onClick={(e) => { e.preventDefault(); e.stopPropagation() }} title="Редактировать" icon="edit" />
                <IconButton onClick={(e) => handleDuplicate(guide, e)} title="Дублировать" icon="copy" />
                <ExportButton onClick={(e) => handleExport(guide, 'pdf', e)} title="PDF" color="#e53e3e" />
                <ExportButton onClick={(e) => handleExport(guide, 'json', e)} title="JSON" color="#3b82f6" />
                <IconButton onClick={(e) => handleDelete(guide.id, e)} title="Удалить" icon="delete" danger />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function ExportButton({ onClick, title, color }) {
  const [hover, setHover] = useState(false)
  
  return (
    <button
      onClick={onClick}
      onMouseOver={() => setHover(true)}
      onMouseOut={() => setHover(false)}
      title={`Экспорт в ${title}`}
      style={{
        minWidth: '32px',
        height: '26px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: hover ? color : 'transparent',
        color: hover ? '#fff' : color,
        border: `1px solid ${color}`,
        borderRadius: '4px',
        cursor: 'pointer',
        fontSize: '9px',
        fontWeight: 600,
        fontFamily: 'Montserrat, sans-serif',
        textTransform: 'uppercase',
        letterSpacing: '0.3px',
        transition: 'all 0.15s',
        padding: '0 6px'
      }}
    >
      {title}
    </button>
  )
}

function IconButton({ onClick, title, icon, danger, active }) {
  const [hover, setHover] = useState(false)
  
  const icons = {
    star: 'M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z',
    edit: 'M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z',
    copy: 'M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z',
    delete: 'M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16'
  }

  const getColor = () => {
    if (icon === 'star' && active) return '#ed8d48'
    if (hover) return danger ? '#d32f2f' : '#ed8d48'
    return '#bbb'
  }

  return (
    <button
      onClick={onClick}
      onMouseOver={() => setHover(true)}
      onMouseOut={() => setHover(false)}
      title={title}
      style={{
        width: '26px',
        height: '26px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'transparent',
        border: 'none',
        borderRadius: '4px',
        cursor: 'pointer',
        color: getColor(),
        transition: 'all 0.15s'
      }}
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill={icon === 'star' && active ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d={icons[icon]} />
      </svg>
    </button>
  )
}

export default Dashboard
