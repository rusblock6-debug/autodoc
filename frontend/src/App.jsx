import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import GuidesList from './pages/GuidesList'
import GuideEditor from './pages/GuideEditor'
import CreateGuide from './pages/CreateGuide'
import ExportGuide from './pages/ExportGuide'
import ShortsGenerator from './pages/ShortsGenerator'

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <main className="container mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<GuidesList />} />
            <Route path="/guides" element={<GuidesList />} />
            <Route path="/guides/create" element={<CreateGuide />} />
            <Route path="/guides/:id/edit" element={<GuideEditor />} />
            <Route path="/guides/:id/export" element={<ExportGuide />} />
            <Route path="/guides/:id/shorts" element={<ShortsGenerator />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App