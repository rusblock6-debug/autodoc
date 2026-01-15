import React, { useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import api from '../services/api';

function ShortsGenerator() {
  const { id } = useParams();
  const [guide, setGuide] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentSlide, setCurrentSlide] = useState(0);
  const [shortsReady, setShortsReady] = useState(false);

  useEffect(() => {
    fetchGuide();
  }, [id]);

  const fetchGuide = async () => {
    try {
      const response = await api.get(`/guides/${id}`);
      setGuide(response.data);
    } catch (error) {
      console.error('Error fetching guide:', error);
    } finally {
      setLoading(false);
    }
  };

  const startGeneration = async () => {
    setGenerating(true);
    setProgress(0);

    try {
      const response = await api.post(`/guides/${id}/shorts`);
      
      // Simulate progress
      const interval = setInterval(() => {
        setProgress(prev => {
          if (prev >= 100) {
            clearInterval(interval);
            setShortsReady(true);
            setGenerating(false);
            return 100;
          }
          return prev + 5;
        });
      }, 200);
    } catch (error) {
      console.error('Error generating shorts:', error);
      setGenerating(false);
      alert('Ошибка при генерации видео');
    }
  };

  const downloadShorts = async () => {
    try {
      const response = await api.get(`/guides/${id}/shorts/download`, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${guide.title}_shorts.zip`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Error downloading shorts:', error);
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
              <i className="fas fa-video"></i>
              <span>Создать шортс</span>
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
                <span>Создать шортс</span>
              </div>
            </div>
          </header>

          {/* Content Area */}
          <div className="notion-content">
            <div className="notion-page-header">
              <h1>Создание видео-гайда</h1>
            </div>

            <div style={{ maxWidth: '600px', margin: '0 auto' }}>
              {/* Preview */}
              <div className="notion-short-preview" style={{ marginBottom: 'var(--space-6)' }}>
                <div className="notion-slideshow">
                  <div className="slide active">
                    <img
                      src={`data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 700'%3E%3Crect fill='%23FAFAF9' width='400' height='700'/%3E%3Crect x='20' y='20' width='360' height='28' rx='4' fill='%23E7E5E4'/%3E%3Crect x='40' y='100' width='320' height='44' rx='4' fill='%2337352F'/%3E%3Ctext x='200' y='130' font-family='Inter' font-size='14' fill='white' text-anchor='middle' font-weight='500'%3EШаг ${currentSlide + 1}%3C/text%3E%3C/svg%3E`}
                      alt={`Слайд ${currentSlide + 1}`}
                    />
                    <span className="slide-counter">{currentSlide + 1} / {guide?.steps?.length || 0}</span>
                  </div>
                </div>
              </div>

              {/* Info */}
              <div style={{
                background: 'var(--notion-bg-secondary)',
                padding: 'var(--space-4)',
                borderRadius: 'var(--radius-lg)',
                marginBottom: 'var(--space-5)'
              }}>
                <h3 style={{ fontSize: '14px', fontWeight: '600', color: 'var(--notion-gray-800)', marginBottom: 'var(--space-2)' }}>
                  <i className="fas fa-info-circle"></i> Информация
                </h3>
                <ul style={{ fontSize: '13px', color: 'var(--notion-gray-600)', paddingLeft: 'var(--space-5)' }}>
                  <li>Формат: вертикальное видео 9:16 (1080x1920)</li>
                  <li>Количество слайдов: {guide?.steps?.length || 0}</li>
                  <li>Озвучка: автоматическая генерация</li>
                  <li>Длительность: ~{(guide?.steps?.length || 0) * 5} секунд</li>
                </ul>
              </div>

              {/* Progress */}
              {generating && (
                <div className="notion-progress" style={{ marginBottom: 'var(--space-5)' }}>
                  <div className="progress-track">
                    <div className="progress-fill" style={{ width: `${progress}%` }}></div>
                  </div>
                  <p>Генерация видео: {progress}%</p>
                </div>
              )}

              {/* Actions */}
              <div style={{ display: 'flex', gap: 'var(--space-3)', justifyContent: 'center' }}>
                {!generating && !shortsReady && (
                  <button className="notion-btn notion-btn-primary notion-btn-large" onClick={startGeneration}>
                    <i className="fas fa-play"></i>
                    <span>Начать генерацию</span>
                  </button>
                )}

                {generating && (
                  <button className="notion-btn notion-btn-secondary notion-btn-large" disabled>
                    <i className="fas fa-spinner fa-spin"></i>
                    <span>Генерация...</span>
                  </button>
                )}

                {shortsReady && (
                  <>
                    <button className="notion-btn notion-btn-secondary" onClick={() => {
                      setShortsReady(false);
                      setProgress(0);
                    }}>
                      <i className="fas fa-redo"></i>
                      <span>Создать заново</span>
                    </button>
                    <button className="notion-btn notion-btn-primary" onClick={downloadShorts}>
                      <i className="fas fa-download"></i>
                      <span>Скачать ZIP</span>
                    </button>
                  </>
                )}
              </div>

              {/* Navigation */}
              {guide?.steps && guide.steps.length > 1 && (
                <div style={{
                  display: 'flex',
                  justifyContent: 'center',
                  gap: 'var(--space-2)',
                  marginTop: 'var(--space-5)'
                }}>
                  <button
                    className="notion-btn-icon"
                    onClick={() => setCurrentSlide(Math.max(0, currentSlide - 1))}
                    disabled={currentSlide === 0}
                  >
                    <i className="fas fa-chevron-left"></i>
                  </button>
                  <button
                    className="notion-btn-icon"
                    onClick={() => setCurrentSlide(Math.min(guide.steps.length - 1, currentSlide + 1))}
                    disabled={currentSlide === guide.steps.length - 1}
                  >
                    <i className="fas fa-chevron-right"></i>
                  </button>
                </div>
              )}

              {/* Back Link */}
              <div style={{ textAlign: 'center', marginTop: 'var(--space-6)' }}>
                <Link to={`/editor/${id}`} className="notion-btn notion-btn-secondary">
                  <i className="fas fa-arrow-left"></i>
                  <span>Назад к редактору</span>
                </Link>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default ShortsGenerator;
