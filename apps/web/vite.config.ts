import { defineConfig } from 'vite'

// Dev server: localhost only, /api proxied to regteia-server (uv run regteia-server, or the compose `server`).
export default defineConfig({
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8080' },
  },
  preview: { host: '127.0.0.1' },
  build: { outDir: 'dist', chunkSizeWarningLimit: 2000 },
})
