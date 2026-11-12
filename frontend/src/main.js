import { createApp } from 'vue'
import App from './App.vue'
import Loading from './components/Loading.vue'
import { router } from './router'
import './style.css'

try { const t = localStorage.getItem('theme'); if (t) document.documentElement.dataset.theme = t } catch { /* 저장소 사용 불가 */ }
createApp(App).component('Loading', Loading).use(router).mount('#app')
