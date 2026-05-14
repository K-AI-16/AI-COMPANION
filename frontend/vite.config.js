import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    allowedHosts: 'all',
    proxy: {
      '/v1': 'http://127.0.0.1:8000',
      '/debug': 'http://127.0.0.1:8000',
    },
  },
})
