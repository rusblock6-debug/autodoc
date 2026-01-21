import React, { useState } from 'react'

function AnnotationTools({ onAddAnnotation, onClearAll, annotations }) {
  const [selectedTool, setSelectedTool] = useState(null)
  
  const tools = [
    { id: 'circle', icon: '⭕', label: 'Круг' },
    { id: 'rect', icon: '▭', label: 'Прямоугольник' },
    { id: 'arrow', icon: '➜', label: 'Стрелка' },
  ]
  
  return (
    <div style={{ 
      display: 'flex', 
      gap: '8px', 
      padding: '12px', 
      backgroundColor: '#fff', 
      borderRadius: '8px',
      boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
      alignItems: 'center'
    }}>
      <span style={{ fontSize: '12px', color: '#666', fontWeight: 600 }}>Аннотации:</span>
      
      {tools.map(tool => (
        <button
          key={tool.id}
          onClick={() => {
            setSelectedTool(selectedTool === tool.id ? null : tool.id)
            if (selectedTool !== tool.id) {
              onAddAnnotation(tool.id)
            }
          }}
          style={{
            padding: '8px 12px',
            fontSize: '16px',
            backgroundColor: selectedTool === tool.id ? '#ed8d48' : '#f5f5f5',
            color: selectedTool === tool.id ? '#fff' : '#333',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            transition: 'all 0.2s',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}
          title={tool.label}
        >
          <span>{tool.icon}</span>
          <span style={{ fontSize: '11px' }}>{tool.label}</span>
        </button>
      ))}
      
      {annotations && annotations.length > 0 && (
        <button
          onClick={onClearAll}
          style={{
            padding: '8px 12px',
            fontSize: '11px',
            backgroundColor: '#e53e3e',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            marginLeft: '8px'
          }}
        >
          Очистить все ({annotations.length})
        </button>
      )}
    </div>
  )
}

export default AnnotationTools
