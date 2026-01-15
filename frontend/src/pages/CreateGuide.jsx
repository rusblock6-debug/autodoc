import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import api from '../services/api';

function CreateGuide() {
  const navigate = useNavigate();
  const [title, setTitle] = useState('');
  const [videoFile, setVideoFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setVideoFile(file);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!title || !videoFile) {
      alert('Пожалуйста, заполните все поля');
      return;
    }

    setLoading(true);
    const formData = new FormData();
    formData.append('title', title);
    formData.append('video', videoFile);

    try {
      const response = await api.post('/guides/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(progress);
        },
      });

      navigate(`/editor/${response.data.id}`);
    } catch (error) {
      console.error('Error creating guide:', error);
      alert('Ошибка при создании гайда');
    } finally {
      setLoading(false);
    }
  };

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
            <a href="#" className="sidebar-item active">
              <i className="fas fa-plus"></i>
              <span>Создать гайд</span>
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
                <span>Создать новый гайд</span>
              </div>
            </div>
          </header>

          {/* Content Area */}
          <div className="notion-content">
            <div className="notion-page-header">
              <h1>Создать новый гайд</h1>
            </div>

            <div style={{ maxWidth: '600px', margin: '0 auto' }}>
              <form onSubmit={handleSubmit}>
                <div className="notion-setting-row">
                  <label>Название гайда</label>
                  <input
                    type="text"
                    className="notion-input"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Например: Как оформить заказ"
                    required
                  />
                </div>

                <div className="notion-setting-row">
                  <label>Видео запись</label>
                  <div
                    style={{
                      border: '2px dashed var(--notion-border)',
                      borderRadius: 'var(--radius-lg)',
                      padding: 'var(--space-10)',
                      textAlign: 'center',
                      cursor: 'pointer',
                      transition: 'all var(--transition-fast)',
                    }}
                    onClick={() => document.getElementById('videoInput').click()}
                    onDragOver={(e) => {
                      e.preventDefault();
                      e.currentTarget.style.borderColor = 'var(--notion-blue)';
                      e.currentTarget.style.background = 'var(--notion-blue-bg)';
                    }}
                    onDragLeave={(e) => {
                      e.currentTarget.style.borderColor = 'var(--notion-border)';
                      e.currentTarget.style.background = 'transparent';
                    }}
                    onDrop={(e) => {
                      e.preventDefault();
                      e.currentTarget.style.borderColor = 'var(--notion-border)';
                      e.currentTarget.style.background = 'transparent';
                      const file = e.dataTransfer.files[0];
                      if (file && file.type.startsWith('video/')) {
                        setVideoFile(file);
                      }
                    }}
                  >
                    <input
                      id="videoInput"
                      type="file"
                      accept="video/*"
                      onChange={handleFileChange}
                      style={{ display: 'none' }}
                    />
                    {videoFile ? (
                      <div>
                        <i className="fas fa-video" style={{ fontSize: '48px', color: 'var(--notion-blue)', marginBottom: 'var(--space-3)' }}></i>
                        <p style={{ fontSize: '14px', color: 'var(--notion-gray-700)', marginBottom: 'var(--space-2)' }}>
                          {videoFile.name}
                        </p>
                        <p style={{ fontSize: '12px', color: 'var(--notion-gray-500)' }}>
                          {(videoFile.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                      </div>
                    ) : (
                      <div>
                        <i className="fas fa-cloud-upload-alt" style={{ fontSize: '48px', color: 'var(--notion-gray-400)', marginBottom: 'var(--space-3)' }}></i>
                        <p style={{ fontSize: '14px', color: 'var(--notion-gray-700)', marginBottom: 'var(--space-2)' }}>
                          Перетащите видео сюда или нажмите для выбора
                        </p>
                        <p style={{ fontSize: '12px', color: 'var(--notion-gray-500)' }}>
                          Поддерживаются форматы: MP4, WebM, AVI
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                {loading && (
                  <div className="notion-progress" style={{ marginBottom: 'var(--space-5)' }}>
                    <div className="progress-track">
                      <div className="progress-fill" style={{ width: `${uploadProgress}%` }}></div>
                    </div>
                    <p>Загрузка: {uploadProgress}%</p>
                  </div>
                )}

                <div style={{ display: 'flex', gap: 'var(--space-3)', justifyContent: 'flex-end' }}>
                  <Link to="/" className="notion-btn notion-btn-secondary">
                    Отмена
                  </Link>
                  <button
                    type="submit"
                    className="notion-btn notion-btn-primary"
                    disabled={loading}
                  >
                    {loading ? (
                      <>
                        <i className="fas fa-spinner fa-spin"></i>
                        <span>Создание...</span>
                      </>
                    ) : (
                      <>
                        <i className="fas fa-check"></i>
                        <span>Создать гайд</span>
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

export default CreateGuide;
