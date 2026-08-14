import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { createReadStream, existsSync, statSync } from 'node:fs'
import * as path from 'node:path'

function serveDistAssetsFallback() {
  return {
    name: 'serve-dist-assets-fallback',
    configureServer(server: any) {
      const distAssetsDir = path.resolve(process.cwd(), 'dist', 'assets')
      const contentTypes: Record<string, string> = {
        '.css': 'text/css; charset=utf-8',
        '.js': 'text/javascript; charset=utf-8',
        '.json': 'application/json; charset=utf-8',
        '.svg': 'image/svg+xml',
        '.wasm': 'application/wasm',
      }

      server.middlewares.use('/assets', (req: any, res: any, next: () => void) => {
        const assetName = decodeURIComponent(String(req.url || '').split('?')[0]).replace(/^\/+/, '')
        if (!assetName) {
          next()
          return
        }

        const filePath = path.resolve(distAssetsDir, assetName)
        if (!filePath.startsWith(`${distAssetsDir}${path.sep}`) || !existsSync(filePath) || !statSync(filePath).isFile()) {
          next()
          return
        }

        res.setHeader('Content-Type', contentTypes[path.extname(filePath).toLowerCase()] || 'application/octet-stream')
        res.setHeader('Cache-Control', 'no-store')
        createReadStream(filePath).pipe(res)
      })
    },
  }
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000'
  // Browser navigations send Accept: text/html; XHR/fetch API calls do not.
  // Without this, SPA paths under /student (e.g. /student/hall) are proxied to
  // FastAPI and return {"detail":"Not Found"} / 401 instead of index.html.
  const bypassSpaDocument = (req: { headers?: Record<string, unknown>; url?: string }) => {
    const accept = String(req.headers?.accept || '')
    if (accept.includes('text/html')) {
      return '/index.html'
    }
    return undefined
  }
  const apiProxy = {
    target: apiTarget,
    changeOrigin: true,
    ws: true,
    bypass: bypassSpaDocument,
  }

  return {
    plugins: [vue(), serveDistAssetsFallback()],
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
        '/api': apiProxy,
        '/auth': apiProxy,
        '/training': apiProxy,
        '/student': apiProxy,
        '/speech': apiProxy,
        '/cases': apiProxy,
        '/knowledge': apiProxy,
        '/dashboard': apiProxy,
        '/videos': apiProxy,
        '/video-training': apiProxy,
        '/face': apiProxy,
        '/classes': apiProxy,
        '/avatars': apiProxy,
        '/object-storage': apiProxy,
        // 静态文件（视频、封面图等）
        '/static': apiProxy,
      },
    },
  }
})
