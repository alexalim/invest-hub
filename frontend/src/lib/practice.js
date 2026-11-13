// 심법 화면의 기록: 날짜별 횟수 하나만 저장하고 오늘·누적·연속·12주 격자는 모두 여기서 계산한다
import { computed } from 'vue'
import { stored } from './prefs'

export function dayKey(t = new Date()) { return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}` }
function shift(t, n) { const x = new Date(t); x.setDate(x.getDate() + n); return x }

export function usePractice(kind, defGoal) {
  const rec = stored('sb.' + kind, { days: {}, goal: defGoal, favs: [], sound: true })
  const today = computed(() => rec.value.days[dayKey()] || 0)
  const total = computed(() => Object.values(rec.value.days).reduce((a, b) => a + b, 0))
  const stats = computed(() => {
    const d = rec.value.days; const keys = Object.keys(d).filter(k => d[k] > 0).sort()
    let longest = 0; let run = 0; let prev = null
    for (const k of keys) {
      run = prev && dayKey(shift(new Date(prev + 'T00:00:00'), 1)) === k ? run + 1 : 1
      longest = Math.max(longest, run); prev = k
    }
    // 오늘 아직 안 했어도 어제까지 이어졌으면 연속은 유지된 것으로 센다
    let streak = 0; let t = new Date(); if (!d[dayKey(t)]) t = shift(t, -1)
    while (d[dayKey(t)] > 0) { streak++; t = shift(t, -1) }
    return { days: keys.length, longest, streak, best: Math.max(0, ...keys.map(k => d[k])) }
  })
  // 최근 12주: 열 하나가 한 주(일~토), 오른쪽 끝이 이번 주
  const weeks = computed(() => {
    const now = new Date(); const start = shift(now, -now.getDay() - 7 * 11); const g = rec.value.goal || 1
    return Array.from({ length: 12 }, (_, w) => Array.from({ length: 7 }, (_, i) => {
      const t = shift(start, w * 7 + i); const k = dayKey(t); const n = rec.value.days[k] || 0
      return { k, n, future: t > now, today: k === dayKey(now), lv: n === 0 ? 0 : n >= g ? 4 : Math.min(3, 1 + Math.floor((n / g) * 3)) }
    }))
  })
  function hit() { const k = dayKey(); rec.value.days = { ...rec.value.days, [k]: (rec.value.days[k] || 0) + 1 } }
  function reset() { rec.value = { ...rec.value, days: {} } }
  function isFav(t) { return rec.value.favs.includes(t) }
  function toggleFav(t) { rec.value.favs = isFav(t) ? rec.value.favs.filter(x => x !== t) : [...rec.value.favs, t] }
  function summary(name, unit) {
    const s = stats.value
    return `${name} 기록 (${dayKey()})\n누적 ${total.value.toLocaleString('ko-KR')}${unit} · 오늘 ${today.value}${unit} · 연속 ${s.streak}일\n함께한 날 ${s.days}일 · 최장 연속 ${s.longest}일 · 하루 최다 ${s.best}${unit}`
  }
  return { rec, today, total, stats, weeks, hit, reset, isFav, toggleFav, summary }
}

// 날짜마다 같은 구절이 나오게 고른다
export function ofTheDay(list) { const t = new Date(); const n = Math.floor((t - new Date(t.getFullYear(), 0, 0)) / 86400000) + t.getFullYear() * 7; return list[n % list.length] }
