import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      output: {
        entryFileNames: 'assets/[name].js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name][extname]',
        manualChunks(id) {
          if (!id.includes('node_modules')) return
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
