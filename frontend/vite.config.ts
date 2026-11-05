import path from 'node:path'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(import.meta.dirname, './src') } },
  server: {
    host: '127.0.0.1',
    proxy: {
      '/api': { target: 'http://127.0.0.1:8080', ws: true },
      '/voice-capture.js': 'http://127.0.0.1:8080',
    },
  },
  build: { outDir: '../trendcoffee/static', emptyOutDir: false, assetsDir: 'kiosk-assets' },
})
