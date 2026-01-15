import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { guidesApi, sessionsApi } from '../services/api'
import { ArrowLeftIcon, CloudArrowUpIcon, DocumentTextIcon } from '@heroicons/react/24/outline'

function CreateGuide() {
  const navigate = useNavigate()
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    language: 'ru',
    tts_voice: 'ru-RU-SvetlanaNeural'
  })
  const [dragActive, setDragActive] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [errors, setErrors] = useState({})

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    })
    // Clear error when user types
    if (errors[e.target.name]) {
      setErrors({
        ...errors,
        [e.target.name]: ''
      })
    }
  }

  const handleDrag = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    
    const files = e.dataTransfer.files
    if (files && files[0]) {
      handleFileUpload(files[0])
    }
  }

  const handleFileInput = (e) => {
    const files = e.target.files
    if (files && files[0]) {
      handleFileUpload(files[0])
    }
  }

  const handleFileUpload = async (file) => {
    // Validate file type
    const validTypes = ['video/mp4', 'video/webm', 'video/quicktime']
    if (!validTypes.includes(file.type)) {
      setErrors({ file: 'Please upload a valid video file (MP4, WebM, MOV)' })
      return
    }

    // Validate file size (max 500MB)
    if (file.size > 500 * 1024 * 1024) {
      setErrors({ file: 'File size must be less than 500MB' })
      return
    }

    setUploading(true)
    setErrors({})

    try {
      // First create the guide
      const guideData = {
        title: formData.title || 'Untitled Guide',
        language: formData.language,
        tts_voice: formData.tts_voice
      }

      const guideResponse = await guidesApi.create(guideData)
      const guideId = guideResponse.id

      // Then upload the file
      const formDataObj = new FormData()
      formDataObj.append('video', file)
      formDataObj.append('guide_id', guideId.toString())

      const sessionResponse = await sessionsApi.upload(formDataObj)
      
      // Start processing
      await sessionsApi.process(sessionResponse.session_id)
      
      // Navigate to editor
      navigate(`/guides/${guideId}/edit`)
      
    } catch (error) {
      console.error('Upload failed:', error)
      setErrors({ file: 'Upload failed. Please try again.' })
    } finally {
      setUploading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    // Validation
    const newErrors = {}
    if (!formData.title.trim()) {
      newErrors.title = 'Title is required'
    }
    
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    // If no file uploaded yet, just create empty guide
    try {
      const response = await guidesApi.create({
        title: formData.title,
        description: formData.description,
        language: formData.language,
        tts_voice: formData.tts_voice
      })
      
      navigate(`/guides/${response.id}/edit`)
    } catch (error) {
      console.error('Failed to create guide:', error)
      setErrors({ submit: 'Failed to create guide. Please try again.' })
    }
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-6">
        <button
          onClick={() => navigate('/guides')}
          className="flex items-center text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeftIcon className="w-5 h-5 mr-2" />
          Back to guides
        </button>
        
        <h1 className="text-3xl font-bold text-gray-900">Create New Guide</h1>
        <p className="mt-2 text-gray-600">
          Upload a screen recording or create an empty guide to get started
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Info */}
        <div className="card">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Guide Information</h2>
          
          <div className="space-y-4">
            <div>
              <label htmlFor="title" className="block text-sm font-medium text-gray-700 mb-1">
                Title *
              </label>
              <input
                type="text"
                id="title"
                name="title"
                value={formData.title}
                onChange={handleChange}
                className={`input-field ${errors.title ? 'border-red-300 focus:ring-red-500' : ''}`}
                placeholder="Enter guide title"
              />
              {errors.title && <p className="mt-1 text-sm text-red-600">{errors.title}</p>}
            </div>

            <div>
              <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-1">
                Description
              </label>
              <textarea
                id="description"
                name="description"
                value={formData.description}
                onChange={handleChange}
                rows={3}
                className="input-field"
                placeholder="Describe what this guide covers..."
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="language" className="block text-sm font-medium text-gray-700 mb-1">
                  Language
                </label>
                <select
                  id="language"
                  name="language"
                  value={formData.language}
                  onChange={handleChange}
                  className="input-field"
                >
                  <option value="ru">Russian</option>
                  <option value="en">English</option>
                </select>
              </div>

              <div>
                <label htmlFor="tts_voice" className="block text-sm font-medium text-gray-700 mb-1">
                  Voice for Shorts
                </label>
                <select
                  id="tts_voice"
                  name="tts_voice"
                  value={formData.tts_voice}
                  onChange={handleChange}
                  className="input-field"
                >
                  <option value="ru-RU-SvetlanaNeural">Russian (Svetlana)</option>
                  <option value="ru-RU-DmitryNeural">Russian (Dmitry)</option>
                  <option value="en-US-JennyNeural">English (Jenny)</option>
                  <option value="en-US-GuyNeural">English (Guy)</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* File Upload */}
        <div className="card">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Upload Recording</h2>
          
          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
              dragActive 
                ? 'border-blue-500 bg-blue-50' 
                : 'border-gray-300 hover:border-gray-400'
            } ${errors.file ? 'border-red-300 bg-red-50' : ''}`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <CloudArrowUpIcon className="mx-auto h-12 w-12 text-gray-400" />
            
            <div className="mt-4">
              <p className="text-lg font-medium text-gray-900">
                {uploading ? 'Uploading...' : 'Drop your screen recording here'}
              </p>
              <p className="mt-1 text-sm text-gray-500">
                or{' '}
                <label className="text-blue-600 hover:text-blue-500 cursor-pointer font-medium">
                  browse files
                  <input
                    type="file"
                    className="hidden"
                    accept="video/*"
                    onChange={handleFileInput}
                    disabled={uploading}
                  />
                </label>
              </p>
              <p className="mt-2 text-xs text-gray-500">
                Supported formats: MP4, WebM, MOV • Max size: 500MB
              </p>
            </div>

            {uploading && (
              <div className="mt-4">
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div className="bg-blue-600 h-2 rounded-full animate-pulse" style={{ width: '60%' }}></div>
                </div>
                <p className="mt-2 text-sm text-gray-600">Processing your recording...</p>
              </div>
            )}

            {errors.file && (
              <p className="mt-2 text-sm text-red-600">{errors.file}</p>
            )}
          </div>
        </div>

        {/* Submit Buttons */}
        <div className="flex space-x-4">
          <button
            type="button"
            onClick={() => navigate('/guides')}
            className="btn-secondary flex-1"
            disabled={uploading}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="btn-primary flex-1 flex items-center justify-center"
            disabled={uploading}
          >
            <DocumentTextIcon className="w-5 h-5 mr-2" />
            {uploading ? 'Creating...' : 'Create Guide'}
          </button>
        </div>

        {errors.submit && (
          <div className="rounded-md bg-red-50 p-4">
            <p className="text-sm text-red-700">{errors.submit}</p>
          </div>
        )}
      </form>
    </div>
  )
}

export default CreateGuide