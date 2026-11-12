import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import './style.css'

try { const t = localStorage.getItem('theme'); if (t) document.documentElement.dataset.theme = t } catch { /* 저장소 사용 불가 */ }
createApp(App).use(router).mount('#app')
