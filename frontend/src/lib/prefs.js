// 이 브라우저에만 기억해 두는 화면 선택값 (시장 선택, 접어 둔 메뉴, 자주 여는 화면)
import { ref, watch } from 'vue'

export function stored(key, def) {
  let v = def
  try { const s = localStorage.getItem(key); if (s !== null) v = JSON.parse(s) } catch { /* 저장소 사용 불가 */ }
  const r = ref(v)
  watch(r, x => { try { localStorage.setItem(key, JSON.stringify(x)) } catch { /* 무시 */ } }, { deep: true })
  return r
}

// 코스피/코스닥 선택은 수급 화면들이 함께 쓴다
export const krMarket = stored('pref.krMarket', 'KOSPI')
export const KR_MARKETS = [['KOSPI', '코스피'], ['KOSDAQ', '코스닥']]
