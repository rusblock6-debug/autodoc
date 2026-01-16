import React, { useState, useEffect } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { guidesApi } from '../services/api'

function Layout() {
  const [guides, setGuides] = useState([])
  const [expandedSections, setExpandedSections] = useState({ all: true, favorites: false, drafts: false })
  const navigate = useNavigate()

  useEffect(() => {
    fetchGuides()
    const interval = setInterval(fetchGuides, 5000)
    return () => clearInterval(interval)
  }, [])

  const fetchGuides = async () => {
    try {
      const response = await guidesApi.getAll()
      setGuides(response.items || response || [])
    } catch (error) {
      console.error('Failed to fetch guides:', error)
    }
  }

  const toggleSection = (section) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }))
  }

  const allGuides = guides
  const favoriteGuides = guides.filter(g => g.is_favorite)
  const draftGuides = guides.filter(g => g.status === 'draft')

  const SidebarSection = ({ title, items, sectionKey }) => (
    <div style={{ marginBottom: '4px' }}>
      <button
        onClick={() => toggleSection(sectionKey)}
        style={{
          width: '100%',
          padding: '8px 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: 'transparent',
          border: 'none',
          cursor: 'pointer',
          fontFamily: 'Montserrat, sans-serif',
          fontSize: '11px',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          color: '#666',
          textAlign: 'left'
        }}
      >
        <span>{title}</span>
        <span style={{ fontSize: '10px', color: '#999' }}>{expandedSections[sectionKey] ? '▼' : '▶'}</span>
      </button>
      
      {expandedSections[sectionKey] && (
        <div style={{ paddingLeft: '8px' }}>
          {items.length === 0 ? (
            <div style={{ padding: '6px 16px', fontSize: '12px', color: '#bbb', fontStyle: 'italic' }}>
              Пусто
            </div>
          ) : (
            items.map((guide) => (
              <NavLink
                key={guide.id}
                to={`/guide/${guide.uuid}/edit`}
                style={({ isActive }) => ({
                  display: 'block',
                  padding: '6px 16px',
                  fontSize: '12px',
                  color: isActive ? '#ed8d48' : '#333',
                  textDecoration: 'none',
                  backgroundColor: isActive ? 'rgba(237, 141, 72, 0.08)' : 'transparent',
                  borderLeft: isActive ? '2px solid #ed8d48' : '2px solid transparent',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  transition: 'all 0.15s'
                })}
              >
                {guide.title}
              </NavLink>
            ))
          )}
        </div>
      )}
    </div>
  )

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Sidebar */}
      <aside style={{
        width: '240px',
        backgroundColor: '#fff',
        borderRight: '1px solid #e0e0e0',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0
      }}>
        {/* Logo */}
        <div style={{
          padding: '16px 16px',
          borderBottom: '1px solid #e0e0e0',
          display: 'flex',
          alignItems: 'center',
          gap: '10px'
        }}>
          <div style={{
            width: '28px',
            height: '28px',
            backgroundColor: '#ed8d48',
            borderRadius: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <span style={{ color: '#fff', fontFamily: 'Montserrat, sans-serif', fontWeight: 700, fontSize: '10px' }}>НД</span>
          </div>
          <span style={{ fontFamily: 'Montserrat, sans-serif', fontSize: '13px', fontWeight: 600, color: '#333' }}>НИР-Документ</span>
        </div>

        {/* Navigation sections */}
        <nav style={{ flex: 1, paddingTop: '12px', overflowY: 'auto' }}>
          <SidebarSection title="Все руководства" items={allGuides} sectionKey="all" />
          <SidebarSection title="Избранное" items={favoriteGuides} sectionKey="favorites" />
          <SidebarSection title="Черновики" items={draftGuides} sectionKey="drafts" />
        </nav>
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, backgroundColor: '#fafafa', overflow: 'auto' }}>
        <Outlet context={{ guides, fetchGuides }} />
      </main>
    </div>
  )
}

export default Layout
