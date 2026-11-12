// 숫자·금액·날짜 표시
export function num(v, d = 0) {
  if (v === null || v === undefined || Number.isNaN(+v)) return '-'
  return (+v).toLocaleString('ko-KR', { minimumFractionDigits: d, maximumFractionDigits: d })
}
export function price(v, currency = 'KRW') {
  if (v === null || v === undefined) return '-'
  const a = Math.abs(+v)
  if (currency === 'USD') return num(v, 2)
  if (a > 0 && a < 1) return num(v, 4)
  if (a < 100 && a % 1 !== 0) return num(v, 2)
  return num(v, 0)
}
// 지수·환율·원자재·금리: 항상 소수 둘째 자리 (금리는 셋째 자리)
export function macro(v, symbol = '') {
  if (v === null || v === undefined) return '-'
  return num(v, symbol.startsWith('RT:') ? 3 : 2)
}
export function isMacro(symbol) { return /^(IX|FX|CM|RT):/.test(symbol || '') }
export function pct(v, d = 2, sign = true) {
  if (v === null || v === undefined || Number.isNaN(+v)) return '-'
  return (sign && +v > 0 ? '+' : '') + (+v).toFixed(d) + '%'
}
export function signed(v, d = 0) {
  if (v === null || v === undefined) return '-'
  return (+v > 0 ? '+' : '') + num(v, d)
}
// 원 단위 큰 금액 → '1조 2,345억'
export function won(v, digits = null) {
  if (v === null || v === undefined || Number.isNaN(+v)) return '-'
  const s = +v < 0 ? '-' : ''
  let a = Math.abs(+v)
  if (a >= 1e12) { const jo = Math.floor(a / 1e12); const eok = Math.round((a % 1e12) / 1e8); return `${s}${num(jo)}조${eok ? ' ' + num(eok) + '억' : ''}` }
  if (a >= 1e8) { const dg = digits ?? (a < 1e9 ? 1 : 0); return `${s}${(+(a / 1e8).toFixed(dg)).toLocaleString('ko-KR')}억` }
  if (a >= 9999.5e4) return `${s}${(+(a / 1e8).toFixed(2)).toLocaleString('ko-KR')}억`   // 9,999.5만 이상은 '1억'으로
  if (a >= 1e4) return `${s}${num(a / 1e4)}만`
  return s + num(a)
}
export function usd(v) {
  if (v === null || v === undefined) return '-'
  const a = Math.abs(+v)
  if (a >= 1e12) return '$' + (v / 1e12).toFixed(2) + 'T'
  if (a >= 1e9) return '$' + (v / 1e9).toFixed(2) + 'B'
  if (a >= 1e6) return '$' + (v / 1e6).toFixed(1) + 'M'
  return '$' + num(v)
}
export function mcap(v, currency) { return currency === 'USD' ? usd(v) : won(v) }
export function vol(v) {
  if (v === null || v === undefined) return '-'
  const a = Math.abs(+v)
  if (a >= 1e8) return num(v / 1e8, 1) + '억'
  if (a >= 1e4) return num(v / 1e4, 0) + '만'
  return num(v, a < 10 ? 4 : 0)
}
export function cls(v) { return v > 0 ? 'up' : v < 0 ? 'down' : '' }
export function date(ts) {
  if (!ts) return '-'
  const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts)
  return d.toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/\.\s?/g, '-').replace(/-$/, '')
}
export function datetime(ts) {
  if (!ts) return '-'
  const d = new Date(ts * 1000)
  return `${date(ts)} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
// 일봉 차트 시각(UTC 자정 기준)을 날짜 문자열로
export function barDate(ts) { const d = new Date(ts * 1000); return d.toISOString().slice(0, 10) }
export function ago(ts) {
  if (!ts) return ''
  const s = Date.now() / 1000 - ts
  if (s < 60) return '방금'
  if (s < 3600) return Math.floor(s / 60) + '분 전'
  if (s < 86400) return Math.floor(s / 3600) + '시간 전'
  if (s < 86400 * 7) return Math.floor(s / 86400) + '일 전'
  return date(ts)
}
export const MARKET_LABEL = { KOSPI: '코스피', KOSDAQ: '코스닥', NASDAQ: '나스닥', NYSE: '뉴욕', AMEX: '아멕스', CRYPTO: '코인', MACRO: '지표' }
export function curOf(symbol) { return symbol && symbol.startsWith('US:') ? 'USD' : 'KRW' }
