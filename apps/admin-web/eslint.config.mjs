// 从 URL 和路径模块中导入必要的功能
import fs from 'fs'
import path, { dirname } from 'path'
import { fileURLToPath } from 'url'

// 从 ESLint 插件中导入推荐配置
import pluginJs from '@eslint/js'
import eslintPluginPrettierRecommended from 'eslint-plugin-prettier/recommended'
import pluginVue from 'eslint-plugin-vue'
import globals from 'globals'
import tseslint from 'typescript-eslint'

// 使用 import.meta.url 获取当前模块的路径
const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

// 读取 .auto-import.json 文件的内容，并将其解析为 JSON 对象。
// 该文件由 unplugin-auto-import 在开发/构建阶段生成；干净环境首次执行 lint 时
// 可能尚不存在，因此这里提供安全兜底，避免质量门禁被生成物缺失阻断。
const autoImportPath = path.resolve(__dirname, '.auto-import.json')
const autoImportConfig = fs.existsSync(autoImportPath)
  ? JSON.parse(fs.readFileSync(autoImportPath, 'utf-8'))
  : { globals: {} }

// 与 Vite 的 unplugin-auto-import 保持一致：在首次构建前 .auto-import.json
// 可能不存在，但项目中已经大量使用 Vue/Pinia/Vue Router 自动导入。
// 这里显式兜底声明常用全局符号，避免 lint 在干净 CI 环境误报 no-undef。
const autoImportFallbackGlobals = Object.fromEntries(
  [
    'ref', 'reactive', 'readonly', 'computed', 'watch', 'watchEffect', 'h',
    'onMounted', 'onUnmounted', 'onBeforeMount', 'onBeforeUnmount', 'nextTick',
    'defineProps', 'defineEmits', 'defineExpose', 'withDefaults', 'toRefs', 'toRef',
    'shallowRef', 'customRef', 'markRaw', 'provide', 'inject', 'useAttrs',
    'defineAsyncComponent', 'storeToRefs', 'defineStore', 'useRouter', 'useRoute',
    'useDark', 'useToggle', 'useStorage', 'useLocalStorage', 'useSessionStorage',
    'useMediaQuery', 'useMagicKeys', 'useBreakpoints', 'useDebounceFn', 'useThrottleFn',
    'useEventListener', 'useIntervalFn', 'useTimeoutFn', 'useClipboard', 'useFullscreen',
    'useResizeObserver', 'useMutationObserver', 'useIntersectionObserver', 'useElementSize',
    'useElementBounding', 'useWindowSize', 'useScroll', 'useDraggable', 'useSortable',
    'useCssVar', 'useFavicon', 'useTitle', 'useDateFormat', 'useNow', 'useTimestamp',
    'useInterval', 'useTimeout', 'useTransition', 'useVModel', 'useVModels', 'useAsyncState',
    'useFetch', 'useWebSocket', 'useEventBus', 'useMounted', 'useSupported', 'useFocus',
    'useFocusWithin', 'useActiveElement', 'useIdle', 'useOnline', 'useDocumentVisibility',
    'usePreferredDark', 'usePreferredColorScheme', 'useColorMode', 'useMemory', 'useCloned',
    'useTemplateRef', 'useTemplateRefsList', 'toReactive', 'reactify', 'syncRef', 'syncRefs',
    'refAutoReset', 'refDebounced', 'refThrottled', 'refWithControl', 'controlledRef',
    'computedAsync', 'computedWithControl', 'whenever', 'until', 'ElMessage', 'ElMessageBox',
    'ElNotification', 'ElLoading', 'VNode', 'Ref'
  ].map(name => [name, 'readonly'])
)

export default [
  // 指定文件匹配规则
  {
    files: ['**/*.{js,mjs,cjs,ts,tsx,vue}']
  },
  // 指定全局变量和环境
  {
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node
      }
    }
  },
  // 扩展配置
  pluginJs.configs.recommended,
  ...tseslint.configs.recommended,
  ...pluginVue.configs['flat/essential'],
  // 自定义规则
  {
    // 针对所有 JavaScript、TypeScript 和 Vue 文件应用以下配置
    files: ['**/*.{js,mjs,cjs,ts,tsx,vue}'],

    languageOptions: {
      globals: {
        // 合并从 autoImportConfig 中读取的全局变量配置
        ...autoImportFallbackGlobals,
        ...autoImportConfig.globals,
        // TypeScript 全局命名空间
        Api: 'readonly'
      }
    },
    rules: {
      quotes: ['error', 'single'], // 使用单引号
      semi: ['error', 'never'], // 语句末尾不加分号
      'no-var': 'error', // 要求使用 let 或 const 而不是 var
      '@typescript-eslint/no-explicit-any': 'off', // 禁用 any 检查
      'vue/multi-word-component-names': 'off', // 禁用对 Vue 组件名称的多词要求检查
      'no-multiple-empty-lines': ['warn', { max: 1 }], // 不允许多个空行
      'no-unexpected-multiline': 'error', // 禁止空余的多行
      // 当前项目历史代码采用单引号、无分号风格，Prettier 默认规则与既有 ESLint 规则冲突。
      // 将格式化交给独立的 lint:prettier 脚本，避免 lint 质量门禁被纯格式问题淹没。
      'prettier/prettier': 'off'
    }
  },
  // vue 规则
  {
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: { parser: tseslint.parser }
    }
  },
  // 忽略文件
  {
    ignores: [
      'node_modules',
      'dist',
      'public',
      '.vscode/**',
      'src/assets/**',
      'src/utils/console.ts'
    ]
  },
  // prettier 配置
  eslintPluginPrettierRecommended,
  {
    rules: {
      'prettier/prettier': 'off'
    }
  }
]
