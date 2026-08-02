import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  optimizeDeps: {
    include: ['@mediapipe/tasks-vision'],
  },
  build: {
    rollupOptions: {
      output: {
        // Production assets are cached by the reverse proxy. Content hashes
        // keep a fresh entry page from mixing with stale lazy chunks or CSS.
        entryFileNames: 'assets/[name]-[hash].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('@mediapipe/tasks-vision')) return 'vendor-mediapipe'
          if (id.includes('element-plus') || id.includes('@element-plus')) return 'vendor-element'
          if (id.includes('vant')) return 'vendor-vant'
          if (id.includes('echarts')) return 'vendor-echarts'
          if (id.includes('xlsx')) return 'vendor-xlsx'
          return 'vendor-core'
        },
      },
    },
  },
  server: {
    port: 5556,
    strictPort: true,
    host: true,
    headers: {
      'Cache-Control': 'no-store',
    },
    proxy: {
      '/api':       { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/auth':      { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/training':  { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/cases':     { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/knowledge': { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/dashboard': { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/videos':    { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/video-training': { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/face':        { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/classes':   { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/avatars':   { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      // 静态文件（视频、封面图等）
      '/static':    { target: process.env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
