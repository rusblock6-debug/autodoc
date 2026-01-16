import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Dashboard from './pages/Dashboard'
import StepEditor from './pages/StepEditor'
import ShortsPreview from './pages/ShortsPreview'
import SessionStatus from './pages/SessionStatus'

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-900 text-white">
        <Navbar />
        <main className="container mx-auto px-4 py-6">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/session/:sessionId" element={<SessionStatus />} />
            <Route path="/sessions/:sessionId" element={<SessionStatus />} />
            <Route path="/guide/:guideId/edit" element={<StepEditor />} />
            <Route path="/guide/:guideId/shorts" element={<ShortsPreview />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App
