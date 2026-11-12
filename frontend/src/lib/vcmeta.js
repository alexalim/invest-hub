import { ref } from 'vue'
import { api } from './api'
const meta = ref(null)
export function useVcMeta(force = false) { if (!meta.value || force) api.get('/vc/meta').then(m => (meta.value = m)).catch(() => {}); return meta }
