<template>
  <!-- 가벼운 SVG 선·막대 차트. 마우스를 올리면 그 지점의 값을 보여 준다. -->
  <div class="mcw" @mousemove="move" @mouseleave="hover = null" @touchstart.passive="move" @touchmove.passive="move" @touchend="hover = null">
    <svg ref="svg" :viewBox="`0 0 ${w} ${h}`" class="mc" :style="{ height: h + 'px' }" preserveAspectRatio="none" role="img" :aria-label="label">
      <line v-if="zeroY !== null" :x1="pad" :x2="w - pad" :y1="zeroY" :y2="zeroY" class="zero" />
      <template v-if="type === 'bar'">
        <rect v-for="(b, i) in bars" :key="i" :x="b.x" :y="b.y" :width="b.w" :height="b.h" :fill="b.color" :opacity="hover === null || hover === i ? 1 : .55" rx="2" />
      </template>
      <template v-else>
        <path v-if="band" :d="band" class="band" />
        <path v-for="(p, i) in paths" :key="i" :d="p.d" :stroke="p.color" :stroke-width="p.width || 1.8" :stroke-dasharray="p.dashed ? '4 3' : ''" fill="none" vector-effect="non-scaling-stroke" />
        <line v-if="split !== null" :x1="sx(split)" :x2="sx(split)" :y1="pad" :y2="h - pad" class="zero" stroke-dasharray="3 3" />
      </template>
    </svg>
    <template v-if="axis && left.n">
      <span class="ax tl">{{ show(left.hi) }}</span><span class="ax bl">{{ show(left.lo) }}</span>
      <template v-if="right.n"><span class="ax tr">{{ show(right.hi, rightSeries) }}</span><span class="ax br">{{ show(right.lo, rightSeries) }}</span></template>
    </template>
    <template v-if="tip && hover !== null && tipRows.length">
      <div v-if="type !== 'bar'" class="guide" :style="{ left: guideX + '%', height: h + 'px' }" />
      <div class="tip" :class="{ flip: guideX > 50, above: h < 90 }" :style="guideX > 50 ? { right: 100 - guideX + '%' } : { left: guideX + '%' }">
        <div v-if="labels[hover] != null" class="tl-h">{{ labels[hover] }}</div>
        <div v-for="(r, i) in tipRows" :key="i" class="tr-r"><span v-if="r.color" class="dot" :style="{ background: r.color }" />
          <span v-if="r.name" class="nm">{{ r.name }}</span><b>{{ r.text }}</b></div>
      </div>
    </template>
    <div v-if="xaxis && labels.length > 1" class="xl"><span>{{ labels[0] }}</span><span v-if="labels.length > 4">{{ labels[Math.floor((labels.length - 1) / 2)] }}</span><span>{{ labels[labels.length - 1] }}</span></div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  series: { type: Array, default: () => [] },   // [{ values, color, name, dashed, width, axis: 'right', fmt }]
  type: { type: String, default: 'line' },
  labels: { type: Array, default: () => [] },    // 가로축 이름(날짜·시각). 값 표시 머리말과 xaxis 에 쓴다
  bandLow: { type: Array, default: null }, bandHigh: { type: Array, default: null }, // 범위 음영
  split: { type: Number, default: null },        // 이 인덱스에 세로 점선
  h: { type: Number, default: 160 }, w: { type: Number, default: 600 },
  zero: { type: Boolean, default: false }, label: { type: String, default: '차트' },
  axis: { type: Boolean, default: false },       // 세로축 최댓값·최솟값 표시
  xaxis: { type: Boolean, default: false },      // 가로축 처음·가운데·끝 이름 표시
  tip: { type: Boolean, default: true },         // 마우스를 올리면 값 표시
  fmt: { type: Function, default: null },
})
const pad = 6
const svg = ref(null); const hover = ref(null)
const isRight = s => s.axis === 'right' && props.type !== 'bar'
function range(vals, withZero) {
  const v = vals.filter(x => x != null && Number.isFinite(x))
  const n = v.length
  if (withZero) v.push(0)
  return { lo: Math.min(...v), hi: Math.max(...v), n }
}
// 왼쪽 축과 오른쪽(보조) 축은 눈금을 따로 잡는다. 단위가 다른 두 선을 한 차트에 겹칠 때 쓴다.
const left = computed(() => range(props.series.filter(s => !isRight(s)).flatMap(s => s.values).concat(props.bandLow || [], props.bandHigh || []), props.zero || props.type === 'bar'))
const right = computed(() => range(props.series.filter(isRight).flatMap(s => s.values), false))
const rightSeries = computed(() => props.series.find(isRight))
const n = computed(() => Math.max(...props.series.map(s => s.values.length), props.bandLow?.length || 0, 2))
function sx(i) { return pad + (i / (n.value - 1)) * (props.w - pad * 2) }
function sy(v, r = left.value) { const d = r.hi - r.lo || 1; return props.h - pad - ((v - r.lo) / d) * (props.h - pad * 2) }
const zeroY = computed(() => (props.zero || props.type === 'bar') && left.value.lo < 0 && left.value.hi > 0 ? sy(0) : null)
const paths = computed(() => props.series.map(s => {
  const r = isRight(s) ? right.value : left.value
  return { ...s, d: s.values.map((v, i) => v == null ? '' : `${i === 0 || s.values[i - 1] == null ? 'M' : 'L'}${sx(i)},${sy(v, r)}`).join(' ') }
}))
const band = computed(() => {
  if (!props.bandLow || !props.bandHigh) return null
  const off = n.value - props.bandLow.length
  const top = props.bandHigh.map((v, i) => `${i ? 'L' : 'M'}${sx(i + off)},${sy(v)}`).join(' ')
  const bot = props.bandLow.map((v, i) => `L${sx(i + off)},${sy(v)}`).reverse().join(' ')
  return top + ' ' + bot + ' Z'
})
const barW = computed(() => (props.w - pad * 2) / (props.series[0]?.values.length || 1))
const bars = computed(() => {
  const s = props.series[0]; if (!s) return []
  const bw = barW.value
  const base = sy(Math.max(0, left.value.lo))
  return s.values.map((v, i) => {
    const y = sy(v)
    return { x: pad + i * bw + bw * 0.15, w: bw * 0.7, y: Math.min(y, base), h: Math.max(1, Math.abs(base - y)),
      color: s.colors ? s.colors[i] : (v >= 0 ? s.color || 'var(--accent)' : 'var(--down)') }
  })
})

function show(v, s) {
  const f = s?.fmt || (s && isRight(s) ? null : props.fmt)   // 보조 축 선에는 왼쪽 축 단위를 붙이지 않는다
  if (f) return f(v)
  const a = Math.abs(v)
  return a >= 1000 ? Math.round(v).toLocaleString('ko-KR') : a >= 100 ? (+v).toFixed(1) : (+v).toFixed(2)
}
function move(e) {
  if (!props.tip || !svg.value) return
  const box = svg.value.getBoundingClientRect()
  const cx = (e.touches ? e.touches[0].clientX : e.clientX) - box.left
  const x = (cx / (box.width || 1)) * props.w
  const last = (props.type === 'bar' ? props.series[0]?.values.length || 1 : n.value) - 1
  const i = props.type === 'bar' ? Math.floor((x - pad) / barW.value) : Math.round(((x - pad) / (props.w - pad * 2)) * last)
  hover.value = Math.max(0, Math.min(last, i))
}
const guideX = computed(() => (props.type === 'bar' ? pad + (hover.value + 0.5) * barW.value : sx(hover.value)) / props.w * 100)
const tipRows = computed(() => (props.type === 'bar' ? props.series.slice(0, 1) : props.series)
  .filter(s => s.values[hover.value] != null)
  .map(s => ({ name: s.name, color: props.type === 'bar' ? null : s.color, text: show(s.values[hover.value], s) })))
</script>

<style scoped>
.mcw { position: relative; }
.mc { width: 100%; display: block; }
.zero { stroke: var(--line); stroke-width: 1; }
.band { fill: var(--accent); opacity: .12; }
.ax { position: absolute; font-size: 10px; line-height: 1; color: var(--faint); background: var(--panel); padding: 1px 3px; border-radius: 3px; opacity: .9; pointer-events: none; font-variant-numeric: tabular-nums; }
.ax.tl { left: 0; top: 0; } .ax.bl { left: 0; top: v-bind("(h - 12) + 'px'"); } .ax.tr { right: 0; top: 0; } .ax.br { right: 0; top: v-bind("(h - 12) + 'px'"); }
.guide { position: absolute; top: 0; width: 1px; background: var(--faint); opacity: .6; pointer-events: none; }
.tip { position: absolute; top: 4px; z-index: 5; margin: 0 8px; background: var(--panel); border: 1px solid var(--line); border-radius: 7px; padding: 5px 8px; font-size: 11px; line-height: 1.5; white-space: nowrap; pointer-events: none; box-shadow: 0 2px 8px rgba(0, 0, 0, .15); }
.tip.above { top: auto; bottom: 100%; }
.tl-h { color: var(--muted); }
.tr-r { display: flex; align-items: center; gap: 5px; } .tr-r .nm { color: var(--muted); } .tr-r b { margin-left: auto; padding-left: 8px; font-variant-numeric: tabular-nums; }
.dot { width: 7px; height: 7px; border-radius: 50%; flex: none; }
.xl { display: flex; justify-content: space-between; font-size: 11px; color: var(--faint); margin-top: 2px; }
</style>
