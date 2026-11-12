<template>
  <!-- 반원 계기판: stops 로 나눈 구간마다 색을 칠하고 바늘로 점수를 가리킨다 -->
  <svg viewBox="0 0 200 108" style="width:100%;max-width:260px" role="img" :aria-label="`점수 ${score}`">
    <path v-for="(a, i) in arcs" :key="i" :d="a" :stroke="colors[i]" stroke-width="13" fill="none" />
    <line :x1="CX" :y1="CY" :x2="needle[0]" :y2="needle[1]" stroke="var(--text)" stroke-width="3" stroke-linecap="round" />
    <circle :cx="CX" :cy="CY" r="5" fill="var(--text)" />
  </svg>
</template>
<script setup>
import { computed } from 'vue'
const props = defineProps({ score: Number, stops: { type: Array, required: true }, colors: { type: Array, required: true } })
const R = 80; const CX = 100; const CY = 96
function pt(v, rad = R) { const a = Math.PI * (1 - v / 100); return [CX + rad * Math.cos(a), CY - rad * Math.sin(a)] }
const arcs = computed(() => { const e = [0, ...props.stops, 100]
  return e.slice(0, -1).map((a, i) => { const [x1, y1] = pt(a + 0.6); const [x2, y2] = pt(e[i + 1] - 0.6); return `M${x1},${y1} A${R},${R} 0 0 1 ${x2},${y2}` }) })
const needle = computed(() => pt(Math.max(0, Math.min(100, props.score ?? 0)), R - 14))
</script>
