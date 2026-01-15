import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { guidesApi } from '../services/api'
import { 
  DocumentTextIcon, 
  ClockIcon, 
  PlayIcon, 
  PencilIcon, 
  TrashIcon,
  PlusIcon 
} from '@heroicons/react/24/outline'

function GuidesList() {
  const [guides, setGuides] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')

  useEffect(() => {
    fetchGuides()
  }, [])

  const fetchGuides = async () => {
    try {
      setLoading(true)
      const response = await guidesApi.getAll()
      setGuides(response.items || [])
    } catch (error) {
      console.error('Failed to fetch guides:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (guideId) => {
    if (window.confirm('Are you sure you want to delete this guide?')) {
      try {
        await guidesApi.delete(guideId)
        fetchGuides()
      } catch (error) {
        console.error('Failed to delete guide:', error)
      }
    }
  }

  const filteredGuides = guides.filter(guide =>
    guide.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (guide.description && guide.description.toLowerCase().includes(searchTerm.toLowerCase()))
  )

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">My Guides</h1>
          <p className="mt-2 text-gray-600">
            Manage your auto-generated step-by-step guides
          </p>
        </div>
        <Link
          to="/guides/create"
          className="btn-primary flex items-center space-x-2"
        >
          <PlusIcon className="w-5 h-5" />
          <span>Create New Guide</span>
        </Link>
      </div>

      {/* Search */}
      <div className="relative">
        <input
          type="text"
          placeholder="Search guides..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="input-field pl-10"
        />
        <svg
          className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
      </div>

      {/* Guides Grid */}
      {filteredGuides.length === 0 ? (
        <div className="text-center py-12">
          <DocumentTextIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No guides found</h3>
          <p className="mt-1 text-sm text-gray-500">
            {searchTerm ? 'Try adjusting your search terms' : 'Get started by creating a new guide'}
          </p>
          {!searchTerm && (
            <div className="mt-6">
              <Link
                to="/guides/create"
                className="btn-primary inline-flex items-center"
              >
                <PlusIcon className="w-5 h-5 mr-2" />
                Create your first guide
              </Link>
            </div>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredGuides.map((guide) => (
            <div key={guide.id} className="step-card overflow-hidden">
              <div className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-gray-900 truncate">
                      {guide.title}
                    </h3>
                    {guide.description && (
                      <p className="mt-1 text-sm text-gray-500 line-clamp-2">
                        {guide.description}
                      </p>
                    )}
                  </div>
                  <div className="ml-4 flex-shrink-0">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      guide.status === 'completed' 
                        ? 'bg-green-100 text-green-800'
                        : guide.status === 'processing' 
                        ? 'bg-yellow-100 text-yellow-800'
                        : 'bg-gray-100 text-gray-800'
                    }`}>
                      {guide.status}
                    </span>
                  </div>
                </div>

                <div className="mt-4 flex items-center text-sm text-gray-500">
                  <ClockIcon className="w-4 h-4 mr-1" />
                  <span>{new Date(guide.created_at).toLocaleDateString()}</span>
                  
                  {guide.step_count > 0 && (
                    <>
                      <span className="mx-2">•</span>
                      <span>{guide.step_count} steps</span>
                    </>
                  )}
                </div>

                <div className="mt-6 flex space-x-3">
                  <Link
                    to={`/guides/${guide.id}/edit`}
                    className="flex-1 btn-primary flex items-center justify-center space-x-1"
                  >
                    <PencilIcon className="w-4 h-4" />
                    <span>Edit</span>
                  </Link>
                  
                  <Link
                    to={`/guides/${guide.id}/export`}
                    className="flex-1 btn-secondary flex items-center justify-center space-x-1"
                  >
                    <PlayIcon className="w-4 h-4" />
                    <span>Export</span>
                  </Link>
                  
                  <button
                    onClick={() => handleDelete(guide.id)}
                    className="p-2 text-gray-400 hover:text-red-500 transition-colors"
                    title="Delete guide"
                  >
                    <TrashIcon className="w-5 h-5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default GuidesList