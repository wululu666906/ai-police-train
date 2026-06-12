import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5555,
    strictPort: true,
    host: true,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/auth': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/training': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/cases': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/student': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/speech': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/knowledge': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/dashboard': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
