import { createApp } from 'vue'
import App from './App.vue'
// 仅保留首屏必需样式；auth-pages.css 由登录/注册页懒加载，mobile-responsive.css 由移动端组件按需引入
import './styles.css'

// build marker: 2026-07-20 force chunk hash rotation to invalidate stale browser 404 cache
createApp(App).mount('#app')
