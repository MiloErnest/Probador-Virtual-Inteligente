import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // Permite importar como "@/services/apiClient" en lugar de "../../services/apiClient".
      // Se usa import.meta.url y no __dirname porque package.json declara
      // "type": "module": en un módulo ESM __dirname no existe.
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
  },
})
