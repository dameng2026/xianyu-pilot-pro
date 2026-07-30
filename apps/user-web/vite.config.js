import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import viteCompression from 'vite-plugin-compression'
import pkg from './package.json'

// Build metadata must be supplied by the release pipeline. Falling back to an
// empty value keeps local/CI artifacts reproducible and the UI truthfully shows
// an unavailable build date instead of inventing the current wall-clock time.
const buildDate = process.env.VITE_BUILD_DATE?.trim() || ''
if (buildDate && Number.isNaN(Date.parse(buildDate))) {
  throw new Error('VITE_BUILD_DATE must be an ISO-8601 timestamp')
}

export default defineConfig({
  plugins: [
    vue(),
    // 构建时预压缩 .gz 文件，配合 nginx `gzip_static on` 实现零 CPU 在线压缩开销
    // 与 admin-web/vite.config.ts 配置保持一致
    viteCompression({
      algorithm: 'gzip',
      ext: '.gz',
      threshold: 10240,
      deleteOriginFile: false,
    }),
  ],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
    __APP_BUILD_DATE__: JSON.stringify(buildDate)
  },
  build: {
    minify: 'oxc',
    sourcemap: false,
    // ES2018 target drops legacy polyfills and shrinks bundle size.
    target: 'es2018',
    // Split CSS per route so opening the products page does not load order CSS.
    cssCodeSplit: true,
    // Inline assets below 8KB as base64 to cut HTTP request count (icons, small SVGs).
    assetsInlineLimit: 8192,
    // Larger warning threshold to avoid noise from echarts vendor chunk.
    chunkSizeWarningLimit: 1200,
    // Keep Vite 8's native Oxc minifier and remove production diagnostics
    // that may otherwise retain account/event objects in the browser bundle.
    rolldownOptions: {
      output: {
        // Split vendor bundles so that app code changes do not invalidate
        // the long-lived cache for stable third-party libraries (echarts/vue).
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('echarts') || id.includes('zrender')) return 'vendor-echarts'
          if (id.includes('vue')) return 'vendor-vue'
          if (id.includes('axios')) return 'vendor-utils'
          return 'vendor'
        },
        minify: {
          compress: {
            // 保留 console.error / console.warn 用于线上排障；仅移除 log/info/debug/trace 等纯诊断输出
            dropDebugger: true,
            pure_funcs: ['console.log', 'console.info', 'console.debug', 'console.trace']
          },
          mangle: true
        }
      }
    }
  },
  server: {
    // Keep the dev server aligned with dev-start.ps1 and the documented local URL.
    // If this drifts, localhost:5174 may point at a stale/Python process and the
    // browser will report the misleading expired-token response.
    port: 5174,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://localhost:18080',
        changeOrigin: true,
      },
      // 私有媒体由 core-api 校验短期 HttpOnly 媒体会话、租户归属与文件完整性。
      // 必须与生产 Nginx 一样代理到 Java，不能绕过鉴权直连 Python 文件目录。
      '/uploads': {
        target: 'http://localhost:18080',
        changeOrigin: true,
      },
    },
  },
})
