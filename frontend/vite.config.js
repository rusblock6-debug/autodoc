import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  root: '.',
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://autodoc-ai:8000',
        changeOrigin: true,
        rewrite: (path) => path, // Don't rewrite path, keep /api/v1/...
      }
    }
  },
  publicDir: 'public',
  build: {
    outDir: 'dist',
    emptyOutDir: true
  }
})