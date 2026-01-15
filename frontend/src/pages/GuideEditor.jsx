import React, { useState, useRef, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { DndProvider, useDrag, useDrop } from 'react-dnd'
import { HTML5Backend } from 'react-dnd-html5-backend'
import { guidesApi, stepsApi } from '../services/api'
import { 
  ArrowLeftIcon, 
  ArrowPathIcon, 
  ArrowsPointingOutIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  TrashIcon,
  PencilIcon,
  CheckIcon,
  XMarkIcon
} from '@heroicons/react/24/outline'

// Draggable marker component
const Marker = ({ step, onUpdatePosition }) => {
  const [{ isDragging }, drag] = useDrag(() => ({
    type: 'marker',
    item: { id: step.id, x: step.click_x, y: step.click_y },
    collect: (monitor) => ({
      isDragging: !!monitor.isDragging(),
    }),
  }))

  const handleMouseDown = (e) => {
    e.preventDefault()
    const rect = e.currentTarget.parentElement.getBoundingClientRect()
    const startX = e.clientX - rect.left
    const startY = e.clientY - rect.top
    
    const handleMouseMove = (moveEvent) => {
      const newX = Math.max(0, Math.min(rect.width - 32, moveEvent.clientX - rect.left - 16))
      const newY = Math.max(0, Math.min(rect.height - 32, moveEvent.clientY - rect.top - 16))
      onUpdatePosition(step.id, newX, newY)
    }

    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }

  return (
    <div
      ref={drag}
      className="click-marker"
      style={{
        left: `${step.click_x}px`,
        top: `${step.click_y}px`,
        opacity: isDragging ? 0.5 : 1,
        cursor: 'move'
      }}
      onMouseDown={handleMouseDown}
    />
  )
}

// Step card component
const StepCard = ({ step, index, onUpdate, onDelete, onMove, totalSteps }) => {
  const [isEditing, setIsEditing] = useState(false)
  const [editText, setEditText] = useState(step.text)
  const textareaRef = useRef(null)

  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.focus()
      textareaRef.current.select()
    }
  }, [isEditing])

  const handleSave = () => {
    if (editText.trim()) {
      onUpdate(step.id, { text: editText.trim() })
      setIsEditing(false)
    }
  }

  const handleCancel = () => {
    setEditText(step.text)
    setIsEditing(false)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      handleSave()
    } else if (e.key === 'Escape') {
      handleCancel()
    }
  }

  return (
    <div className="step-card p-4">
      <div className="flex items-start space-x-4">
        {/* Step number */}
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 text-blue-800 flex items-center justify-center font-medium">
          {index + 1}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {isEditing ? (
            <div className="space-y-3">
              <textarea
                ref={textareaRef}
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                onKeyDown={handleKeyDown}
                className="input-field w-full"
                rows={3}
              />
              <div className="flex space-x-2">
                <button
                  onClick={handleSave}
                  className="btn-success flex items-center space-x-1"
                >
                  <CheckIcon className="w-4 h-4" />
                  <span>Save</span>
                </button>
                <button
                  onClick={handleCancel}
                  className="btn-secondary flex items-center space-x-1"
                >
                  <XMarkIcon className="w-4 h-4" />
                  <span>Cancel</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="group">
              <p className="text-gray-900">{step.text}</p>
              <button
                onClick={() => setIsEditing(true)}
                className="mt-2 text-blue-600 hover:text-blue-800 text-sm flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <PencilIcon className="w-4 h-4" />
                <span>Edit text</span>
              </button>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex-shrink-0 flex space-x-1">
          {index > 0 && (
            <button
              onClick={() => onMove(index, index - 1)}
              className="p-1 text-gray-400 hover:text-gray-600"
              title="Move up"
            >
              <ChevronLeftIcon className="w-5 h-5 rotate-90" />
            </button>
          )}
          {index < totalSteps - 1 && (
            <button
              onClick={() => onMove(index, index + 1)}
              className="p-1 text-gray-400 hover:text-gray-600"
              title="Move down"
            >
              <ChevronRightIcon className="w-5 h-5 -rotate-90" />
            </button>
          )}
          <button
            onClick={() => onDelete(step.id)}
            className="p-1 text-gray-400 hover:text-red-500"
            title="Delete step"
          >
            <TrashIcon className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  )
}

// Main editor component
function GuideEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [guide, setGuide] = useState(null)
  const [steps, setSteps] = useState([])
  const [loading, setLoading] = useState(true)
  const [imageLoaded, setImageLoaded] = useState(false)
  const imageRef = useRef(null)

  useEffect(() => {
    fetchGuide()
  }, [id])

  const fetchGuide = async () => {
    try {
      setLoading(true)
      const [guideData, stepsData] = await Promise.all([
        guidesApi.getById(id),
        stepsApi.getByGuideId(id)
      ])
      setGuide(guideData)
      setSteps(stepsData.items || [])
    } catch (error) {
      console.error('Failed to fetch guide:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleMarkerUpdate = async (stepId, x, y) => {
    try {
      // Convert pixel coordinates to relative coordinates (0-1)
      const img = imageRef.current
      if (!img) return
      
      const relativeX = x / img.offsetWidth
      const relativeY = y / img.offsetHeight
      
      await stepsApi.update(stepId, {
        click_x: relativeX,
        click_y: relativeY
      })
      
      // Update local state
      setSteps(prev => prev.map(step => 
        step.id === stepId 
          ? { ...step, click_x: relativeX, click_y: relativeY }
          : step
      ))
    } catch (error) {
      console.error('Failed to update marker position:', error)
    }
  }

  const handleStepUpdate = async (stepId, updates) => {
    try {
      await stepsApi.update(stepId, updates)
      setSteps(prev => prev.map(step => 
        step.id === stepId ? { ...step, ...updates } : step
      ))
    } catch (error) {
      console.error('Failed to update step:', error)
    }
  }

  const handleStepDelete = async (stepId) => {
    if (window.confirm('Are you sure you want to delete this step?')) {
      try {
        await stepsApi.delete(stepId)
        setSteps(prev => prev.filter(step => step.id !== stepId))
      } catch (error) {
        console.error('Failed to delete step:', error)
      }
    }
  }

  const handleStepMove = async (fromIndex, toIndex) => {
    try {
      const newSteps = [...steps]
      const [movedStep] = newSteps.splice(fromIndex, 1)
      newSteps.splice(toIndex, 0, movedStep)
      
      // Update step numbers
      const reorderedSteps = newSteps.map((step, index) => ({
        ...step,
        step_number: index + 1
      }))
      
      setSteps(reorderedSteps)
      
      // Send reorder request to backend
      const stepOrder = reorderedSteps.map(step => step.id)
      await stepsApi.reorder(id, stepOrder)
      
    } catch (error) {
      console.error('Failed to reorder steps:', error)
      fetchGuide() // Re-fetch to restore original order
    }
  }

  const handleRegenerate = async () => {
    // TODO: Implement regeneration logic
    console.log('Regenerate clicked')
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  if (!guide) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Guide not found</p>
      </div>
    )
  }

  return (
    <DndProvider backend={HTML5Backend}>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => navigate('/guides')}
            className="flex items-center text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeftIcon className="w-5 h-5 mr-2" />
            Back to guides
          </button>
          
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">{guide.title}</h1>
              <p className="mt-1 text-gray-600">
                Edit your step-by-step guide and adjust click positions
              </p>
            </div>
            <div className="flex space-x-3">
              <button
                onClick={handleRegenerate}
                className="btn-secondary flex items-center space-x-2"
              >
                <ArrowPathIcon className="w-5 h-5" />
                <span>Regenerate</span>
              </button>
              <button
                onClick={() => navigate(`/guides/${id}/export`)}
                className="btn-primary"
              >
                Export Guide
              </button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Preview Panel */}
          <div className="card">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Preview</h2>
            
            <div className="relative bg-gray-100 rounded-lg overflow-hidden">
              {guide.screenshots && guide.screenshots[0] ? (
                <>
                  <img
                    ref={imageRef}
                    src={guide.screenshots[0].url}
                    alt="Guide preview"
                    className="w-full h-auto max-h-[500px] object-contain"
                    onLoad={() => setImageLoaded(true)}
                  />
                  {imageLoaded && steps.map((step) => (
                    <Marker
                      key={step.id}
                      step={step}
                      onUpdatePosition={handleMarkerUpdate}
                    />
                  ))}
                </>
              ) : (
                <div className="h-96 flex items-center justify-center text-gray-500">
                  <ArrowsPointingOutIcon className="w-12 h-12 mx-auto mb-2" />
                  <p>No screenshot available</p>
                </div>
              )}
            </div>
            
            <div className="mt-4 text-sm text-gray-500">
              Drag the yellow markers to adjust click positions
            </div>
          </div>

          {/* Steps Editor */}
          <div className="card">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">
              Steps ({steps.length})
            </h2>
            
            <div className="space-y-4 max-h-[600px] overflow-y-auto pr-2">
              {steps.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <p>No steps generated yet</p>
                  <p className="text-sm mt-1">Start by uploading a recording</p>
                </div>
              ) : (
                steps.map((step, index) => (
                  <StepCard
                    key={step.id}
                    step={step}
                    index={index}
                    totalSteps={steps.length}
                    onUpdate={handleStepUpdate}
                    onDelete={handleStepDelete}
                    onMove={handleStepMove}
                  />
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </DndProvider>
  )
}

export default GuideEditor