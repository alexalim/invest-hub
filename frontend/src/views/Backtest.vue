<template>
  <div>
    <div class="page-h"><div><h1>백테스팅</h1><div class="muted small">{{ mode === 'day' ? '보조지표 조건으로 매수·매도 규칙을 만들고 과거 일봉으로 검증합니다. 신호는 종가에 확정되고 다음 날 시가에 체결합니다.' : '5분봉으로 하루 안에 사고파는 단타 전략을 검증합니다. 다음 날로 넘기지 않고 장 마감 전에 모두 청산합니다.' }}</div></div>
      <div class="row wrap"><div class="seg"><button :class="{ on: mode === 'day' }" @click="mode = 'day'">일봉 (며칠~몇 주)</button><button :class="{ on: mode === 'intraday' }" @click="mode = 'intraday'">장중 단타 (5분봉)</button></div>
        <SavedSpecs v-if="mode === 'day'" kind="backtest" label="전략" :spec="spec" @load="s => Object.assign(spec, s)" /></div></div>
    <IntradayBacktest v-if="mode === 'intraday'" />
    <template v-else>
    <div class="grid g-side">
      <div class="card">
        <div class="row wrap" style="margin-bottom:12px">
          <SymbolSearch placeholder="종목 선택" style="width:260px" @select="s => { symbol = s.symbol; symName = s.name }" />
          <span v-if="symbol" class="chip blue">{{ symName || symbol }}</span>
        </div>
        <h3>매수 조건 <span class="small muted">— 모두 충족(AND)</span></h3>
        <CondBuilder v-model="spec.entry" />
        <h3 style="margin-top:14px">매도 조건 <span class="small muted">— 하나라도 충족(OR)</span></h3>
        <CondBuilder v-model="spec.exit" />
        <div class="row wrap" style="margin-top:14px">
          <label class="field">손절 (%)<input class="w90" type="number" step="any" v-model.number="spec.stop_loss" placeholder="없음" /></label>
          <label class="field">익절 (%)<input class="w90" type="number" step="any" v-model.number="spec.take_profit" placeholder="없음" /></label>
          <label class="field">최대 보유일<input class="w90" type="number" v-model.number="spec.max_hold" placeholder="없음" /></label>
          <label class="field">수수료 (%)<input class="w90" type="number" step="any" v-model.number="spec.fee_pct" /></label>
          <label class="field">매도세 (%)<input class="w90" type="number" step="any" v-model.number="spec.tax_pct" /></label>
          <label class="field">시작일<input type="date" v-model="startDate" /></label>
        </div>
        <div class="row" style="margin-top:14px"><button class="primary" :disabled="!symbol || busy" @click="run">{{ busy ? '계산 중…' : '백테스트 실행' }}</button></div>
      </div>
      <div class="card">
        <h3>예시 전략</h3>
        <div class="col">
          <button v-for="p in PRESETS" :key="p.name" class="sm" style="text-align:left" @click="loadPreset(p)">{{ p.name }}</button>
        </div>
        <div class="tiny faint" style="margin-top:10px">손절·익절은 장중 고가·저가가 닿으면 그 가격에 체결된 것으로 계산합니다. 매수는 전액 진입입니다.</div>
      </div>
    </div>

    <template v-if="res">
      <div class="grid g4" style="margin-top:12px">
        <div class="card stat"><span class="k">전략 수익률</span><span class="v" :class="cls(res.stats.total_return)">{{ pct(res.stats.total_return) }}</span><span class="tiny faint">같은 기간 보유만 했을 때 {{ pct(res.stats.buy_hold) }}</span></div>
        <div class="card stat"><span class="k">연환산 수익률 · 최대 낙폭</span><span class="v">{{ pct(res.stats.cagr) }} · <span class="down">{{ pct(res.stats.mdd) }}</span></span></div>
        <div class="card stat"><span class="k">거래 · 승률</span><span class="v">{{ res.stats.n_trades }}회 · {{ res.stats.win_rate }}%</span><span class="tiny faint">평균 이익 {{ pct(res.stats.avg_win) }} / 평균 손실 {{ pct(res.stats.avg_loss) }}</span></div>
        <div class="card stat"><span class="k">손익비 · 샤프 · 보유비중</span><span class="v">{{ res.stats.profit_factor ?? '-' }} · {{ res.stats.sharpe }} · {{ res.stats.exposure }}%</span><span class="tiny faint">평균 보유 {{ res.stats.avg_bars }}일</span></div>
      </div>
      <div class="card" style="margin-top:12px">
        <h3>{{ res.name }} — 매매 지점</h3>
        <PriceChart :candles="res.candles" :markers="markers" :height="420" />
      </div>
      <div class="grid g2" style="margin-top:12px">
        <div class="card"><h3>평가액 곡선 (시작 = 1)</h3><MiniChart :series="[{ values: res.equity.map(e => e[1]), color: 'var(--accent)' }]" :h="200" /></div>
        <div class="card flush" style="max-height:300px;overflow:auto"><table class="t">
          <thead><tr><th>매수일</th><th>매도일</th><th class="num">수익률</th><th class="num">보유</th><th>사유</th></tr></thead>
          <tbody><tr v-for="(t, i) in [...res.trades].reverse()" :key="i"><td class="small">{{ barDate(t.entry_ts) }}</td><td class="small">{{ barDate(t.exit_ts) }}</td>
            <td class="num" :class="cls(t.ret_pct)">{{ pct(t.ret_pct) }}</td><td class="num">{{ t.bars }}일</td><td class="small">{{ t.reason }}</td></tr>
            <tr v-if="!res.trades.length"><td colspan="5" class="empty">거래가 없었습니다</td></tr></tbody></table></div>
      </div>
      <div class="card" style="margin-top:12px">
        <div class="card-h"><h3>같은 전략을 여러 종목에</h3>
          <div class="row"><select aria-label="비교할 종목 묶음" v-model="multiSet"><option value="kospi">코스피 시총 상위 30</option><option value="kosdaq">코스닥 시총 상위 30</option><option value="us">미국 시총 상위 30</option><option value="watch">내 관심종목</option></select>
            <button :disabled="multiBusy" @click="runMulti">{{ multiBusy ? '계산 중…' : '비교' }}</button></div></div>
        <div v-if="multi" class="scroll-x"><table class="t">
          <thead><tr><th>종목</th><th class="num">수익률</th><th class="num">보유만 했을 때</th><th class="num">최대 낙폭</th><th class="num">거래</th><th class="num">승률</th><th class="num">손익비</th></tr></thead>
          <tbody><tr v-for="r in multi" :key="r.symbol" class="click" @click="symbol = r.symbol; symName = r.name; run()">
            <td>{{ r.name }}</td><td class="num" :class="cls(r.total_return)">{{ pct(r.total_return) }}</td><td class="num" :class="cls(r.buy_hold)">{{ pct(r.buy_hold) }}</td>
            <td class="num down">{{ pct(r.mdd) }}</td><td class="num">{{ r.n_trades }}</td><td class="num">{{ r.win_rate }}%</td><td class="num">{{ r.profit_factor ?? '-' }}</td></tr></tbody></table>
          <div class="small muted" style="margin-top:6px">평균 수익률 {{ pct(multi.reduce((a, r) => a + r.total_return, 0) / (multi.length || 1)) }} · 보유 대비 우세 {{ multi.filter(r => r.total_return > r.buy_hold).length }}/{{ multi.length }}</div></div>
      </div>
    </template>
    </template>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import CondBuilder from '../components/CondBuilder.vue'
import IntradayBacktest from '../components/IntradayBacktest.vue'
import MiniChart from '../components/MiniChart.vue'
import PriceChart from '../components/PriceChart.vue'
import SavedSpecs from '../components/SavedSpecs.vue'
import SymbolSearch from '../components/SymbolSearch.vue'
import { api } from '../lib/api'
import { barDate, cls, pct } from '../lib/fmt'

const route = useRoute()
const mode = ref(route.query.mode === 'intraday' ? 'intraday' : 'day')
const symbol = ref(route.query.symbol || 'KR:005930'); const symName = ref('')
const I = (ind, p = [], x = {}) => ({ ind, p, ...x })
const spec = reactive({ entry: [{ left: I('sma', [5]), op: 'cross_up', right: I('sma', [20]) }], exit: [{ left: I('sma', [5]), op: 'cross_down', right: I('sma', [20]) }],
  stop_loss: 7, take_profit: null, max_hold: null, fee_pct: 0.015, tax_pct: 0.18 })
const startDate = ref('')
const PRESETS = [
  { name: '골든크로스 매수 / 데드크로스 매도', entry: [{ left: I('sma', [5]), op: 'cross_up', right: I('sma', [20]) }], exit: [{ left: I('sma', [5]), op: 'cross_down', right: I('sma', [20]) }], stop_loss: 7 },
  { name: 'RSI 30 회복 매수 / 70 도달 매도', entry: [{ left: I('rsi', [14]), op: 'cross_up', right: { value: 30 } }], exit: [{ left: I('rsi', [14]), op: '>', right: { value: 70 } }], stop_loss: 10 },
  { name: '볼린저 하단 반등 / 중심선 매도', entry: [{ left: I('close'), op: 'cross_up', right: I('bb', [20, 2], { out: 'lower' }) }], exit: [{ left: I('close'), op: '>', right: I('bb', [20, 2], { out: 'mid' }) }], stop_loss: 8 },
  { name: '20일 신고가 돌파 / 10일 저가 이탈', entry: [{ left: I('close'), op: '>', right: I('highest', [20], { shift: 1 }) }], exit: [{ left: I('close'), op: '<', right: I('lowest', [10], { shift: 1 }) }] },
  { name: 'MACD 골든크로스 / 데드크로스', entry: [{ left: I('macd', [12, 26, 9], { out: 'macd' }), op: 'cross_up', right: I('macd', [12, 26, 9], { out: 'signal' }) }], exit: [{ left: I('macd', [12, 26, 9], { out: 'macd' }), op: 'cross_down', right: I('macd', [12, 26, 9], { out: 'signal' }) }] },
  { name: '추세 눌림목 (60일선 위, RSI 40 이하) / 익절 10%', entry: [{ left: I('close'), op: '>', right: I('sma', [60]) }, { left: I('rsi', [14]), op: '<', right: { value: 40 } }], exit: [], take_profit: 10, stop_loss: 6, max_hold: 30 },
]
function loadPreset(p) { spec.entry = JSON.parse(JSON.stringify(p.entry)); spec.exit = JSON.parse(JSON.stringify(p.exit)); spec.stop_loss = p.stop_loss ?? null; spec.take_profit = p.take_profit ?? null; spec.max_hold = p.max_hold ?? null }
const res = ref(null); const busy = ref(false)
function fullSpec() { return { ...spec, start: startDate.value ? Date.parse(startDate.value) / 1000 : 0 } }
async function run() { busy.value = true; try { res.value = await api.post('/discover/backtest', { symbol: symbol.value, spec: fullSpec() }) } finally { busy.value = false } }
const markers = computed(() => res.value ? res.value.trades.flatMap(t => [
  { time: t.entry_ts, position: 'belowBar', color: '#e0353c', shape: 'arrowUp', text: '매수' },
  { time: t.exit_ts, position: 'aboveBar', color: '#2366d1', shape: 'arrowDown', text: `${t.ret_pct > 0 ? '+' : ''}${t.ret_pct}%` }]) : [])

const multiSet = ref('kospi'); const multi = ref(null); const multiBusy = ref(false)
async function runMulti() {
  multiBusy.value = true
  try {
    let symbols
    if (multiSet.value === 'watch') symbols = (await api.get('/user/watchlist')).flatMap(g => g.items.map(i => i.symbol))
    else {
      const mk = { kospi: 'KOSPI', kosdaq: 'KOSDAQ', us: 'US' }[multiSet.value]
      symbols = (await api.get('/market/list', { market_: mk, sort: 'mcap', size: 30 })).rows.map(r => r.symbol)
    }
    multi.value = await api.post('/discover/backtest/multi', { symbols, spec: fullSpec() })
  } finally { multiBusy.value = false }
}
if (route.query.symbol) run()
</script>
