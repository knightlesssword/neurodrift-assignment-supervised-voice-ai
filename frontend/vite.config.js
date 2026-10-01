import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Dev-only: proxy API to the FastAPI backend so the browser app stays
// same-origin (the backend has no CORS middleware, which we must not add).
// Run: npm run dev  ->  http://localhost:5173  (API at /api/* -> :8000).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
})
