<template>
  <div>
    <div class="page-h"><div><h1>유사차트</h1><div class="muted small">원하는 모양을 마우스로 그리면, 최근 차트가 그 모양과 닮은 종목을 찾습니다. 특정 종목과 닮은 종목은 종목 화면의 '유사차트' 탭에서 볼 수 있습니다.</div></div></div>
    <div class="grid g-side">
      <div class="card">
        <div class="row between" style="margin-bottom:8px">
          <div class="row wrap"><button v-for="p in PRESETS" :key="p[0]" class="sm" @click="usePreset(p[1])">{{ p[0] }}</button></div>
          <button class="sm ghost" @click="clear">지우기</button></div>
        <canvas ref="cv" width="800" height="300" class="cv" @pointerdown="start" @pointermove="move" @pointerup="end" @pointerleave="end" />
        <div class="row" style="margin-top:8px">
          <div class="seg"><button v-for="w in [30, 60, 120]" :key="w" :class="{ on: win === w }" @click="win = w">최근 {{ w }}일과 비교</button></div>
          <button class="primary" :disabled="pts.length < 5 || busy" @click="search">{{ busy ? '찾는 중…' : '닮은 차트 찾기' }}</button></div>
      </div>
      <div class="card"><h3>사용법</h3><p class="small muted">왼쪽에서 오른쪽으로 한 번에 선을 그어 주세요. 높이는 상대적인 모양만 봅니다. 위쪽 버튼으로 대표 패턴을 불러올 수도 있습니다.</p></div>
    </div>
    <div v-if="res" class="grid g4" style="margin-top:12px">
      <router-link v-for="s in res" :key="s.symbol" :to="'/stock/' + s.symbol" class="card" style="padding:10px">
        <div class="row between"><b class="small ellipsis">{{ s.name }}</b><span class="tiny faint">유사도 {{ s.corr }}</span></div>
        <MiniChart :series="[{ values: s.series, color: 'var(--accent)' }]" :h="70" />
      </router-link>
      <div v-if="!res.length" class="empty">결과가 없습니다</div>
    </div>
  </div>
</template>
<script setup>
import { onMounted, ref } from 'vue'
import MiniChart from '../components/MiniChart.vue'
import { api } from '../lib/api'
const cv = ref(null); const pts = ref([]); const win = ref(60); const res = ref(null); const busy = ref(false); let drawing = false
const PRESETS = [['쌍바닥(W)', [8, 3, 6, 3, 9]], ['상승 추세', [1, 3, 2, 5, 4, 7, 6, 9]], ['V자 반등', [9, 6, 3, 1, 4, 7, 9]], ['박스권 돌파', [5, 6, 5, 6, 5, 6, 5, 9]], ['고점 후 하락', [2, 5, 8, 9, 7, 5, 3]], ['컵앤핸들', [8, 5, 3, 3, 5, 8, 7, 7.5, 9]]]
function ctx() { return cv.value.getContext('2d') }
function redraw() {
  const c = ctx(); const W = cv.value.width, H = cv.value.height
  c.clearRect(0, 0, W, H)
  c.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--line'); c.lineWidth = 1
  for (let i = 1; i < 6; i++) { c.beginPath(); c.moveTo(0, H * i / 6); c.lineTo(W, H * i / 6); c.stroke() }
  if (pts.value.length < 2) return
  c.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--accent'); c.lineWidth = 3; c.lineJoin = 'round'
  c.beginPath(); pts.value.forEach(([x, y], i) => i ? c.lineTo(x, y) : c.moveTo(x, y)); c.stroke()
}
function pos(e) { const r = cv.value.getBoundingClientRect(); return [(e.clientX - r.left) * cv.value.width / r.width, (e.clientY - r.top) * cv.value.height / r.height] }
function start(e) { drawing = true; pts.value = [pos(e)]; cv.value.setPointerCapture(e.pointerId); redraw() }
function move(e) { if (!drawing) return; const p = pos(e); if (p[0] > pts.value[pts.value.length - 1][0]) { pts.value.push(p); redraw() } }
function end() { drawing = false }
function clear() { pts.value = []; res.value = null; redraw() }
function usePreset(vals) {
  const W = cv.value.width, H = cv.value.height, lo = Math.min(...vals), hi = Math.max(...vals)
  pts.value = vals.map((v, i) => [20 + i * (W - 40) / (vals.length - 1), H - 20 - (v - lo) / (hi - lo) * (H - 40)]); redraw()
}
async function search() {
  busy.value = true
  try { res.value = await api.post('/discover/similar', { series: pts.value.map(p => cv.value.height - p[1]), window: win.value }) } finally { busy.value = false }
}
onMounted(redraw)
</script>
<style scoped>.cv { width: 100%; height: auto; aspect-ratio: 8/3; border: 1px solid var(--line); border-radius: 8px; touch-action: none; cursor: crosshair; background: var(--panel-2); }</style>
