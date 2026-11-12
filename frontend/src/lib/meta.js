// 발굴분석 메타(지표 목록·필드·프리셋·전략)를 한 번만 받아 공유한다.
import { ref } from 'vue'
import { api } from './api'
const meta = ref(null)
let p = null
export function useMeta() {
  if (!p) p = api.get('/discover/meta').then(m => (meta.value = m)).catch(() => { p = null })
  return meta
}
