<template>
  <div>
    <div class="page-h"><div><h1>{{ part === 'short' ? '공매도·장중 가집계' : '프로그램 매매·업종별 수급' }}</h1><div class="muted small">한국투자증권 시세 조회로 받는 자료입니다. 단위는 억 원, +가 순매수입니다.</div></div>
      <MarketSeg /></div>
    <div v-if="unavailable" class="card empty">관리자가 실계좌 화면에서 한국투자증권 실전투자 키를 등록해야 볼 수 있습니다. 등록해도 이 화면은 시세 조회만 하며 주문은 하지 않습니다.</div>
    <template v-else>
      <template v-if="part === 'program'">
      <div v-if="bs && bs.basis != null" class="card row wrap" style="gap:22px;margin-bottom:12px">
        <div class="stat"><span class="k">코스피200 선물</span><span class="v">{{ num(bs.future, 2) }} <span class="small" :class="cls(bs.future_pct)">{{ pct(bs.future_pct) }}</span></span></div>
        <div class="stat"><span class="k">코스피200 현물</span><span class="v">{{ num(bs.spot, 2) }} <span class="small" :class="cls(bs.spot_pct)">{{ pct(bs.spot_pct) }}</span></span></div>
        <div class="stat"><span class="k">베이시스 (선물 − 현물)</span><span class="v" :class="cls(bs.basis)">{{ signed(bs.basis, 2) }}</span></div>
        <div class="small muted grow">베이시스가 음수면 선물이 현물보다 싸다는 뜻(백워데이션)이고, 이때 차익 프로그램 매도가 나오기 쉽습니다.</div>
      </div>
      <div class="grid g2">
        <div class="card">
          <div class="card-h"><h3>프로그램 매매 — 장중 누계 <span class="small muted">{{ md(pg?.tick_date) }}</span></h3>
            <span v-if="lastTick" class="small">전체 <b :class="cls(lastTick.total)">{{ signed(lastTick.total) }}</b></span></div>
          <Loading v-if="!pg" />
          <template v-else>
            <div class="legend"><span v-for="k in PKEYS" :key="k[0]" class="lg"><span class="dot" :style="{ background: k[2] }" />{{ k[1] }}
              <b v-if="lastTick" :class="cls(lastTick[k[0]])">{{ signed(lastTick[k[0]]) }}</b></span></div>
            <MiniChart v-if="pg.ticks.length > 1" :series="PKEYS.map(k => ({ name: k[1], values: pg.ticks.map(t => t[k[0]]), color: k[2] }))" :labels="pg.ticks.map(t => hm(t.hhmm))" :h="190" zero axis xaxis :fmt="eok" label="프로그램 매매 장중 누계" />
            <div v-else class="empty">정규장 중에 1분마다 쌓입니다</div>
            <div class="tiny faint" style="margin-top:6px">차익 = 선물과 현물의 가격 차이를 노린 매매 · 비차익 = 여러 종목을 한꺼번에 사고파는 바스켓 매매</div>
          </template>
        </div>
        <div class="card">
          <div class="card-h"><h3>프로그램 매매 — 일별 <span class="small muted">최근 {{ pg?.days?.length || 0 }}거래일</span></h3>
            <div class="seg"><button v-for="k in PKEYS" :key="k[0]" :class="{ on: pk === k[0] }" @click="pk = k[0]">{{ k[1] }}</button></div></div>
          <Loading v-if="!pg" />
          <template v-else>
            <MiniChart type="bar" :series="[{ values: pg.days.map(x => x[pk]), color: 'var(--up)' }]" :labels="pg.days.map(x => md(x.date))" :h="190" axis xaxis :fmt="eok" label="프로그램 매매 일별" />
            <div class="tiny faint" style="text-align:center">합계 <b :class="cls(pgSum)">{{ signed(pgSum) }}억</b></div>
          </template>
        </div>
      </div>

      <div class="card" style="margin-top:12px">
        <div class="card-h"><h3>업종별 수급 <span class="small muted">{{ sec?.at ? mdhm(sec.at) + ' 기준' : '' }}</span></h3>
          <div class="row wrap"><div class="seg"><button v-for="w in WHO" :key="w[0]" :class="{ on: who === w[0] }" @click="who = w[0]">{{ w[1] }}</button></div>
            <div class="seg"><button v-for="s in SPANS" :key="s[0]" :class="{ on: span === s[0] }" @click="span = s[0]">{{ s[1] }}</button></div></div></div>
        <Loading v-if="!sec" />
        <div v-else-if="!sec.rows.length" class="empty">아직 받지 못했습니다. 서버를 켠 뒤 1~2분 안에 채워집니다.</div>
        <div v-else class="scroll-x"><table class="t">
          <thead><tr><th>업종</th><th class="num">오늘 등락</th><th class="num">{{ whoLabel }} 순매수</th><th style="width:38%;min-width:120px"></th><th class="num">외국인</th><th class="num">기관</th><th class="num">개인</th></tr></thead>
          <tbody><tr v-for="r in secRows" :key="r.code">
            <td class="nowrap">{{ r.name }}</td><td class="num" :class="cls(r.change_pct)">{{ pct(r.change_pct) }}</td>
            <td class="num" :class="cls(r[who][span])"><b>{{ signed(r[who][span]) }}</b></td>
            <td><div class="hbar"><i :class="r[who][span] >= 0 ? 'pos' : 'neg'" :style="barStyle(r[who][span])" /></div></td>
            <td class="num" :class="cls(r.foreigner[span])">{{ signed(r.foreigner[span]) }}</td><td class="num" :class="cls(r.institution[span])">{{ signed(r.institution[span]) }}</td>
            <td class="num" :class="cls(r.individual[span])">{{ signed(r.individual[span]) }}</td></tr></tbody></table></div>
        <div class="tiny faint" style="margin-top:8px">1년 누적에서 크게 음수인 업종은 그 주체가 오래 팔아 온 곳, 크게 양수인 업종은 오래 사 온 곳입니다. 세 주체 합이 0이 아니면 나머지는 기타법인(자사주 매입 등)입니다.</div>
      </div>

      </template>

      <div v-else class="grid g2">
        <div class="card flush">
          <div class="card-h" style="padding:12px 12px 0"><h3>공매도 상위 <span class="small muted">직전 거래일까지</span></h3>
            <div class="seg"><button v-for="p in PERIODS" :key="p[0]" :class="{ on: period === p[0] }" @click="period = p[0]">{{ p[1] }}</button></div></div>
          <Loading v-if="!sh" />
          <div v-else class="scroll-x" style="max-height:520px;overflow-y:auto"><table class="t">
            <thead><tr><th>종목</th><th class="num">공매도(억)</th><th class="num">거래대금 중 비중</th><th class="num">현재가</th><th class="num">오늘</th></tr></thead>
            <tbody><tr v-for="r in sh.rows" :key="r.symbol" class="click" @click="$router.push('/stock/' + r.symbol)">
              <td><SymLink :symbol="r.symbol" :name="r.name" hide-code /></td><td class="num">{{ num(r.short_amount, 1) }}</td><td class="num"><b>{{ r.short_ratio.toFixed(1) }}%</b></td>
              <td class="num">{{ num(r.price) }}</td><td class="num" :class="cls(r.change_pct)">{{ pct(r.change_pct) }}</td></tr>
              <tr v-if="!sh.rows.length"><td colspan="5" class="empty">자료가 없습니다</td></tr></tbody></table></div>
        </div>
        <div class="card flush">
          <div class="card-h" style="padding:12px 12px 0"><h3>장중 가집계 <span class="small muted">오늘, 어림값</span></h3>
            <div class="row wrap"><div class="seg"><button v-for="w in PWHO" :key="w[0]" :class="{ on: pw === w[0] }" @click="pw = w[0]">{{ w[1] }}</button></div>
              <div class="seg"><button :class="{ on: side === 'buy' }" @click="side = 'buy'">순매수</button><button :class="{ on: side === 'sell' }" @click="side = 'sell'">순매도</button></div></div></div>
          <Loading v-if="!pr" />
          <div v-else class="scroll-x" style="max-height:520px;overflow-y:auto"><table class="t">
            <thead><tr><th>종목</th><th class="num">외국인(억)</th><th class="num">기관(억)</th><th class="num">현재가</th><th class="num">오늘</th></tr></thead>
            <tbody><tr v-for="r in pr.rows" :key="r.symbol" class="click" @click="$router.push('/stock/' + r.symbol)">
              <td><SymLink :symbol="r.symbol" :name="r.name" hide-code /></td><td class="num" :class="cls(r.foreigner)">{{ signed(r.foreigner) }}</td>
              <td class="num" :class="cls(r.institution)">{{ signed(r.institution) }}</td><td class="num">{{ num(r.price) }}</td><td class="num" :class="cls(r.change_pct)">{{ pct(r.change_pct) }}</td></tr>
              <tr v-if="!pr.rows.length"><td colspan="5" class="empty">자료가 없습니다</td></tr></tbody></table></div>
          <div class="tiny faint" style="padding:8px 12px">증권사가 장중에 하루 네 번쯤(9:30~14:30) 입력하는 어림 집계입니다. 확정치는 '투자자 수급' 화면에서 저녁에 볼 수 있습니다.</div>
        </div>
      </div>
      <div class="tiny faint" style="margin-top:10px">이 화면은 사실을 보여줄 뿐이며 매수·매도 판단의 근거가 되는지는 따로 검증하지 않았습니다.</div>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import MarketSeg from '../components/MarketSeg.vue'
import MiniChart from '../components/MiniChart.vue'
import SymLink from '../components/SymLink.vue'
import { api } from '../lib/api'
import { cls, hm, md, mdhm, num, pct, signed } from '../lib/fmt'
import { krMarket as mk } from '../lib/prefs'

const props = defineProps({ part: { type: String, default: 'program' } })
const eok = v => signed(Math.round(v)) + '억'

const PKEYS = [['total', '전체', '#0d9488'], ['arb', '차익', '#d99a1b'], ['nonarb', '비차익', '#8b5cf6']]
const WHO = [['foreigner', '외국인'], ['institution', '기관'], ['individual', '개인']]
const SPANS = [['1', '오늘'], ['5', '5일'], ['20', '20일'], ['250', '1년']]
const PERIODS = [['0', '1일'], ['4', '1주'], ['9', '2주']]
const PWHO = [['foreign', '외국인'], ['organ', '기관']]
const pk = ref('total'); const who = ref('foreigner'); const span = ref('1'); const period = ref('0'); const pw = ref('foreign'); const side = ref('buy')
const bs = ref(null); const pg = ref(null); const sec = ref(null); const sh = ref(null); const pr = ref(null); const unavailable = ref(false)
function take(target) { return r => { if (r.available === false) unavailable.value = true; else target.value = r } }
function loadMain(quiet) {
  if (!quiet) { pg.value = null; sec.value = null }
  api.get('/pulse/program', { market_: mk.value }, { quiet }).then(take(pg)).catch(() => { if (!quiet) pg.value = { ticks: [], days: [] } })
  api.get('/pulse/basis', null, { quiet: true }).then(r => (bs.value = r)).catch(() => {})
  api.get('/pulse/sectors', { market_: mk.value }, { quiet }).then(take(sec)).catch(() => {})
}
// 탭마다 그 탭에 필요한 자료만 받는다
if (props.part === 'program') watch(mk, () => loadMain(false), { immediate: true })
if (props.part === 'short') watch([mk, period], () => { sh.value = null; api.get('/pulse/short', { market_: mk.value, period: period.value }).then(take(sh)).catch(() => { sh.value = { rows: [] } }) }, { immediate: true })
if (props.part === 'short') watch([mk, pw, side], () => { pr.value = null; api.get('/pulse/prelim', { market_: mk.value, who: pw.value, side: side.value }).then(take(pr)).catch(() => { pr.value = { rows: [] } }) }, { immediate: true })
const timer = props.part === 'program' ? setInterval(() => loadMain(true), 60000) : 0
onBeforeUnmount(() => clearInterval(timer))

const lastTick = computed(() => pg.value?.ticks?.[pg.value.ticks.length - 1])
const pgSum = computed(() => Math.round((pg.value?.days || []).reduce((a, x) => a + x[pk.value], 0)))
const whoLabel = computed(() => WHO.find(w => w[0] === who.value)[1])
const secRows = computed(() => [...sec.value.rows].sort((a, b) => b[who.value][span.value] - a[who.value][span.value]))
const secMax = computed(() => Math.max(1, ...sec.value.rows.map(r => Math.abs(r[who.value][span.value]))))
function barStyle(v) { const w = Math.abs(v) / secMax.value * 50; return v >= 0 ? { left: '50%', width: w + '%' } : { left: 50 - w + '%', width: w + '%' } }
</script>

<style scoped>
.hbar { position: relative; height: 10px; background: var(--panel-2); border-radius: 5px; overflow: hidden; }
.hbar::after { content: ''; position: absolute; left: 50%; top: 0; bottom: 0; width: 1px; background: var(--line); }
.hbar i { position: absolute; top: 0; bottom: 0; } .hbar i.pos { background: var(--up); } .hbar i.neg { background: var(--down); }
</style>
