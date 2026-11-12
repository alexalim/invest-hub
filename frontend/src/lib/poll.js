// 화면에 보이는 종목만 몇 초마다 시세를 다시 받는다.
import { onBeforeUnmount, reactive, watch } from 'vue'
import { api } from './api'

export function useQuotes(symbolsRef, interval = 4000) {
  const quotes = reactive({})
  let timer = null
  let stopped = false
  async function tick() {
    const syms = (symbolsRef.value || []).filter(Boolean)
    if (syms.length && !document.hidden) {
      try {
        const res = await api.get('/quotes', { symbols: syms.slice(0, 120).join(',') }, { quiet: true })
        Object.assign(quotes, res)
      } catch { /* 다음 주기에 다시 시도 */ }
    }
    if (!stopped) timer = setTimeout(tick, interval)
  }
  watch(symbolsRef, () => { clearTimeout(timer); tick() }, { immediate: true, deep: true })
  onBeforeUnmount(() => { stopped = true; clearTimeout(timer) })
  return quotes
}

export function useInterval(fn, ms) {
  let t = setInterval(() => { if (!document.hidden) fn() }, ms)
  onBeforeUnmount(() => clearInterval(t))
}
