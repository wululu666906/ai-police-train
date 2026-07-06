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
      '/api':       { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/auth':      { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/training':  { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/cases':     { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/knowledge': { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/dashboard': { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/videos':    { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/video-training': { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/classes':   { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/avatars':   { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      // 静态文件（视频、封面图等）
      '/static':    { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
