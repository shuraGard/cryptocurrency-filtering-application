import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In development, /api/* is proxied to the FastAPI backend so the browser only
// ever talks to this origin (no CORS, no hard-coded backend URL in the app).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
