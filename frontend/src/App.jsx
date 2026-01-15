import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import CreateGuide from './pages/CreateGuide';
import GuideEditor from './pages/GuideEditor';
import ExportGuide from './pages/ExportGuide';
import ShortsGenerator from './pages/ShortsGenerator';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/create" element={<CreateGuide />} />
        <Route path="/editor/:id" element={<GuideEditor />} />
        <Route path="/export/:id" element={<ExportGuide />} />
        <Route path="/shorts/:id" element={<ShortsGenerator />} />
      </Routes>
    </Router>
  );
}

export default App;
