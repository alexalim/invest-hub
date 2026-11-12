<template>
  <div class="pc" :style="{ height: height + 'px' }">
    <div ref="el" class="pc-canvas" :style="{ bottom: oscillators.length ? oscH + 'px' : 0 }" />
    <div v-show="oscillators.length" ref="el2" class="pc-osc" :style="{ height: oscH + 'px' }" />
    <div v-if="legend" class="pc-legend small">
      <span class="faint">{{ legend.time }}</span>
      <span>시 <b>{{ legend.o }}</b></span><span>고 <b class="up">{{ legend.h }}</b></span><span>저 <b class="down">{{ legend.l }}</b></span><span>종 <b>{{ legend.c }}</b></span>
      <span v-if="legend.v" class="faint">거래량 {{ legend.v }}</span>
    </div>
  </div>
</template>

<script setup>
// lightweight-charts 4.x 래퍼. 캔들 + 거래량 + 겹쳐 그리는 지표 + 하단 보조지표 + 마커 + 가격선/추세선.
import { createChart, CrosshairMode, LineStyle } from 'lightweight-charts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { price as fmtPrice, vol as fmtVol } from '../lib/fmt'

const props = defineProps({
  candles: { type: Array, default: () => [] },        // [[ts,o,h,l,c,v]]
  overlays: { type: Array, default: () => [] },       // [{ data: [[ts, v]], color, title }]
  oscillators: { type: Array, default: () => [] },    // 같은 형식, 하단 영역
  markers: { type: Array, default: () => [] },        // [{ time, position, color, shape, text }]
  priceLines: { type: Array, default: () => [] },     // [{ price, color, title, style }]
  trendLines: { type: Array, default: () => [] },     // [{ points: [[t, p], [t, p]], color }]
  height: { type: Number, default: 460 },
  intraday: { type: Boolean, default: false },
  currency: { type: String, default: 'KRW' },
  showVolume: { type: Boolean, default: true },
  line: { type: Boolean, default: false },            // 캔들 대신 선 (지수·환율 등)
})
const emit = defineEmits(['click'])
const el = ref(null)
const el2 = ref(null)
const oscH = 130
let chart2 = null
let oscSeriesList = []
let syncing = false
const legend = ref(null)
let chart, main, volume, ro
let extra = []
let lines = []

function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim() }
function clean(rows) {
  // 4.x는 시간이 겹치거나 뒤섞이면 예외를 던진다: 정렬 후 중복 제거
  const m = new Map()
  for (const r of rows) if (r && r[0] != null && r[4] != null) m.set(+r[0], r)
  return [...m.values()].sort((a, b) => a[0] - b[0])
}
function cleanSeries(data) {
  const m = new Map()
  for (const [t, v] of data || []) if (v != null && Number.isFinite(+v)) m.set(+t, +v)
  return [...m.entries()].sort((a, b) => a[0] - b[0]).map(([time, value]) => ({ time, value }))
}
function theme() {
  return {
    layout: { background: { color: 'transparent' }, textColor: css('--muted'), fontSize: 11, fontFamily: 'inherit' },
    grid: { vertLines: { color: css('--line') + '80' }, horzLines: { color: css('--line') + '80' } },
    rightPriceScale: { borderColor: css('--line') }, timeScale: { borderColor: css('--line') },
  }
}

function build() {
  chart = createChart(el.value, {
    ...theme(), autoSize: true, crosshair: { mode: CrosshairMode.Normal },
    localization: { locale: 'ko-KR', priceFormatter: p => fmtPrice(p, props.currency) },
    timeScale: { ...theme().timeScale, timeVisible: props.intraday, secondsVisible: false, rightOffset: 4 },
  })
  chart.subscribeCrosshairMove(p => {
    if (!p || !p.time || !main) { legend.value = null; return }
    const d = p.seriesData.get(main)
    if (!d) return
    const t = new Date(p.time * 1000).toISOString()
    legend.value = {
      time: props.intraday ? t.slice(0, 16).replace('T', ' ') : t.slice(0, 10),
      o: fmtPrice(d.open ?? d.value, props.currency), h: fmtPrice(d.high ?? d.value, props.currency),
      l: fmtPrice(d.low ?? d.value, props.currency), c: fmtPrice(d.close ?? d.value, props.currency),
      v: volume ? fmtVol(p.seriesData.get(volume)?.value) : null,
    }
  })
  chart.subscribeClick(p => {
    if (!p || !p.point || !main) return
    emit('click', { time: p.time, price: main.coordinateToPrice(p.point.y) })
  })
  chart2 = createChart(el2.value, { ...theme(), autoSize: true, crosshair: { mode: CrosshairMode.Normal },
    timeScale: { ...theme().timeScale, visible: false, rightOffset: 4 }, rightPriceScale: { ...theme().rightPriceScale, minimumWidth: 70 } })
  chart.applyOptions({ rightPriceScale: { ...theme().rightPriceScale, minimumWidth: 70 } })
  // 위 차트가 기준이다. 아래(보조지표) 차트는 사용자가 그 위에서 직접 끌 때만 위 차트를 움직인다.
  // (아래 차트는 숨겨진 채 만들어져서, 나타날 때 생기는 범위 변화가 위 차트를 밀어내는 일이 있었다)
  let over2 = false
  el2.value.addEventListener('pointerenter', () => { over2 = true })
  el2.value.addEventListener('pointerleave', () => { over2 = false })
  const sync = (src, dst, allow) => src.timeScale().subscribeVisibleLogicalRangeChange(r => {
    if (syncing || !r || !allow()) return
    syncing = true; dst.timeScale().setVisibleLogicalRange(r); syncing = false
  })
  sync(chart, chart2, () => !over2); sync(chart2, chart, () => over2)
  ro = new ResizeObserver(() => alignOsc()); ro.observe(el2.value)
  render(true)
}

function render(fit = false) {
  if (!chart) return
  syncing = true   // 자료를 바꾸는 동안에는 두 차트의 범위 동기화를 멈춘다
  const up = css('--up'), down = css('--down')
  const hasOsc = props.oscillators.length > 0
  for (const s of extra) chart.removeSeries(s)
  extra = []
  if (main) { chart.removeSeries(main); main = null }
  if (volume) { chart.removeSeries(volume); volume = null }
  const rows = clean(props.candles)
  if (props.line) {
    main = chart.addAreaSeries({ lineColor: css('--accent'), topColor: css('--accent') + '40', bottomColor: css('--accent') + '05', lineWidth: 2 })
    main.setData(rows.map(r => ({ time: r[0], value: r[4] })))
  } else {
    main = chart.addCandlestickSeries({ upColor: up, downColor: down, borderUpColor: up, borderDownColor: down, wickUpColor: up, wickDownColor: down })
    main.setData(rows.map(r => ({ time: r[0], open: r[1], high: r[2], low: r[3], close: r[4] })))
  }
  main.priceScale().applyOptions({ scaleMargins: { top: 0.06, bottom: props.showVolume ? 0.2 : 0.06 } })
  if (props.showVolume && rows.some(r => r[5])) {
    volume = chart.addHistogramSeries({ priceScaleId: 'vol', priceFormat: { type: 'volume' }, lastValueVisible: false, priceLineVisible: false })
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
    volume.setData(rows.map(r => ({ time: r[0], value: r[5], color: (r[4] >= r[1] ? up : down) + '55' })))
  }
  for (const o of props.overlays) {
    const s = chart.addLineSeries({ color: o.color, lineWidth: o.width || 1.5, lineStyle: o.dashed ? LineStyle.Dashed : LineStyle.Solid,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, title: o.title || '' })
    s.setData(cleanSeries(o.data))
    extra.push(s)
  }
  for (const x of oscSeriesList) chart2.removeSeries(x)
  oscSeriesList = []
  // 보조지표는 아래 별도 차트에 그린다 (같은 축에 그리면 가격 눈금이 겹친다). 시간축을 맞추려고 캔들 시각에 빈 값도 채운다
  const whitespace = chart2.addLineSeries({ lineVisible: false, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
  whitespace.setData(rows.map(r => ({ time: r[0] })))
  oscSeriesList.push(whitespace)
  for (const o of props.oscillators) {
    const s2 = o.histogram
      ? chart2.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false })
      : chart2.addLineSeries({ color: o.color, lineWidth: 1.5, priceLineVisible: false, lastValueVisible: true, title: o.title || '' })
    const data = cleanSeries(o.data)
    s2.setData(o.histogram ? data.map(d => ({ ...d, color: (d.value >= 0 ? up : down) + '99' })) : data)
    oscSeriesList.push(s2)
  }
  for (const t of props.trendLines) {
    const pts = cleanSeries(t.points)
    if (pts.length < 2) continue
    const s = chart.addLineSeries({ color: t.color || css('--warn'), lineWidth: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false })
    s.setData(pts)
    extra.push(s)
  }
  for (const p of props.priceLines) {
    main.createPriceLine({ price: p.price, color: p.color || css('--warn'), lineWidth: 1, lineStyle: p.style ?? LineStyle.Dashed, axisLabelVisible: true, title: p.title || '' })
  }
  const times = new Set(rows.map(r => r[0]))
  main.setMarkers(props.markers.filter(m => times.has(m.time)).sort((a, b) => a.time - b.time))
  if (fit) {
    // 화면 폭에 맞춰 처음 보여 줄 봉 수를 정한다 (봉 하나에 5px 안팎, 60~200개)
    const show = Math.round(Math.min(200, Math.max(60, (el.value?.clientWidth || 900) / 5)))
    const apply = () => {
      if (!chart) return
      if (rows.length > show + 20) chart.timeScale().setVisibleLogicalRange({ from: rows.length - show, to: rows.length + 4 })
      else chart.timeScale().fitContent()
    }
    apply()
    setTimeout(() => { apply(); alignOsc() }, 80)   // 크기가 늦게 잡히는 경우(탭 전환·좁은 화면)에 한 번 더
  }
  alignOsc()
  // 아래 차트는 방금 나타났을 수 있어 크기가 잡힌 뒤에 한 번 더 맞춘다
  setTimeout(() => { alignOsc(); syncing = false }, 60)
  setTimeout(alignOsc, 350)
}

function alignOsc() {
  if (!chart || !chart2 || !props.oscillators.length) return
  const r = chart.timeScale().getVisibleLogicalRange()
  if (r) { const was = syncing; syncing = true; chart2.timeScale().setVisibleLogicalRange(r); syncing = was }
}

let fitNext = true
watch(() => props.candles, (n, o) => { render(fitNext || !o || !o.length || n.length - o.length > 2 || (n[0] && o[0] && n[0][0] !== o[0][0])); fitNext = false })
watch(() => [props.overlays, props.oscillators, props.markers, props.priceLines, props.trendLines, props.line], () => render(false), { deep: true })
watch(() => props.intraday, v => chart && chart.applyOptions({ timeScale: { timeVisible: v } }))
function onTheme() { chart && chart.applyOptions(theme()); chart2 && chart2.applyOptions(theme()); render(false) }
onMounted(() => { build(); window.addEventListener('themechange', onTheme) })
onBeforeUnmount(() => { window.removeEventListener('themechange', onTheme); ro && ro.disconnect(); chart && chart.remove(); chart2 && chart2.remove(); chart = null; chart2 = null })
defineExpose({
  fit: () => chart && chart.timeScale().fitContent(),
  // 두 시각이 모두 보이도록 앞뒤 여유를 두고 맞춘다
  showRange: (from, to) => {
    if (!chart || !from || !to) return
    const pad = Math.max(86400 * 10, (to - from) * 0.08)
    try { chart.timeScale().setVisibleRange({ from: from - pad, to: to + pad }) } catch { /* 자료 범위 밖 */ }
  },
})
</script>

<style scoped>
.pc { position: relative; width: 100%; }
.pc-canvas { position: absolute; top: 0; left: 0; right: 0; }
.pc-osc { position: absolute; left: 0; right: 0; bottom: 0; border-top: 1px solid var(--line); }
.pc-legend { position: absolute; left: 8px; top: 4px; z-index: 3; display: flex; gap: 10px; flex-wrap: wrap; pointer-events: none; background: var(--panel); opacity: .92; padding: 0 4px; border-radius: 4px; }
</style>
