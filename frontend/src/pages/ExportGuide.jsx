import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { guidesApi, exportApi } from '../services/api'
import { ArrowLeftIcon, DocumentTextIcon, CodeBracketIcon, ArrowDownTrayIcon } from '@heroicons/react/24/outline'

function ExportGuide() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [guide, setGuide] = useState(null)
  const [steps, setSteps] = useState([])
  const [loading, setLoading] = useState(true)
  const [exportFormat, setExportFormat] = useState('markdown')
  const [preview, setPreview] = useState('')

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
      generatePreview('markdown', stepsData.items || [])
    } catch (error) {
      console.error('Failed to fetch guide:', error)
    } finally {
      setLoading(false)
    }
  }

  const generatePreview = (format, stepsData) => {
    if (format === 'markdown') {
      const markdown = generateMarkdown(stepsData)
      setPreview(markdown)
    } else {
      const html = generateHTML(stepsData)
      setPreview(html)
    }
  }

  const generateMarkdown = (stepsData) => {
    let content = `# ${guide?.title}\n\n`
    
    if (guide?.description) {
      content += `${guide.description}\n\n`
    }
    
    stepsData.forEach((step, index) => {
      content += `## Step ${index + 1}\n\n`
      content += `${step.text}\n\n`
      
      if (step.screenshot_url) {
        content += `![Step ${index + 1} screenshot](${step.screenshot_url})\n\n`
      }
    })
    
    return content
  }

  const generateHTML = (stepsData) => {
    let content = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>${guide?.title}</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        h1 { color: #333; border-bottom: 2px solid #3b82f6; padding-bottom: 10px; }
        h2 { color: #3b82f6; margin-top: 30px; }
        .step { margin-bottom: 30px; }
        .step-image { max-width: 100%; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .step-number { 
            display: inline-block; 
            background: #3b82f6; 
            color: white; 
            width: 30px; 
            height: 30px; 
            border-radius: 50%; 
            text-align: center; 
            line-height: 30px; 
            margin-right: 10px; 
        }
    </style>
</head>
<body>
    <h1>${guide?.title}</h1>
    ${guide?.description ? `<p>${guide.description}</p>` : ''}
`

    stepsData.forEach((step, index) => {
      content += `
    <div class="step">
        <h2><span class="step-number">${index + 1}</span>${step.text}</h2>
        ${step.screenshot_url ? `<img src="${step.screenshot_url}" alt="Step ${index + 1}" class="step-image">` : ''}
    </div>`
    })

    content += `
</body>
</html>`
    
    return content
  }

  const handleExport = async () => {
    try {
      let blob
      if (exportFormat === 'markdown') {
        blob = await exportApi.markdown(id)
      } else {
        blob = await exportApi.html(id)
      }
      
      // Create download link
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${guide.title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.${exportFormat === 'markdown' ? 'md' : 'html'}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
      
    } catch (error) {
      console.error('Export failed:', error)
    }
  }

  const handleFormatChange = (format) => {
    setExportFormat(format)
    generatePreview(format, steps)
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
        
        <h1 className="text-3xl font-bold text-gray-900">Export Guide</h1>
        <p className="mt-2 text-gray-600">
          Export your guide in various formats for sharing or documentation
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Export Options */}
        <div className="card">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Export Settings</h2>
          
          <div className="space-y-6">
            {/* Format Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">
                Export Format
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => handleFormatChange('markdown')}
                  className={`p-4 rounded-lg border-2 transition-colors ${
                    exportFormat === 'markdown'
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <DocumentTextIcon className="w-8 h-8 mx-auto text-gray-600 mb-2" />
                  <div className="text-center">
                    <div className="font-medium text-gray-900">Markdown</div>
                    <div className="text-xs text-gray-500 mt-1">.md file</div>
                  </div>
                </button>
                
                <button
                  onClick={() => handleFormatChange('html')}
                  className={`p-4 rounded-lg border-2 transition-colors ${
                    exportFormat === 'html'
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <CodeBracketIcon className="w-8 h-8 mx-auto text-gray-600 mb-2" />
                  <div className="text-center">
                    <div className="font-medium text-gray-900">HTML</div>
                    <div className="text-xs text-gray-500 mt-1">.html file</div>
                  </div>
                </button>
              </div>
            </div>

            {/* Guide Info */}
            <div className="bg-gray-50 rounded-lg p-4">
              <h3 className="font-medium text-gray-900 mb-2">Guide Details</h3>
              <div className="space-y-2 text-sm text-gray-600">
                <div><span className="font-medium">Title:</span> {guide?.title}</div>
                <div><span className="font-medium">Steps:</span> {steps.length}</div>
                <div><span className="font-medium">Status:</span> {guide?.status}</div>
              </div>
            </div>

            {/* Export Button */}
            <button
              onClick={handleExport}
              className="btn-primary w-full flex items-center justify-center space-x-2"
            >
              <ArrowDownTrayIcon className="w-5 h-5" />
              <span>Download {exportFormat.toUpperCase()}</span>
            </button>
          </div>
        </div>

        {/* Preview */}
        <div className="card">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Preview</h2>
          
          <div className="bg-gray-50 rounded-lg p-4 h-96 overflow-auto">
            {exportFormat === 'markdown' ? (
              <pre className="text-sm text-gray-700 whitespace-pre-wrap font-mono">
                {preview}
              </pre>
            ) : (
              <div 
                className="text-sm text-gray-700"
                dangerouslySetInnerHTML={{ __html: preview }}
              />
            )}
          </div>
          
          <div className="mt-4 text-sm text-gray-500">
            This is a preview of how your exported guide will look
          </div>
        </div>
      </div>
    </div>
  )
}

export default ExportGuide