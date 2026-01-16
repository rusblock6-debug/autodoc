import React from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import StepEditor from './pages/StepEditor'
import SessionStatus from './pages/SessionStatus'
import ShortsPreview from './pages/ShortsPreview'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="guide/:guideId/edit" element={<StepEditor />} />
          <Route path="guide/:guideId/shorts" element={<ShortsPreview />} />
          <Route path="session/:sessionId" element={<SessionStatus />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
