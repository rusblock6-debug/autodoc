import React, { useState, useEffect, useRef } from 'react';
import { Link, useParams } from 'react-router-dom';
import api from '../services/api';

function GuideEditor() {
  const { id } = useParams();
  const [guide, setGuide] = useState(null);
  const [steps, setSteps] = useState([]);
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(true);
  const [title, setTitle] = useState('');
  const [instruction, setInstruction] = useState('');
  const [markerPosition, setMarkerPosition] = useState({ x: 68, y: 55 });
  const [isDragging, setIsDragging] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [previewModalOpen, setPreviewModalOpen] = useState(false);
  const [shortsModalOpen, setShortsModalOpen] = useState(false);
  const [exportDropdownOpen, setExportDropdownOpen] = useState(false);
  const [openStepMenu, setOpenStepMenu] = useState(null);
  
  const screenshotContainerRef = useRef(null);
  const markerRef = useRef(null);

  useEffect(() => {
    if (id) {
      fetchGuide();
    }
  }, [id]);

  const fetchGuide = async () => {
    try {
      console.log('Fetching guide with id:', id);
      const response = await api.get(`/guides/${id}`);
      console.log('Fetched guide response:', response);
      // API interceptor already returns response.data
      setGuide(response);
      setTitle(response?.title || '');
      setSteps(response?.steps || []);
      if (response?.steps && response.steps.length > 0) {
        // Use edited_text if available, otherwise original_text, otherwise final_text
        const firstStep = response.steps[0];
        setInstruction(firstStep.edited_text || firstStep.original_text || firstStep.final_text || '');
      }
    } catch (error) {
      console.error('Error fetching guide:', error);
      console.error('Error response:', error.response);
      console.error('Error data:', error.response?.data);
      alert('Ошибка загрузки гайда: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const handleMouseDown = (e) => {
    setIsDragging(true);
  };

  const handleMouseMove = (e) => {
    if (!isDragging || !screenshotContainerRef.current) return;

    const rect = screenshotContainerRef.current.getBoundingClientRect();
    let x = e.clientX - rect.left;
    let y = e.clientY - rect.top;

    const markerSize = 40;
    x = Math.max(markerSize / 2, Math.min(x, rect.width - markerSize / 2));
    y = Math.max(markerSize / 2, Math.min(y, rect.height - markerSize / 2));

    const percentX = (x / rect.width) * 100;
    const percentY = (y / rect.height) * 100;

    setMarkerPosition({ x: percentX, y: percentY });
    setHasChanges(true);
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    } else {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  const saveDraft = async () => {
    try {
      console.log('Saving draft for guide:', id);
      // API uses PATCH, not PUT
      await api.patch(`/guides/${id}`, {
        title,
        // Steps should be updated separately via steps API
      });
      
      // Update current step instruction if changed
      if (steps[currentStep - 1]) {
        const step = steps[currentStep - 1];
        const currentText = step.edited_text || step.original_text || step.final_text || '';
        if (instruction !== currentText && step.id) {
          console.log('Updating step:', step.id, 'with edited_text:', instruction);
          await api.patch(`/steps/${step.id}/text`, {
            edited_text: instruction
          });
        } else if (!step.id) {
          console.warn('Step has no ID, cannot update');
        }
      }
      
      setHasChanges(false);
      showNotification('Черновик сохранен');
    } catch (error) {
      console.error('Error saving draft:', error);
      console.error('Error response:', error.response);
      console.error('Error data:', error.response?.data);
      const errorMessage = error.response?.data?.detail || error.response?.data?.message || error.message || 'Неизвестная ошибка';
      showNotification('Ошибка сохранения: ' + errorMessage);
    }
  };

  const addNewStep = () => {
    // For MVP: just add step locally, user can save later
    const stepNumber = steps.length + 1;
    const stepText = `Новый шаг ${stepNumber}`;
    
    const newStep = {
      id: null, // Temporary, will be created on save
      step_number: stepNumber,
      original_text: stepText,
      edited_text: stepText,
      final_text: stepText,
      guide_id: parseInt(id),
    };
    
    setSteps([...steps, newStep]);
    setCurrentStep(stepNumber);
    setInstruction(stepText);
    setHasChanges(true);
    showNotification('Шаг добавлен (сохраните для применения)');
  };

  const switchToStep = (stepNum) => {
    setCurrentStep(stepNum);
    const step = steps[stepNum - 1];
    if (step) {
      // Use edited_text if available, otherwise original_text, otherwise final_text
      setInstruction(step.edited_text || step.original_text || step.final_text || '');
    }
  };

  const toggleStepMenu = (stepNum) => {
    setOpenStepMenu(openStepMenu === stepNum ? null : stepNum);
  };

  const showNotification = (message) => {
    // Simple notification implementation
    const notification = document.createElement('div');
    notification.className = 'editor-notification';
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed;
      bottom: 24px;
      left: 50%;
      transform: translateX(-50%);
      padding: 12px 24px;
      background: #37352F;
      color: white;
      border-radius: 6px;
      font-size: 14px;
      font-weight: 500;
      z-index: 1001;
      animation: slideUp 0.3s ease;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    `;
    document.body.appendChild(notification);
    setTimeout(() => {
      notification.style.animation = 'fadeOut 0.3s ease forwards';
      setTimeout(() => notification.remove(), 300);
    }, 2000);
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <div className="spinner"></div>
      </div>
    );
  }

  return (
    <div className="notion-style editor-page">
      {/* Top Bar */}
      <header className="notion-topbar notion-topbar-editor">
        <div className="topbar-left">
          <Link to="/" className="notion-back-btn">
            <i className="fas fa-arrow-left"></i>
          </Link>
          <div className="notion-breadcrumb">
            <i className="fas fa-file-alt"></i>
            <span>Мои гайды</span>
            <i className="fas fa-chevron-right"></i>
            <span>{title}</span>
          </div>
        </div>
        <div className="topbar-right">
          <button 
            className={`notion-btn notion-btn-secondary ${hasChanges ? 'changed' : ''}`}
            onClick={saveDraft}
          >
            <i className="fas fa-save"></i>
            <span>{hasChanges ? 'Сохранить' : 'Сохранено'}</span>
          </button>
          <button className="notion-btn notion-btn-secondary" onClick={() => setPreviewModalOpen(true)}>
            <i className="fas fa-eye"></i>
            <span>Предпросмотр</span>
          </button>
          <div className="notion-dropdown">
            <button 
              className="notion-btn notion-btn-primary"
              onClick={() => setExportDropdownOpen(!exportDropdownOpen)}
            >
              <i className="fas fa-download"></i>
              <span>Экспорт</span>
              <i className="fas fa-caret-down"></i>
            </button>
            {exportDropdownOpen && (
              <div className="notion-dropdown-menu">
                <a href="#"><i className="fab fa-markdown"></i> Markdown</a>
                <a href="#"><i className="fas fa-code"></i> HTML</a>
                <a href="#"><i className="fas fa-file-pdf"></i> PDF</a>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Editor */}
      <div className="notion-editor-container">
        {/* Left Panel - Canvas */}
        <div className="notion-editor-main">
          {/* Document Title */}
          <div className="notion-doc-header">
            <input
              type="text"
              className="notion-title-input"
              value={title}
              onChange={(e) => {
                setTitle(e.target.value);
                setHasChanges(true);
              }}
              placeholder="Название гайда..."
            />
          </div>

          {/* Canvas Area */}
          <div className="notion-canvas">
            <div className="notion-canvas-header">
              <div className="step-indicator">
                <span className="step-number">
                  Шаг <strong>{currentStep}</strong>
                </span>
                <span className="step-total">из <span>{steps.length}</span></span>
              </div>
              <p className="step-hint">Перетащите маркер на нужный элемент</p>
            </div>

            <div className="notion-canvas-wrapper">
              <div 
                className="notion-screenshot-container"
                ref={screenshotContainerRef}
              >
                <img
                  src="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 800 500'%3E%3Crect fill='%23FAFAF9' width='800' height='500'/%3E%3Crect x='20' y='20' width='760' height='36' rx='4' fill='%23E7E5E4'/%3E%3Ccircle cx='44' cy='38' r='10' fill='%23EF4444'/%3E%3Ccircle cx='68' cy='38' r='10' fill='%23F59E0B'/%3E%3Ccircle cx='92' cy='38' r='10' fill='%2322C55E'/%3E%3Crect x='140' y='28' width='180' height='20' rx='4' fill='%23D6D3D1'/%3E%3Crect x='25' y='76' width='280' height='380' rx='6' fill='%23FFFFFF' stroke='%23E7E5E4'/%3E%3Ctext x='45' y='106' font-family='Inter' font-size='14' fill='%23737373'%3EEmail%3C/text%3E%3Crect x='45' y='116' width='240' height='32' rx='4' fill='%23F5F5F4' stroke='%23E5E5E5'/%3E%3Ctext x='45' y='176' font-family='Inter' font-size='14' fill='%23737373'%3EПароль%3C/text%3E%3Crect x='45' y='186' width='240' height='32' rx='4' fill='%23F5F5F4' stroke='%23E5E5E5'/%3E%3Crect x='45' y='246' width='240' height='36' rx='4' fill='%2337352F'/%3E%3Ctext x='165' y='270' font-family='Inter' font-size='13' fill='white' font-weight='500'%3EВойти%3C/text%3E%3Crect x='395' y='76' width='380' height='380' rx='6' fill='%23FFFFFF' stroke='%23E7E5E4'/%3E%3Crect x='415' y='96' width='90' height='28' rx='4' fill='%2337352F'/%3E%3Crect x='415' y='146' width='340' height='22' rx='3' fill='%23E7E5E4'/%3E%3Crect x='415' y='186' width='280' height='22' rx='3' fill='%23E7E5E4'/%3E%3Crect x='415' y='226' width='200' height='22' rx='3' fill='%23E7E5E4'/%3E%3Crect x='415' y='346' width='340' height='44' rx='4' fill='%2322C55E'/%3E%3Ctext x='515' y='378' font-family='Inter' font-size='13' fill='white' font-weight='500'%3EОформить заказ%3C/text%3E%3C/svg%3E"
                  alt="Screenshot"
                  className="notion-screenshot-img"
                />

                {/* Draggable Marker */}
                <div
                  ref={markerRef}
                  className={`notion-marker ${isDragging ? 'dragging' : ''}`}
                  style={{ left: `${markerPosition.x}%`, top: `${markerPosition.y}%` }}
                  onMouseDown={handleMouseDown}
                >
                  <span className="marker-number">{currentStep}</span>
                  <div className="marker-ring"></div>
                </div>
              </div>
            </div>

            {/* Tools */}
            <div className="notion-canvas-tools">
              <button className="notion-tool-btn" title="Увеличить">
                <i className="fas fa-search-plus"></i>
              </button>
              <button className="notion-tool-btn" title="Уменьшить">
                <i className="fas fa-search-minus"></i>
              </button>
              <button className="notion-tool-btn" title="Размыть область">
                <i className="fas fa-eye-slash"></i>
              </button>
              <button className="notion-tool-btn" title="Нарисовать стрелку">
                <i className="fas fa-long-arrow-alt-right"></i>
              </button>
            </div>

            {/* Instruction */}
            <div className="notion-instruction-block">
              <div className="notion-block-header">
                <i className="fas fa-align-left"></i>
                <span>Инструкция</span>
              </div>
              <textarea
                className="notion-textarea"
                rows="3"
                value={instruction}
                onChange={(e) => {
                  setInstruction(e.target.value);
                  setHasChanges(true);
                }}
                placeholder="Введите инструкцию для этого шага..."
              />
              <div className="notion-block-footer">
                <i className="fas fa-info-circle"></i>
                <span>Исходный текст будет улучшен с помощью AI</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Panel - Steps */}
        <aside className="notion-steps-sidebar">
          <div className="notion-sidebar-header">
            <h3>Шаги</h3>
            <button className="notion-btn-icon-sm" onClick={addNewStep} title="Добавить шаг">
              <i className="fas fa-plus"></i>
            </button>
          </div>

          <div className="notion-steps-list">
            {steps.map((step, index) => (
              <div
                key={index}
                className={`notion-step-item ${currentStep === index + 1 ? 'active' : ''}`}
                onClick={() => switchToStep(index + 1)}
              >
                <div className="notion-step-thumb">
                  <img
                    src={`data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 80'%3E%3Crect fill='%23FAFAF9' width='120' height='80'/%3E%3Crect x='8' y='8' width='104' height='12' rx='2' fill='%23E7E5E4'/%3E%3Crect x='8' y='28' width='50' height='20' rx='2' fill='%23F5F5F4'/%3E%3Ccircle cx='20' cy='38' r='8' fill='%2337352F'/%3E%3Crect x='8' y='56' width='70' height='10' rx='2' fill='%23E7E5E4'/%3E%3C/svg%3E`}
                    alt={`Шаг ${index + 1}`}
                  />
                  <span className="step-num">{index + 1}</span>
                </div>
                <div className="notion-step-content">
                  <p>{step.edited_text || step.original_text || step.final_text || `Шаг ${index + 1}`}</p>
                  <div className="notion-step-actions">
                    <button className="notion-btn-icon-sm" title="Редактировать">
                      <i className="fas fa-edit"></i>
                    </button>
                    <button className="notion-btn-icon-sm" title="Дублировать">
                      <i className="fas fa-copy"></i>
                    </button>
                  </div>
                </div>
                <button
                  className="notion-btn-icon-sm step-menu-toggle"
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleStepMenu(index + 1);
                  }}
                >
                  <i className="fas fa-ellipsis-h"></i>
                </button>
                {openStepMenu === index + 1 && (
                  <div className="notion-step-menu">
                    <a href="#"><i className="fas fa-link"></i> Связать со следующим</a>
                    <a href="#" className="danger"><i className="fas fa-trash"></i> Удалить</a>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Footer Actions */}
          <div className="notion-sidebar-footer">
            <button className="notion-btn notion-btn-secondary notion-btn-block">
              <i className="fas fa-volume-up"></i>
              <span>Озвучить шаги</span>
            </button>
            <button
              className="notion-btn notion-btn-secondary notion-btn-block"
              onClick={() => setShortsModalOpen(true)}
            >
              <i className="fas fa-video"></i>
              <span>Создать шортс</span>
            </button>
          </div>
        </aside>
      </div>

      {/* Preview Modal */}
      {previewModalOpen && (
        <div className="notion-modal-overlay" onClick={() => setPreviewModalOpen(false)}>
          <div className="notion-modal notion-modal-large" onClick={(e) => e.stopPropagation()}>
            <div className="notion-modal-header">
              <h2>Предпросмотр гайда</h2>
              <button className="notion-icon-btn" onClick={() => setPreviewModalOpen(false)}>
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="notion-modal-body">
              <div className="notion-preview-content">
                {steps.map((step, index) => {
                  const stepText = step.edited_text || step.original_text || step.final_text || step.normalized_text || '';
                  return (
                    <div key={index} className="notion-preview-step">
                      <h3>Шаг {index + 1}. {stepText}</h3>
                      <div className="notion-preview-image">
                        <img
                          src={`data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 800 500'%3E%3Crect fill='%23FAFAF9' width='800' height='500'/%3E%3C/svg%3E`}
                          alt={`Шаг ${index + 1}`}
                        />
                      </div>
                      <p>{stepText}</p>
                      {index < steps.length - 1 && <hr className="notion-divider" />}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Shorts Modal */}
      {shortsModalOpen && (
        <div className="notion-modal-overlay" onClick={() => setShortsModalOpen(false)}>
          <div className="notion-modal" onClick={(e) => e.stopPropagation()}>
            <div className="notion-modal-header">
              <h2>Создание видео-гайда</h2>
              <button className="notion-icon-btn" onClick={() => setShortsModalOpen(false)}>
                <i className="fas fa-times"></i>
              </button>
            </div>
            <div className="notion-modal-body">
              <div className="notion-short-preview">
                <div className="notion-slideshow">
                  <div className="slide active">
                    <img
                      src={`data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 700'%3E%3Crect fill='%23FAFAF9' width='400' height='700'/%3E%3Crect x='20' y='20' width='360' height='28' rx='4' fill='%23E7E5E4'/%3E%3Crect x='40' y='100' width='320' height='44' rx='4' fill='%2337352F'/%3E%3Ctext x='200' y='130' font-family='Inter' font-size='14' fill='white' text-anchor='middle' font-weight='500'%3EШаг 1%3C/text%3E%3C/svg%3E`}
                      alt="Слайд 1"
                    />
                    <span className="slide-counter">1 / {steps.length}</span>
                  </div>
                </div>
              </div>
              <div className="notion-progress">
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: '20%' }}></div>
                </div>
                <p>Генерация видео: 20%</p>
              </div>
              <div className="notion-modal-actions">
                <button className="notion-btn notion-btn-secondary" onClick={() => setShortsModalOpen(false)}>
                  Отмена
                </button>
                <button className="notion-btn notion-btn-primary">
                  <i className="fas fa-download"></i>
                  Скачать ZIP
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default GuideEditor;
