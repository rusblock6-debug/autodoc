import React from 'react'
import { Link, useLocation } from 'react-router-dom'

function Navbar() {
  const location = useLocation()
  
  const isActive = (path) => location.pathname === path

  return (
    <nav className="bg-gray-800 border-b border-gray-700">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-14">
          <Link to="/" className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-gradient-to-br from-yellow-400 to-orange-500 rounded-lg flex items-center justify-center">
              <span className="text-black font-bold text-sm">НД</span>
            </div>
            <span className="text-lg font-semibold text-white">НИР-Документ</span>
          </Link>

          <div className="flex items-center space-x-4">
            <Link
              to="/"
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                isActive('/') 
                  ? 'bg-gray-700 text-white' 
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Мои гайды
            </Link>
          </div>
        </div>
      </div>
    </nav>
  )
}

export default Navbar
