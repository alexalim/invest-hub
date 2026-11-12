<template>
  <div>
    <div class="page-h"><div><h1>위험·심리 지표</h1><div class="muted small">미국 금융시장의 위험 신호 {{ r?.count || '' }}개와 코스피 공포·탐욕을 0~100 점수로 봅니다. 값이 최근 3년 가운데 어디쯤인지로 점수를 매깁니다.</div></div></div>
    <div v-if="!r && !err" class="spinner" />
    <div v-if="err" class="card empty">{{ err }}</div>
    <template v-if="r">
      <div class="grid g-gauge">
        <div class="card center">
          <h3>미국 위험 점수 <span class="small muted">{{ dateLabel(r.asof) }} 종가</span></h3>
          <Gauge :score="r.score" :stops="[30, 55, 75]" :colors="['#16a34a', '#64748b', '#d97706', '#e0353c']" />
          <div class="big">{{ r.score }}</div><span class="chip" :class="chip(r.level)">{{ r.level }}</span>
          <div class="small muted" style="margin-top:6px">1주 전보다 <b>{{ signed(r.week) }}</b> · 1개월 전보다 <b>{{ signed(r.month) }}</b></div>
          <div class="tiny faint">0 안정 · 30 보통 · 55 경계 · 75 위험</div>
        </div>
        <div class="card">
          <h3>점수 추이 <span class="small muted">최근 1년</span></h3>
          <MiniChart :series="[{ values: r.history.map(h => h.score), color: 'var(--accent)' }]" :h="210" label="위험 점수 추이" />
          <div class="row between tiny faint"><span>{{ dateLabel(r.history[0].date) }}</span><span>{{ dateLabel(r.history[r.history.length - 1].date) }}</span></div>
        </div>
      </div>

      <h2 style="margin-top:16px">분류별</h2>
      <div class="tiles">
        <button v-for="c in r.categories" :key="c.name" class="card tile" :class="{ sel: cat === c.name }" @click="cat = cat === c.name ? '' : c.name">
          <div class="row between"><b>{{ c.name }}</b><span class="chip" :class="chip(c.level)">{{ c.level }}</span></div>
          <div class="v">{{ c.score }}</div><div class="tiny muted">1주 {{ signed(c.week) }}</div>
        </button>
      </div>

      <h2 style="margin-top:16px">지표 {{ cat ? '· ' + cat : '' }}</h2>
      <div class="grid g3 ind">
        <div v-for="i in items" :key="i.key" class="card">
          <div class="row between"><b class="small">{{ i.name }}</b><span class="chip" :class="chip(i.level)">{{ i.level }} {{ i.score }}</span></div>
          <div class="v">{{ fmt(i.value) }}<span class="small muted"> {{ i.unit }}</span><span class="tiny muted" style="margin-left:8px">점수 1주 {{ signed(i.week) }}</span></div>
          <MiniChart :series="[{ values: i.spark, color: 'var(--accent)' }]" :h="54" :label="i.name" />
          <div class="tiny faint">{{ i.desc }}</div>
        </div>
      </div>
    </template>

    <template v-if="f && f.score != null">
      <h2 style="margin-top:20px">코스피 공포·탐욕</h2>
      <div class="grid g-gauge">
        <div class="card center">
          <h3>지금 <span class="small muted">{{ dateLabel(f.asof) }} 종가</span></h3>
          <Gauge :score="f.score" :stops="[20, 40, 60, 80]" :colors="['#2366d1', '#60a5fa', '#64748b', '#f59e0b', '#e0353c']" />
          <div class="big">{{ f.score }}</div><span class="chip blue">{{ f.label }}</span>
          <div class="small muted" style="margin-top:6px">1주 전보다 <b>{{ signed(f.week) }}</b> · 1개월 전보다 <b>{{ signed(f.month) }}</b></div>
          <div class="tiny faint">0 극단적 공포 · 100 극단적 탐욕</div>
        </div>
        <div class="card">
          <h3>추이와 코스피 <span class="small muted">파랑 = 공포·탐욕, 회색 = 코스피(모양 비교용)</span></h3>
          <div class="overlay"><MiniChart :series="[{ values: f.history.map(h => h.score), color: 'var(--accent)' }]" :h="170" label="공포·탐욕 추이" />
            <MiniChart class="over" :series="[{ values: f.history.map(h => h.close), color: 'var(--faint)', width: 1.2 }]" :h="170" label="코스피" /></div>
          <table class="t" style="margin-top:8px"><thead><tr><th>구성 요소</th><th class="num">값</th><th class="num">점수</th><th style="width:34%"></th></tr></thead>
            <tbody><tr v-for="c in f.components" :key="c.key"><td>{{ c.name }}<div class="tiny faint">{{ c.desc }}</div></td>
              <td class="num">{{ fmt(c.value) }}</td><td class="num"><b>{{ c.score }}</b></td>
              <td><div class="bar"><i :style="{ width: c.score + '%' }" /></div></td></tr></tbody></table>
        </div>
      </div>
    </template>

    <div class="card small muted" style="margin-top:14px">
      <b>읽는 법과 한계</b>
      <ul style="margin:6px 0 0 18px;padding:0">
        <li>점수는 "지금 값이 최근 3년 가운데 몇 번째로 위험한 쪽인가"입니다. 70이면 최근 3년 중 70%의 날보다 위험한 쪽이라는 뜻입니다.</li>
        <li>종합 점수는 분류별 평균을 다시 평균한 값이라, 지표 수가 많은 분류가 더 큰 영향을 주지 않습니다.</li>
        <li>신용 지표는 채권 ETF 가격 비율로 만든 대용 지표입니다. 실제 회사채 스프레드나 단기자금 시장(레포) 원자료는 들어 있지 않습니다.</li>
        <li>이 점수로 주가를 맞힐 수 있는지는 검증하지 않았습니다. 시장 분위기를 한눈에 보는 용도입니다.</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { computed, h, ref } from 'vue'
import MiniChart from '../components/MiniChart.vue'
import { api } from '../lib/api'
import { signed } from '../lib/fmt'

// 반원 계기판: stops 로 나눈 구간마다 색을 칠하고 바늘로 점수를 가리킨다
const Gauge = (p) => {
  const R = 80; const cx = 100; const cy = 96
  const pt = (v, rad = R) => { const a = Math.PI * (1 - v / 100); return [cx + rad * Math.cos(a), cy - rad * Math.sin(a)] }
  const edges = [0, ...p.stops, 100]
  const arcs = edges.slice(0, -1).map((a, i) => { const [x1, y1] = pt(a + 0.6); const [x2, y2] = pt(edges[i + 1] - 0.6)
    return h('path', { d: `M${x1},${y1} A${R},${R} 0 0 1 ${x2},${y2}`, stroke: p.colors[i], 'stroke-width': 13, fill: 'none', 'stroke-linecap': 'butt' }) })
  const [nx, ny] = pt(Math.max(0, Math.min(100, p.score ?? 0)), R - 14)
  return h('svg', { viewBox: '0 0 200 108', style: 'width:100%;max-width:260px', role: 'img', 'aria-label': `점수 ${p.score}` },
    [...arcs, h('line', { x1: cx, y1: cy, x2: nx, y2: ny, stroke: 'var(--text)', 'stroke-width': 3, 'stroke-linecap': 'round' }), h('circle', { cx, cy, r: 5, fill: 'var(--text)' })])
}
Gauge.props = ['score', 'stops', 'colors']

const r = ref(null); const f = ref(null); const err = ref(''); const cat = ref('')
api.get('/pulse/risk', null, { quiet: true }).then(x => (r.value = x)).catch(e => (err.value = e.message || '해외 시세를 받지 못했습니다'))
api.get('/pulse/feargreed', null, { quiet: true }).then(x => (f.value = x)).catch(() => {})
const items = computed(() => r.value.items.filter(i => !cat.value || i.category === cat.value))
function chip(level) { return { 안정: 'green', 보통: '', 경계: 'orange', 위험: 'red' }[level] }
function dateLabel(s) { return s ? `${+s.slice(4, 6)}/${+s.slice(6, 8)}` : '' }
function fmt(v) { return v == null ? '-' : Math.abs(v) >= 1000 ? Math.round(v).toLocaleString('ko-KR') : (+v).toFixed(2) }
</script>

<style scoped>
.g-gauge { grid-template-columns: 300px minmax(0, 1fr); }
.center { display: flex; flex-direction: column; align-items: center; text-align: center; }
.big { font-size: 40px; font-weight: 800; line-height: 1; margin: -6px 0 6px; font-variant-numeric: tabular-nums; }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 8px; }
.tile { padding: 10px 12px; text-align: left; } .tile.sel { border-color: var(--accent); }
.tile .v, .ind .v { font-size: 20px; font-weight: 700; font-variant-numeric: tabular-nums; margin: 4px 0; }
.overlay { position: relative; } .overlay .over { position: absolute; inset: 0; pointer-events: none; }
.bar { height: 8px; background: var(--panel-2); border-radius: 4px; overflow: hidden; } .bar i { display: block; height: 100%; background: var(--accent); }
@media (max-width: 900px) { .g-gauge { grid-template-columns: 1fr; } }
</style>
