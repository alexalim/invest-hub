<template>
  <!-- 가벼운 SVG 선·막대 차트 (평가액 곡선, 통계, 유사차트 비교용) -->
  <svg :viewBox="`0 0 ${w} ${h}`" class="mc" :style="{ height: h + 'px' }" preserveAspectRatio="none" role="img" :aria-label="label">
    <line v-if="zeroY !== null" :x1="pad" :x2="w - pad" :y1="zeroY" :y2="zeroY" class="zero" />
    <template v-if="type === 'bar'">
      <g v-for="(b, i) in bars" :key="i">
        <rect :x="b.x" :y="b.y" :width="b.w" :height="b.h" :fill="b.color" rx="2"><title>{{ b.title }}</title></rect>
      </g>
    </template>
    <template v-else>
      <path v-if="band" :d="band" class="band" />
      <path v-for="(p, i) in paths" :key="i" :d="p.d" :stroke="p.color" :stroke-width="p.width || 1.8" :stroke-dasharray="p.dashed ? '4 3' : ''" fill="none" vector-effect="non-scaling-stroke" />
      <line v-if="split !== null" :x1="sx(split)" :x2="sx(split)" :y1="pad" :y2="h - pad" class="zero" stroke-dasharray="3 3" />
    </template>
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  series: { type: Array, default: () => [] },   // [{ values: [..], color, dashed }]
  type: { type: String, default: 'line' },
  labels: { type: Array, default: () => [] },
  bandLow: { type: Array, default: null }, bandHigh: { type: Array, default: null }, // 범위 음영
  split: { type: Number, default: null },        // 이 인덱스에 세로 점선
  h: { type: Number, default: 160 }, w: { type: Number, default: 600 },
  zero: { type: Boolean, default: false }, label: { type: String, default: '차트' },
})
const pad = 6
const all = computed(() => {
  const v = props.series.flatMap(s => s.values).concat(props.bandLow || [], props.bandHigh || []).filter(x => x != null && Number.isFinite(x))
  if (props.zero || props.type === 'bar') v.push(0)
  return v
})
const lo = computed(() => Math.min(...all.value)); const hi = computed(() => Math.max(...all.value))
const n = computed(() => Math.max(...props.series.map(s => s.values.length), props.bandLow?.length || 0, 2))
function sx(i) { return pad + (i / (n.value - 1)) * (props.w - pad * 2) }
function sy(v) { const r = hi.value - lo.value || 1; return props.h - pad - ((v - lo.value) / r) * (props.h - pad * 2) }
const zeroY = computed(() => (props.zero || props.type === 'bar') && lo.value < 0 && hi.value > 0 ? sy(0) : null)
const paths = computed(() => props.series.map(s => ({ ...s, d: s.values.map((v, i) => v == null ? '' : `${i === 0 || s.values[i - 1] == null ? 'M' : 'L'}${sx(i)},${sy(v)}`).join(' ') })))
const band = computed(() => {
  if (!props.bandLow || !props.bandHigh) return null
  const off = n.value - props.bandLow.length
  const top = props.bandHigh.map((v, i) => `${i ? 'L' : 'M'}${sx(i + off)},${sy(v)}`).join(' ')
  const bot = props.bandLow.map((v, i) => `L${sx(i + off)},${sy(v)}`).reverse().join(' ')
  return top + ' ' + bot + ' Z'
})
const bars = computed(() => {
  const s = props.series[0]; if (!s) return []
  const k = s.values.length || 1
  const bw = (props.w - pad * 2) / k
  const base = sy(Math.max(0, lo.value))
  return s.values.map((v, i) => {
    const y = sy(v)
    return { x: pad + i * bw + bw * 0.15, w: bw * 0.7, y: Math.min(y, base), h: Math.max(1, Math.abs(base - y)),
      color: s.colors ? s.colors[i] : (v >= 0 ? s.color || 'var(--accent)' : 'var(--down)'), title: `${props.labels[i] ?? ''} ${v}` }
  })
})
</script>

<style scoped>
.mc { width: 100%; display: block; }
.zero { stroke: var(--line); stroke-width: 1; }
.band { fill: var(--accent); opacity: .12; }
</style>
