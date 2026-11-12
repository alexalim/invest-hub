<template>
  <div>
    <div class="page-h"><div><h1>위험·심리 지표</h1><div class="muted small">미국 금융시장의 위험 신호 {{ r?.count || '' }}개와 코스피 공포·탐욕을 0~100 점수로 봅니다. 값이 최근 3년 가운데 어디쯤인지로 점수를 매깁니다.</div></div></div>
    <Loading v-if="!r && !err" />
    <div v-if="err" class="card empty">{{ err }}</div>
    <template v-if="r">
      <div class="grid g-gauge">
        <div class="card center">
          <h3>미국 위험 점수 <span class="small muted">{{ md(r.asof) }} 종가</span></h3>
          <Gauge :score="r.score" :stops="[30, 55, 75]" :colors="['#16a34a', '#64748b', '#d97706', '#e0353c']" />
          <div class="big">{{ r.score }}</div><span class="chip" :class="chip(r.level)">{{ r.level }}</span>
          <div class="small muted" style="margin-top:6px">1주 전보다 <b>{{ signed(r.week) }}</b> · 1개월 전보다 <b>{{ signed(r.month) }}</b></div>
          <div class="tiny faint">0 안정 · 30 보통 · 55 경계 · 75 위험</div>
        </div>
        <div class="card">
          <h3>점수 추이 <span class="small muted">최근 1년</span></h3>
          <MiniChart :series="[{ name: '위험 점수', values: r.history.map(h => h.score), color: 'var(--accent)' }]" :labels="r.history.map(h => md(h.date))" :h="210" axis xaxis :fmt="pt" label="위험 점수 추이" />
        </div>
      </div>

      <h2 style="margin-top:16px">분류별 <span class="small muted">분류를 누르면 그 안의 지표가 아래에 펼쳐집니다</span></h2>
      <div class="tiles">
        <button v-for="c in r.categories" :key="c.name" class="card tile" :class="{ sel: cat === c.name }" @click="cat = c.name">
          <div class="row between"><b>{{ c.name }}</b><span class="chip" :class="chip(c.level)">{{ c.level }}</span></div>
          <div class="v">{{ c.score }}</div><div class="tiny muted">1주 {{ signed(c.week) }}</div>
        </button>
      </div>

      <div class="row between" style="margin:16px 0 10px"><h2 style="margin:0">지표 · {{ cat === ALL ? '전체' : cat }} <span class="small muted">{{ items.length }}개</span></h2>
        <button class="sm" @click="cat = cat === ALL ? worst : ALL">{{ cat === ALL ? '분류별로 보기' : '전체 ' + r.items.length + '개 펼치기' }}</button></div>
      <div class="grid g3 ind">
        <div v-for="i in items" :key="i.key" class="card">
          <div class="row between"><b class="small">{{ i.name }}</b><span class="chip" :class="chip(i.level)">{{ i.level }} {{ i.score }}</span></div>
          <div class="v">{{ fmt(i.value) }}<span class="small muted"> {{ i.unit }}</span><span class="tiny muted" style="margin-left:8px">점수 1주 {{ signed(i.week) }}</span></div>
          <MiniChart :series="[{ values: i.spark, color: 'var(--accent)' }]" :h="54" :fmt="fmt" :label="i.name" />
          <div class="tiny faint">{{ i.desc }}</div>
        </div>
      </div>
    </template>

    <template v-if="f && f.score != null">
      <h2 style="margin-top:20px">코스피 공포·탐욕</h2>
      <div class="grid g-gauge">
        <div class="card center">
          <h3>지금 <span class="small muted">{{ md(f.asof) }} 종가</span></h3>
          <Gauge :score="f.score" :stops="[20, 40, 60, 80]" :colors="['#2366d1', '#60a5fa', '#64748b', '#f59e0b', '#e0353c']" />
          <div class="big">{{ f.score }}</div><span class="chip blue">{{ f.label }}</span>
          <div class="small muted" style="margin-top:6px">1주 전보다 <b>{{ signed(f.week) }}</b> · 1개월 전보다 <b>{{ signed(f.month) }}</b></div>
          <div class="tiny faint">0 극단적 공포 · 100 극단적 탐욕</div>
        </div>
        <div class="card">
          <h3>추이와 코스피 <span class="small muted">파랑 = 공포·탐욕(왼쪽 눈금), 회색 = 코스피(오른쪽 눈금)</span></h3>
          <MiniChart :series="[{ name: '공포·탐욕', values: f.history.map(h => h.score), color: 'var(--accent)' }, { name: '코스피', values: f.history.map(h => h.close), color: 'var(--faint)', width: 1.2, axis: 'right', fmt }]"
            :labels="f.history.map(h => md(h.date))" :h="170" axis xaxis :fmt="pt" label="공포·탐욕 추이와 코스피" />
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
import { computed, ref } from 'vue'
import Gauge from '../components/Gauge.vue'
import MiniChart from '../components/MiniChart.vue'
import { api } from '../lib/api'
import { md, signed } from '../lib/fmt'

const ALL = '*'
const r = ref(null); const f = ref(null); const err = ref(''); const cat = ref(ALL)
// 지표를 한꺼번에 펼치지 않고, 처음에는 점수가 가장 높은 분류만 보여 준다
const worst = computed(() => [...r.value.categories].sort((a, b) => b.score - a.score)[0]?.name || ALL)
const pt = v => Math.round(v) + '점'
api.get('/pulse/risk', null, { quiet: true }).then(x => { r.value = x; cat.value = worst.value }).catch(e => (err.value = e.message || '해외 시세를 받지 못했습니다'))
api.get('/pulse/feargreed', null, { quiet: true }).then(x => (f.value = x)).catch(() => {})
const items = computed(() => r.value.items.filter(i => cat.value === ALL || i.category === cat.value))
function chip(level) { return { 안정: 'green', 보통: '', 경계: 'orange', 위험: 'red' }[level] }
function fmt(v) { return v == null ? '-' : Math.abs(v) >= 1000 ? Math.round(v).toLocaleString('ko-KR') : (+v).toFixed(2) }
</script>

<style scoped>
.g-gauge { grid-template-columns: 300px minmax(0, 1fr); }
.center { display: flex; flex-direction: column; align-items: center; text-align: center; }
.big { font-size: 40px; font-weight: 800; line-height: 1; margin: -6px 0 6px; font-variant-numeric: tabular-nums; }
.ind .v { font-size: 18px; font-weight: 700; font-variant-numeric: tabular-nums; margin: 4px 0; }
.bar { height: 8px; background: var(--panel-2); border-radius: 4px; overflow: hidden; } .bar i { display: block; height: 100%; background: var(--accent); }
@media (max-width: 900px) { .g-gauge { grid-template-columns: 1fr; } }
</style>
