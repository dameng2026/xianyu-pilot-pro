import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import pkg from './package.json'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import ElementPlus from 'unplugin-element-plus/vite'
import tailwindcss from '@tailwindcss/vite'
import viteCompression from 'vite-plugin-compression'
// Bundle 分析工具：通过 --mode analyze 启用，生成 stats.html 用于分析产物体积分布
import { visualizer } from 'rollup-plugin-visualizer'

export default defineConfig(({ mode }) => ({
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  plugins: [
    vue(),
    tailwindcss(),
    AutoImport({
      imports: [
        'vue',
        'pinia',
        'vue-router',
        {
          '@vueuse/core': [
            'useDark',
            'useToggle',
            'useStorage',
            'useLocalStorage',
            'useSessionStorage',
            'useMediaQuery',
            'useMagicKeys',
            'useBreakpoints',
            'useDebounceFn',
            'useThrottleFn',
            'useEventListener',
            'useIntervalFn',
            'useTimeoutFn',
            'useClipboard',
            'useFullscreen',
            'useResizeObserver',
            'useMutationObserver',
            'useIntersectionObserver',
            'useElementSize',
            'useElementBounding',
            'useWindowSize',
            'useScroll',
            'useDraggable',
            'useSortable',
            'useCssVar',
            'useFavicon',
            'useTitle',
            'useDateFormat',
            'useNow',
            'useTimestamp',
            'useInterval',
            'useTimeout',
            'useTransition',
            'useVModel',
            'useVModels',
            'useAsyncState',
            'useFetch',
            'useWebSocket',
            'useEventBus',
            'useMounted',
            'useSupported',
            'useFocus',
            'useFocusWithin',
            'useActiveElement',
            'useIdle',
            'useOnline',
            'useDocumentVisibility',
            'usePreferredDark',
            'usePreferredColorScheme',
            'useColorMode',
            'useMemory',
            'useCloned',
            'useTemplateRefsList',
            'toReactive',
            'reactify',
            'syncRef',
            'syncRefs',
            'refAutoReset',
            'refDebounced',
            'refThrottled',
            'refWithControl',
            'controlledRef',
            'computedAsync',
            'computedWithControl',
            'whenever',
            'until',
          ],
        },
      ],
      resolvers: [ElementPlusResolver()],
      dts: resolve(__dirname, 'src/types/import/auto-imports.d.ts'),
    }),
    Components({
      resolvers: [
        ElementPlusResolver({
          importStyle: 'sass',
        }),
      ],
      dts: resolve(__dirname, 'src/types/import/components.d.ts'),
      dirs: [
        resolve(__dirname, 'src/components'),
      ],
      include: [/\.vue$/, /\.vue\?vue/, /\.tsx$/],
    }),
    ElementPlus({
      useSource: true,
    }),
    // Pre-compress assets to .gz at build time so nginx can serve them with
    // `gzip_static on` and skip on-the-fly compression CPU cost.
    viteCompression({
      algorithm: 'gzip',
      ext: '.gz',
      threshold: 10240,
      deleteOriginFile: false,
    }),
    // Pre-compress assets to .br at build time for nginx `brotli_static on`.
    // Brotli yields 10-20% smaller payloads than gzip; modern browsers support it.
    // Server Nginx must be compiled with ngx_brotli (see deploy/nginx/brotli.conf).
    viteCompression({
      algorithm: 'brotliCompress',
      ext: '.br',
      threshold: 10240,
      deleteOriginFile: false,
    }),
    // Bundle 分析：仅在 --mode analyze 时启用，生成 stats.html 在 dist/ 下。
    // 用法：npm run analyze
    // 产物：dist/stats.html（用浏览器打开查看各 chunk 体积分布，定位可拆分的大依赖）
    mode === 'analyze' && visualizer({
      filename: 'dist/stats.html',
      open: false,
      gzipSize: true,
      brotliSize: true,
      template: 'treemap',
    }),
  ].filter(Boolean),
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      '@views': resolve(__dirname, 'src/views'),
      '@imgs': resolve(__dirname, 'src/assets/images'),
      '@styles': resolve(__dirname, 'src/assets/styles'),
      '@utils': resolve(__dirname, 'src/utils'),
    },
  },
  css: {
    preprocessorOptions: {
      scss: {},
    },
  },
  build: {
    minify: 'terser',
    sourcemap: false,
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
      },
    },
    // 当前管理后台页面和第三方库较多，关闭压缩体积统计可避免受限 CI/容器在 gzip 统计阶段长时间挂起。
    reportCompressedSize: false,
    chunkSizeWarningLimit: 1200,
    // 构建目标设为 es2018，移除过旧浏览器的兼容代码以减小产物体积
    target: 'es2018',
    // CSS 代码分割，按路由懒加载样式
    cssCodeSplit: true,
    // 小于 8KB 的资源内联为 base64，减少 HTTP 请求
    assetsInlineLimit: 8192,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('element-plus') || id.includes('@element-plus')) return 'vendor-element-plus'
          if (id.includes('echarts')) return 'vendor-echarts'
          if (id.includes('@wangeditor')) return 'vendor-editor'
          if (id.includes('xlsx')) return 'vendor-xlsx'
          if (id.includes('xgplayer')) return 'vendor-player'
          if (id.includes('@iconify')) return 'vendor-iconify'
          if (id.includes('@vueuse')) return 'vendor-vueuse'
          if (id.includes('vue') || id.includes('pinia') || id.includes('vue-router')) return 'vendor-vue'
          if (id.includes('axios') || id.includes('crypto-js') || id.includes('qrcode') || id.includes('file-saver')) return 'vendor-utils'
          return 'vendor'
        }
      }
    }
  },
  server: {
    port: 3006,
    proxy: {
      '/admin-api': {
        target: 'http://127.0.0.1:18080',
        changeOrigin: true,
      },
      '/uploads': {
        // Keep local media reads on the same authorization boundary as
        // production; core-api validates the path-scoped media cookie.
        target: 'http://127.0.0.1:18080',
        changeOrigin: true,
      },
    },
  },
}))
