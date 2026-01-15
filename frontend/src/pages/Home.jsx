import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';

function Home() {
  const [guides, setGuides] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [selectedGuide, setSelectedGuide] = useState(null);
  const [activeTab, setActiveTab] = useState('markdown');
  const [viewMode, setViewMode] = useState('gallery');
  const [openMenuId, setOpenMenuId] = useState(null);

  useEffect(() => {
    fetchGuides();
  }, []);

  const fetchGuides = async () => {
    try {
      const response = await api.get('/guides');
      // API interceptor already returns response.data, and backend returns PaginatedResponse with items
      console.log('Fetched guides response:', response);
      setGuides(response?.items || response || []);
    } catch (error) {
      console.error('Error fetching guides:', error);
      console.error('Error details:', error.response?.data || error.message);
      alert('Ошибка загрузки гайдов: ' + (error.response?.data?.detail || error.message));
      setGuides([]);
    } finally {
      setLoading(false);
    }
  };

  const filteredGuides = guides.filter(guide =>
    guide.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const openExportModal = (guide) => {
    setSelectedGuide(guide);
    setExportModalOpen(true);
  };

  const closeExportModal = () => {
    setExportModalOpen(false);
    setSelectedGuide(null);
  };

  const toggleMenu = (guideId) => {
    setOpenMenuId(openMenuId === guideId ? null : guideId);
  };

  return (
    <div className="notion-style dashboard-page">
      {/* Main Container */}
      <div className="notion-container">
        {/* Sidebar */}
        <aside className="notion-sidebar">
          <div className="sidebar-section">
            <Link to="/" className="sidebar-item active">
              <i className="fas fa-file-alt"></i>
              <span>Мои гайды</span>
            </Link>
            <a href="#" className="sidebar-item">
              <i className="fas fa-clock"></i>
              <span>Недавние</span>
            </a>
            <a href="#" className="sidebar-item">
              <i className="fas fa-star"></i>
              <span>Избранное</span>
            </a>
            <a href="#" className="sidebar-item">
              <i className="fas fa-trash"></i>
              <span>Корзина</span>
            </a>
          </div>
          <div className="sidebar-section">
            <div className="sidebar-label">Рабочие пространства</div>
            <a href="#" className="sidebar-item">
              <i className="fas fa-briefcase"></i>
              <span>Основное</span>
            </a>
          </div>
        </aside>

        {/* Main Content */}
        <main className="notion-main">
          {/* Top Bar */}
          <header className="notion-topbar">
            <div className="topbar-left">
              <div className="notion-breadcrumb">
                <i className="fas fa-file-alt"></i>
                <span>Мои гайды</span>
              </div>
            </div>
            <div className="topbar-right">
              <div className="notion-search">
                <i className="fas fa-search"></i>
                <input
                  type="text"
                  placeholder="Быстрый поиск..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                <span className="search-shortcut">⌘K</span>
              </div>
              <Link to="/create" className="notion-btn notion-btn-primary">
                <i className="fas fa-plus"></i>
                <span>Новый гайд</span>
              </Link>
              <button className="notion-btn-icon">
                <i className="fas fa-bars"></i>
              </button>
            </div>
          </header>

          {/* Content Area */}
          <div className="notion-content">
            {/* Page Title */}
            <div className="notion-page-header">
              <h1>Мои гайды</h1>
              <div className="notion-view-toggle">
                <button
                  className={`notion-view-btn ${viewMode === 'gallery' ? 'active' : ''}`}
                  onClick={() => setViewMode('gallery')}
                >
                  <i className="fas fa-th-large"></i>
                </button>
                <button
                  className={`notion-view-btn ${viewMode === 'list' ? 'active' : ''}`}
                  onClick={() => setViewMode('list')}
                >
                  <i className="fas fa-list"></i>
                </button>
              </div>
            </div>

            {/* Gallery Grid */}
            {loading ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '60px' }}>
                <div className="spinner"></div>
              </div>
            ) : (
              <div className="notion-gallery" style={viewMode === 'list' ? { gridTemplateColumns: '1fr' } : {}}>
                {/* Guide Cards */}
                {filteredGuides.map((guide) => (
                  <div key={guide.id} className="notion-card">
                    <div className="notion-card-cover">
                      <img
                        src={`data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 200'%3E%3Crect fill='%23F5F5F4' width='400' height='200'/%3E%3Crect x='30' y='30' width='340' height='25' rx='4' fill='%23E7E5E4'/%3E%3Crect x='30' y='70' width='160' height='100' rx='6' fill='%23D6D3D1'/%3E%3Crect x='210' y='70' width='160' height='45' rx='4' fill='%23E7E5E4'/%3E%3Crect x='210' y='125' width='120' height='45' rx='4' fill='%23E7E5E4'/%3E%3Ccircle cx='110' cy='120' r='20' fill='%2337352F' opacity='0.1'/%3E%3C/svg%3E`}
                        alt="Preview"
                      />
                    </div>
                    <div className="notion-card-content">
                      <h3 className="notion-card-title">{guide.title}</h3>
                      <div className="notion-card-meta">
                        <span>
                          <i className="far fa-calendar"></i> {new Date(guide.created_at).toLocaleDateString('ru-RU')}
                        </span>
                        <span>
                          <i className="fas fa-list-ol"></i> {guide.steps_count || guide.steps?.length || 0} шагов
                        </span>
                      </div>
                      <div className="notion-card-actions">
                        <Link to={`/editor/${guide.id}`} className="notion-btn-small">
                          <i className="fas fa-edit"></i>
                        </Link>
                        <button className="notion-btn-small" onClick={() => openExportModal(guide)}>
                          <i className="fas fa-download"></i>
                        </button>
                        <button className="notion-btn-small" onClick={() => toggleMenu(guide.id)}>
                          <i className="fas fa-ellipsis-h"></i>
                        </button>
                        <div className="notion-dropdown" style={{ display: openMenuId === guide.id ? 'block' : 'none' }}>
                          <a href="#"><i className="fas fa-copy"></i> Дублировать</a>
                          <a href="#"><i className="fas fa-share-alt"></i> Поделиться</a>
                          <a href="#" className="danger"><i className="fas fa-trash"></i> Удалить</a>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}

                {/* New Card */}
                <Link to="/create" className="notion-card notion-card-new">
                  <div className="new-card-content">
                    <div className="new-icon">
                      <i className="fas fa-plus"></i>
                    </div>
                    <span>Создать новый гайд</span>
                  </div>
                </Link>
              </div>
            )}
          </div>
        </main>
      </div>

      {/* Export Modal */}
      {exportModalOpen && (
        <div className="notion-modal-overlay" onClick={closeExportModal}>
          <div className="notion-modal" onClick={(e) => e.stopPropagation()}>
            <div className="notion-modal-header">
              <h2>Экспорт гайда</h2>
              <button className="notion-icon-btn" onClick={closeExportModal}>
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="notion-modal-body">
              <div className="notion-tabs">
                <button
                  className={`notion-tab ${activeTab === 'markdown' ? 'active' : ''}`}
                  onClick={() => setActiveTab('markdown')}
                >
                  Markdown
                </button>
                <button
                  className={`notion-tab ${activeTab === 'html' ? 'active' : ''}`}
                  onClick={() => setActiveTab('html')}
                >
                  HTML
                </button>
                <button
                  className={`notion-tab ${activeTab === 'pdf' ? 'active' : ''}`}
                  onClick={() => setActiveTab('pdf')}
                >
                  PDF
                </button>
              </div>
              <div className="notion-code-block">
                <pre>
                  {activeTab === 'markdown' && `# ${selectedGuide?.title}\n\n## Шаг 1\nОписание шага...\n\n![Шаг 1](screenshot_01.png)`}
                  {activeTab === 'html' && `<!DOCTYPE html>\n<html>\n<head>\n  <title>${selectedGuide?.title}</title>\n</head>\n<body>\n  <h1>${selectedGuide?.title}</h1>\n</body>\n</html>`}
                  {activeTab === 'pdf' && `PDF документ будет содержать:\n- Титульную страницу\n- Оглавление\n- Пошаговые инструкции`}
                </pre>
              </div>
              <div className="notion-modal-actions">
                <button className="notion-btn notion-btn-secondary" onClick={closeExportModal}>
                  Отмена
                </button>
                <button className="notion-btn notion-btn-secondary">
                  <i className="fas fa-copy"></i>
                  Копировать
                </button>
                <button className="notion-btn notion-btn-primary">
                  <i className="fas fa-download"></i>
                  Скачать
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Home;
