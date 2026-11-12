<template>
  <div>
    <div class="page-h"><div><h1>투자자 수급</h1><div class="muted small">개인·외국인·기관이 오늘, 그리고 최근에 얼마나 사고팔았는지 봅니다. 단위는 억 원, +가 순매수입니다.</div></div>
      <MarketSeg /></div>
    <Loading v-if="!d" />
    <template v-else>
      <div class="grid g-side top">
        <div class="card">
          <div class="card-h"><h3>장중 누적 순매수 <span class="small muted">{{ md(d.tick_date) }}</span></h3>
            <span v-if="d.live" class="chip red">장중 · 1분마다 갱신</span><span v-else class="chip">장 마감</span></div>
          <div class="legend">
            <label v-for="k in LINE_KEYS" :key="k" class="lg"><input type="checkbox" v-model="shown" :value="k" />
              <span class="dot" :style="{ background: COLOR[k] }" />{{ label(k) }}
              <b v-if="lastTick" :class="cls(lastTick[k])">{{ signed(lastTick[k]) }}</b></label>
          </div>
          <MiniChart v-if="d.ticks.length > 1" :series="tickSeries" :labels="d.ticks.map(t => hm(t.ts))" :h="260" zero axis xaxis :fmt="eok" label="장중 누적 순매수" />
          <div v-else class="empty">장중 기록은 서버가 켜져 있는 동안 정규장(9:00~15:45)에 1분마다 쌓입니다.<br>아직 {{ d.ticks.length }}개라 선을 그릴 수 없습니다.</div>
        </div>
        <div class="card flush">
          <div style="padding:12px 12px 0"><h3>주체별 순매수</h3><div class="tiny faint">오늘 · 최근 5일 · 최근 20일 합계</div></div>
          <table class="t"><thead><tr><th>주체</th><th class="num">{{ md(d.latest?.date) }}</th><th class="num">5일</th><th class="num">20일</th></tr></thead>
            <tbody><tr v-for="k in ALL_KEYS" :key="k" :class="{ sub: !MAIN.includes(k) }">
              <td>{{ label(k) }}</td><td class="num" :class="cls(d.latest?.[k])">{{ signed(d.latest?.[k]) }}</td>
              <td class="num" :class="cls(d.sums['5'][k])">{{ signed(d.sums['5'][k]) }}</td>
              <td class="num" :class="cls(d.sums['20'][k])">{{ signed(d.sums['20'][k]) }}</td></tr></tbody></table>
        </div>
      </div>

      <div class="card" style="margin-top:12px">
        <div class="card-h"><h3>일별 순매수와 누적</h3>
          <div class="row wrap"><select v-model="who" aria-label="투자 주체"><option v-for="k in ALL_KEYS" :key="k" :value="k">{{ label(k) }}</option></select>
            <div class="seg"><button v-for="n in SPANS" :key="n" :class="{ on: days === n }" @click="days = n">{{ n }}일</button></div></div></div>
        <div class="small muted">막대 = 하루 순매수 · 아래 선 = 이 구간 누적(파랑, 왼쪽 눈금)과 {{ mkName }} 지수(회색, 오른쪽 눈금)</div>
        <MiniChart type="bar" :series="[{ values: daily, color: 'var(--up)' }]" :labels="dayLabels" :h="170" axis :fmt="eok" label="일별 순매수" />
        <MiniChart style="margin-top:4px" :series="[{ name: '누적', values: cumulative, color: 'var(--accent)' }, { name: mkName, values: closes, color: 'var(--faint)', width: 1.2, axis: 'right', fmt: v => num(v, 2) }]"
          :labels="dayLabels" :h="150" zero axis xaxis :fmt="eok" label="누적 순매수와 지수" />
        <div class="tiny faint" style="text-align:center">구간 합계 <b :class="cls(total)">{{ signed(total) }}억</b></div>
      </div>

      <div class="card" style="margin-top:12px">
        <div class="card-h"><h3>많이 사고판 종목 <span class="small muted">시가총액 상위 200종목 안에서</span></h3>
          <div class="row wrap"><div class="seg"><button v-for="w in WHO" :key="w[0]" :class="{ on: sw === w[0] }" @click="sw = w[0]">{{ w[1] }}</button></div>
            <div class="seg"><button v-for="n in [1, 5, 20]" :key="n" :class="{ on: span === n }" @click="span = n">{{ n }}일</button></div></div></div>
        <Loading v-if="!st" />
        <div v-else-if="!st.dates.length" class="empty">아직 받지 못했습니다. 서버를 켠 뒤 몇 분 안에 채워집니다.</div>
        <template v-else>
          <div class="grid g2">
            <div v-for="side in SIDES" :key="side[0]" class="scroll-x">
              <table class="t"><thead><tr><th>{{ side[1] }}</th><th class="num">금액(억)</th><th class="num">현재가</th><th class="num">등락</th><th class="num">외국인 지분</th></tr></thead>
                <tbody><tr v-for="r in st[side[0]]" :key="r.symbol" class="click" @click="$router.push('/stock/' + r.symbol)">
                  <td><SymLink :symbol="r.symbol" :name="r.name" hide-code /></td><td class="num" :class="cls(r.amount)">{{ signed(r.amount) }}</td>
                  <td class="num">{{ num(r.price) }}</td><td class="num" :class="cls(r.change_pct)">{{ pct(r.change_pct) }}</td>
                  <td class="num">{{ r.foreign_hold == null ? '-' : r.foreign_hold.toFixed(1) + '%' }}</td></tr>
                  <tr v-if="!st[side[0]].length"><td colspan="5" class="empty">해당 종목이 없습니다</td></tr></tbody></table>
            </div>
          </div>
          <div class="tiny faint" style="margin-top:8px">{{ md(st.dates[st.dates.length - 1]) }}{{ st.dates.length > 1 ? ' ~ ' + md(st.dates[0]) : '' }} 확정치 기준. 금액은 순매수 수량 × 그날 종가로 어림한 값이라 실제 체결 금액과 조금 다릅니다. 당일 값은 저녁에 올라옵니다.</div>
        </template>
      </div>
      <div class="tiny faint" style="margin-top:10px">출처: 다음 금융(시장 전체), 네이버 증권(종목별). 이 화면은 사실을 보여줄 뿐이며 매수·매도 판단의 근거가 되는지는 따로 검증하지 않았습니다.</div>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import MarketSeg from '../components/MarketSeg.vue'
import MiniChart from '../components/MiniChart.vue'
import SymLink from '../components/SymLink.vue'
import { api } from '../lib/api'
import { cls, hm, md, num, pct, signed } from '../lib/fmt'
import { krMarket as mk } from '../lib/prefs'

const MAIN = ['individual', 'foreigner', 'institution']
const NAMES = { individual: '개인', foreigner: '외국인', institution: '기관 합계' }
// 빨강·파랑은 등락(상승·하락)에만 쓰므로 주체 색에서는 뺐다
const COLOR = { individual: '#d99a1b', foreigner: '#8b5cf6', institution: '#0d9488', fin: '#db2777', pension: '#65a30d', trust: '#0891b2', corp: '#6b7280' }
const LINE_KEYS = ['individual', 'foreigner', 'institution', 'fin', 'pension', 'trust', 'corp']
const SPANS = [20, 60, 120, 250]
const WHO = [['foreign', '외국인'], ['organ', '기관'], ['individual', '개인']]
const SIDES = [['buy', '순매수 상위'], ['sell', '순매도 상위']]

const days = ref(60); const who = ref('foreigner'); const d = ref(null)
const shown = ref([...MAIN]); const sw = ref('foreign'); const span = ref(1); const st = ref(null)
function label(k) { return NAMES[k] || d.value?.names?.[k] || k }
const ALL_KEYS = computed(() => [...MAIN, ...Object.keys(d.value?.names || {})])
const eok = v => signed(Math.round(v)) + '억'
const mkName = computed(() => mk.value === 'KOSPI' ? '코스피' : '코스닥')
const dayLabels = computed(() => d.value.days.map(x => md(x.date)))

async function load(quiet) {
  if (!quiet) d.value = null
  d.value = await api.get('/pulse/flow', { market_: mk.value, days: days.value }, { quiet })
}
watch([mk, days], () => load(false), { immediate: true })
watch([sw, span], async () => { st.value = null; st.value = await api.get('/pulse/flow/stocks', { who: sw.value, span: span.value, limit: 15 }) }, { immediate: true })
const timer = setInterval(() => { if (d.value?.live) load(true).catch(() => {}) }, 60000)
onBeforeUnmount(() => clearInterval(timer))

const lastTick = computed(() => d.value.ticks[d.value.ticks.length - 1] || d.value.latest)
const tickSeries = computed(() => LINE_KEYS.filter(k => shown.value.includes(k)).map(k => ({ name: label(k), values: d.value.ticks.map(t => t[k] ?? null), color: COLOR[k], width: MAIN.includes(k) ? 2 : 1.3 })))
const daily = computed(() => d.value.days.map(x => x[who.value] ?? 0))
const cumulative = computed(() => { let s = 0; return daily.value.map(v => (s += v)) })
const total = computed(() => Math.round(daily.value.reduce((a, b) => a + b, 0)))
const closes = computed(() => d.value.days.map(x => x.close ?? null))
</script>

<style scoped>
.g-side.top { align-items: start; }
tr.sub td:first-child { padding-left: 18px; color: var(--muted); }
</style>
