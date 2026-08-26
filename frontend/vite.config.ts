/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  test: {
    include: ['src/**/*.test.ts'],
    // Huso al oeste de UTC: es donde se rompen las fechas de calendario si se
    // parsean como instantes. Fijarlo hace el test determinista en CI.
    env: { TZ: 'America/Santo_Domingo' },
  },
})
