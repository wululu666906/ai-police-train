import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5556,
    strictPort: true,
    host: true,
    proxy: {
      '/api':       { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/auth':      { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/training':  { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/cases':     { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/speech':    { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/knowledge': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/dashboard': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/student':   { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/videos':    { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/video-training': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/classes':   { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/avatars':   { target: 'http://127.0.0.1:8000', changeOrigin: true },
      // 静态文件（视频、封面图等）
      '/static':    { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
