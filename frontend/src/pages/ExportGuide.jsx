import React, { useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import api, { API_BASE_URL } from '../services/api';
import axios from 'axios';

function ExportGuide() {
  const { id } = useParams();
  const [guide, setGuide] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('markdown');
  const [exportContent, setExportContent] = useState('');

  useEffect(() => {
    fetchGuide();
  }, [id]);

  const fetchGuide = async () => {
    try {
      const response = await api.get(`/guides/${id}`);
      // API interceptor already returns response.data
      setGuide(response);
      generateExportContent(response, 'markdown');
    } catch (error) {
      console.error('Error fetching guide:', error);
    } finally {
      setLoading(false);
    }
  };

  const generateExportContent = (guideData, format) => {
    if (!guideData) return;

    switch (format) {
      case 'markdown':
        setExportContent(`# ${guideData.title}\n\n${guideData.steps?.map((step, i) => {
          const stepText = step.edited_text || step.original_text || step.final_text || step.normalized_text || '';
          return `## Шаг ${i + 1}\n${stepText}\n\n![Шаг ${i + 1}](screenshot_${String(i + 1).padStart(2, '0')}.png)\n`;
        }).join('\n') || ''}`);
        break;
      case 'html':
        setExportContent(`<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>${guideData.title}</title>
  <style>
    body { font-family: Inter, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
    .step { margin-bottom: 40px; }
    .step h2 { color: #37352F; }
    .step img { max-width: 100%; border-radius: 8px; }
  </style>
</head>
<body>
  <h1>${guideData.title}</h1>
  ${guideData.steps?.map((step, i) => {
    const stepText = step.edited_text || step.original_text || step.final_text || step.normalized_text || '';
    return `
  <div class="step">
    <h2>Шаг ${i + 1}</h2>
    <p>${stepText}</p>
    <img src="screenshot_${String(i + 1).padStart(2, '0')}.png" alt="Шаг ${i + 1}">
  </div>
  `;
  }).join('') || ''}
</body>
</html>`);
        break;
      case 'pdf':
        setExportContent(`PDF документ будет содержать:
- Титульную страницу с названием: "${guideData.title}"
- Оглавление со всеми ${guideData.steps?.length || 0} шагами
- Пошаговые инструкции со скриншотами
- Нумерацию страниц
- Верхний и нижний колонтитулы

Для скачивания нажмите кнопку «Скачать»`);
        break;
    }
  };

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    generateExportContent(guide, tab);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(exportContent);
    alert('Скопировано в буфер обмена!');
  };

  const handleDownload = async () => {
    try {
      // For blob responses, we need to bypass the interceptor
      const response = await axios.get(`${API_BASE_URL}/export/${id}/${activeTab}`, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${guide?.title || 'guide'}.${activeTab === 'markdown' ? 'md' : activeTab}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Error downloading:', error);
      alert('Ошибка при скачивании');
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <div className="spinner"></div>
      </div>
    );
  }

  return (
    <div className="notion-style dashboard-page">
      <div className="notion-container">
        {/* Sidebar */}
        <aside className="notion-sidebar">
          <div className="sidebar-section">
            <Link to="/" className="sidebar-item">
              <i className="fas fa-file-alt"></i>
              <span>Мои гайды</span>
            </Link>
            <Link to={`/editor/${id}`} className="sidebar-item">
              <i className="fas fa-edit"></i>
              <span>Редактор</span>
            </Link>
            <a href="#" className="sidebar-item active">
              <i className="fas fa-download"></i>
              <span>Экспорт</span>
            </a>
          </div>
        </aside>

        {/* Main Content */}
        <main className="notion-main">
          {/* Top Bar */}
          <header className="notion-topbar">
            <div className="topbar-left">
              <Link to="/" className="notion-back-btn">
                <i className="fas fa-arrow-left"></i>
              </Link>
              <div className="notion-breadcrumb">
                <i className="fas fa-file-alt"></i>
                <span>Мои гайды</span>
                <i className="fas fa-chevron-right"></i>
                <span>{guide?.title}</span>
                <i className="fas fa-chevron-right"></i>
                <span>Экспорт</span>
              </div>
            </div>
          </header>

          {/* Content Area */}
          <div className="notion-content">
            <div className="notion-page-header">
              <h1>Экспорт гайда</h1>
            </div>

            <div style={{ maxWidth: '900px', margin: '0 auto' }}>
              {/* Tabs */}
              <div className="notion-tabs">
                <button
                  className={`notion-tab ${activeTab === 'markdown' ? 'active' : ''}`}
                  onClick={() => handleTabChange('markdown')}
                >
                  <i className="fab fa-markdown"></i> Markdown
                </button>
                <button
                  className={`notion-tab ${activeTab === 'html' ? 'active' : ''}`}
                  onClick={() => handleTabChange('html')}
                >
                  <i className="fas fa-code"></i> HTML
                </button>
                <button
                  className={`notion-tab ${activeTab === 'pdf' ? 'active' : ''}`}
                  onClick={() => handleTabChange('pdf')}
                >
                  <i className="fas fa-file-pdf"></i> PDF
                </button>
              </div>

              {/* Code Block */}
              <div className="notion-code-block" style={{ maxHeight: '500px' }}>
                <pre>{exportContent}</pre>
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', gap: 'var(--space-3)', justifyContent: 'flex-end', marginTop: 'var(--space-5)' }}>
                <Link to={`/editor/${id}`} className="notion-btn notion-btn-secondary">
                  <i className="fas fa-arrow-left"></i>
                  <span>Назад к редактору</span>
                </Link>
                <button className="notion-btn notion-btn-secondary" onClick={handleCopy}>
                  <i className="fas fa-copy"></i>
                  <span>Копировать</span>
                </button>
                <button className="notion-btn notion-btn-primary" onClick={handleDownload}>
                  <i className="fas fa-download"></i>
                  <span>Скачать</span>
                </button>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default ExportGuide;
