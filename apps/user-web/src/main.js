import { createApp } from 'vue'
import App from './App.vue'
import './styles.css'
import './auth-pages.css'
import './mobile-responsive.css'

// build marker: 2026-07-20 force chunk hash rotation to invalidate stale browser 404 cache
createApp(App).mount('#app')
