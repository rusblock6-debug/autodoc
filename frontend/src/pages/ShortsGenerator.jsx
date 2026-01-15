import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { guidesApi, shortsApi } from '../services/api'
import { 
  ArrowLeftIcon, 
  VideoCameraIcon, 
  PlayIcon, 
  ArrowPathIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline'

function ShortsGenerator() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [guide, setGuide] = useState(null)
  const [steps, setSteps] = useState([])
  const [loading, setLoading] = useState(true)
  const [generationStatus, setGenerationStatus] = useState('idle') // idle, generating, completed, failed
  const [taskId, setTaskId] = useState(null)
  const [progress, setProgress] = useState(0)
  const [selectedVoice, setSelectedVoice] = useState('ru-RU-SvetlanaNeural')
  const [videoUrl, setVideoUrl] = useState(null)

  const voices = [
    { id: 'ru-RU-SvetlanaNeural', name: 'Russian Female (Svetlana)', lang: 'ru' },
    { id: 'ru-RU-DmitryNeural', name: 'Russian Male (Dmitry)', lang: 'ru' },
    { id: 'en-US-JennyNeural', name: 'English Female (Jenny)', lang: 'en' },
    { id: 'en-US-GuyNeural', name: 'English Male (Guy)', lang: 'en' }
  ]

  useEffect(() => {
    fetchGuide()
  }, [id])

  useEffect(() => {
    if (taskId && generationStatus === 'generating') {
      const interval = setInterval(checkStatus, 2000)
      return () => clearInterval(interval)
    }
  }, [taskId, generationStatus])

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

  const checkStatus = async () => {
    try {
      const response = await shortsApi.getStatus(taskId)
      setProgress(response.progress || 0)
      
      if (response.status === 'completed') {
        setGenerationStatus('completed')
        setVideoUrl(response.video_url)
      } else if (response.status === 'failed') {
        setGenerationStatus('failed')
      }
    } catch (error) {
      console.error('Failed to check status:', error)
    }
  }

  const handleGenerate = async () => {
    try {
      setGenerationStatus('generating')
      setProgress(0)
      
      const response = await shortsApi.generate(id, {
        voice: selectedVoice,
        format: 'vertical', // 9:16 aspect ratio
        quality: 'high'
      })
      
      setTaskId(response.task_id)
      
    } catch (error) {
      console.error('Generation failed:', error)
      setGenerationStatus('failed')
    }
  }

  const handleDownload = async () => {
    try {
      const blob = await shortsApi.download(taskId)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${guide.title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_shorts.mp4`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Download failed:', error)
    }
  }

  const handleRegenerate = () => {
    setGenerationStatus('idle')
    setVideoUrl(null)
    setTaskId(null)
    setProgress(0)
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-6">
        <button
          onClick={() => navigate(`/guides/${id}/edit`)}
          className="flex items-center text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeftIcon className="w-5 h-5 mr-2" />
          Back to editor
        </button>
        
        <h1 className="text-3xl font-bold text-gray-900">Generate Shorts</h1>
        <p className="mt-2 text-gray-600">
          Create vertical videos with voice narration for social media platforms
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Settings Panel */}
        <div className="lg:col-span-1">
          <div className="card sticky top-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Settings</h2>
            
            <div className="space-y-6">
              {/* Voice Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Voice Narration
                </label>
                <div className="space-y-2">
                  {voices.map((voice) => (
                    <label key={voice.id} className="flex items-center">
                      <input
                        type="radio"
                        name="voice"
                        value={voice.id}
                        checked={selectedVoice === voice.id}
                        onChange={(e) => setSelectedVoice(e.target.value)}
                        className="h-4 w-4 text-blue-600 focus:ring-blue-500"
                        disabled={generationStatus === 'generating'}
                      />
                      <span className="ml-3 text-sm text-gray-700">
                        {voice.name}
                      </span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Guide Info */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="font-medium text-gray-900 mb-2">Guide Details</h3>
                <div className="space-y-2 text-sm text-gray-600">
                  <div><span className="font-medium">Title:</span> {guide?.title}</div>
                  <div><span className="font-medium">Steps:</span> {steps.length}</div>
                  <div><span className="font-medium">Duration:</span> ~{steps.length * 5}s</div>
                </div>
              </div>

              {/* Action Buttons */}
              {generationStatus === 'idle' && (
                <button
                  onClick={handleGenerate}
                  disabled={steps.length === 0}
                  className="btn-primary w-full flex items-center justify-center space-x-2 disabled:opacity-50"
                >
                  <VideoCameraIcon className="w-5 h-5" />
                  <span>Generate Shorts</span>
                </button>
              )}

              {generationStatus === 'generating' && (
                <div className="space-y-4">
                  <div className="bg-blue-50 rounded-lg p-4">
                    <div className="flex items-center">
                      <ArrowPathIcon className="w-5 h-5 text-blue-500 animate-spin mr-2" />
                      <span className="text-blue-800 font-medium">Generating...</span>
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Progress</span>
                      <span>{Math.round(progress)}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div 
                        className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${progress}%` }}
                      ></div>
                    </div>
                  </div>
                </div>
              )}

              {generationStatus === 'completed' && (
                <div className="space-y-3">
                  <div className="bg-green-50 rounded-lg p-4">
                    <div className="flex items-center">
                      <CheckCircleIcon className="w-5 h-5 text-green-500 mr-2" />
                      <span className="text-green-800 font-medium">Ready!</span>
                    </div>
                  </div>
                  
                  <button
                    onClick={handleDownload}
                    className="btn-success w-full flex items-center justify-center space-x-2"
                  >
                    <PlayIcon className="w-5 h-5" />
                    <span>Download Video</span>
                  </button>
                  
                  <button
                    onClick={handleRegenerate}
                    className="btn-secondary w-full flex items-center justify-center space-x-2"
                  >
                    <ArrowPathIcon className="w-5 h-5" />
                    <span>Regenerate</span>
                  </button>
                </div>
              )}

              {generationStatus === 'failed' && (
                <div className="space-y-3">
                  <div className="bg-red-50 rounded-lg p-4">
                    <div className="flex items-center">
                      <ExclamationTriangleIcon className="w-5 h-5 text-red-500 mr-2" />
                      <span className="text-red-800 font-medium">Generation Failed</span>
                    </div>
                  </div>
                  
                  <button
                    onClick={handleRegenerate}
                    className="btn-primary w-full"
                  >
                    Try Again
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Preview Panel */}
        <div className="lg:col-span-2">
          <div className="card">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Preview</h2>
            
            {generationStatus === 'completed' && videoUrl ? (
              <div className="space-y-4">
                <div className="aspect-[9/16] bg-black rounded-lg overflow-hidden">
                  <video
                    src={videoUrl}
                    controls
                    className="w-full h-full object-contain"
                  />
                </div>
                
                <div className="text-center text-sm text-gray-500">
                  Your vertical Shorts video is ready for download
                </div>
              </div>
            ) : generationStatus === 'generating' ? (
              <div className="aspect-[9/16] bg-gray-200 rounded-lg flex items-center justify-center">
                <div className="text-center">
                  <ArrowPathIcon className="w-12 h-12 text-gray-400 animate-spin mx-auto mb-3" />
                  <p className="text-gray-500">Generating your video...</p>
                  <p className="text-sm text-gray-400 mt-1">This may take a few minutes</p>
                </div>
              </div>
            ) : (
              <div className="aspect-[9/16] bg-gray-100 rounded-lg flex items-center justify-center">
                <div className="text-center">
                  <VideoCameraIcon className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                  <p className="text-gray-500">Video preview will appear here</p>
                  <p className="text-sm text-gray-400 mt-1">
                    {steps.length === 0 
                      ? 'Add steps to your guide first' 
                      : 'Click "Generate Shorts" to create your video'}
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Steps Preview */}
          <div className="card mt-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Steps Included</h2>
            
            {steps.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <p>No steps available</p>
                <p className="text-sm mt-1">Add steps in the editor first</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-64 overflow-y-auto">
                {steps.map((step, index) => (
                  <div key={step.id} className="flex items-start space-x-3 p-3 bg-gray-50 rounded-lg">
                    <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-100 text-blue-800 flex items-center justify-center text-sm font-medium">
                      {index + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-900">{step.text}</p>
                      {step.screenshot_url && (
                        <img 
                          src={step.screenshot_url} 
                          alt={`Step ${index + 1}`} 
                          className="mt-2 w-16 h-16 object-cover rounded border"
                        />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default ShortsGenerator