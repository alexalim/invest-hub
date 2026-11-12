<template>
  <div class="col" style="gap:12px">
    <IntradayValidation />
    <div class="grid g-side">
      <div class="card">
        <div class="row wrap" style="margin-bottom:12px">
          <SymbolSearch placeholder="국내 종목" style="width:260px" @select="s => { if (s.symbol.startsWith('KR:')) { symbol = s.symbol; symName = s.name } }" />
          <span v-if="symbol" class="chip blue">{{ symName || symbol }}</span>
          <span v-if="meta" class="small muted">5분봉 자료: {{ meta.status.symbols }}종목 · {{ meta.status.first }} ~ {{ meta.status.last }} ({{ meta.status.days }}거래일)</span>
        </div>
        <h3>매수 조건 <span class="small muted">— 모두 충족, 5분봉 기준, 다음 봉 시가에 진입</span></h3>
        <CondBuilder v-model="spec.entry" :indicators="meta?.indicators" intraday />
        <h3 style="margin-top:14px">매도 조건 <span class="small muted">— 하나라도 충족 (없으면 손절·익절·장 마감에만 청산)</span></h3>
        <CondBuilder v-model="spec.exit" :indicators="meta?.indicators" intraday />
        <div class="row wrap" style="margin-top:14px">
          <label class="field">손절 (%)<input class="w90" type="number" step="any" v-model.number="spec.stop_loss" placeholder="없음" /></label>
          <label class="field">익절 (%)<input class="w90" type="number" step="any" v-model.number="spec.take_profit" placeholder="없음" /></label>
          <label class="field">진입 시작 (봉 번호)<input class="w90" type="number" v-model.number="spec.first_bar" /></label>
          <label class="field">마지막 진입 (봉 번호)<input class="w90" type="number" v-model.number="spec.last_entry_bar" /></label>
          <label class="field">하루 최대 거래<input class="w60" type="number" min="1" v-model.number="spec.max_trades" /></label>
        </div>
        <div class="tiny faint" style="margin-top:4px">봉 번호: 0 = 09:00, 6 = 09:30, 12 = 10:00, 66 = 14:30. 마지막 봉(15:15) 종가에 무조건 청산하고, 비용 {{ meta?.cost ?? 0.23 }}%를 뺍니다.</div>
        <div class="row" style="margin-top:14px">
          <button class="primary" :disabled="!symbol || busy" @click="run">{{ busy ? '계산 중…' : '이 종목 백테스트' }}</button>
          <button :disabled="multiBusy" @click="runMulti">{{ multiBusy ? '계산 중…' : '저장된 모든 종목에 돌리기' }}</button>
        </div>
      </div>
      <div class="card">
        <h3>단타 전략 예시</h3>
        <div class="col">
          <button v-for="p in meta?.presets || []" :key="p.key" class="sm" style="text-align:left" :title="p.desc" @click="load(p)">{{ p.name }}</button>
        </div>
        <div class="tiny faint" style="margin-top:10px">손절·익절은 봉 안의 고가·저가로 판단하고, 한 봉에서 둘 다 닿으면 손절이 먼저 일어났다고 봅니다 (보수적).</div>
      </div>
    </div>

    <template v-if="res">
      <div class="grid g4">
        <div class="card stat"><span class="k">거래당 평균 (비용 뺀 뒤)</span><span class="v" :class="cls(res.stats.avg)">{{ res.stats.n_trades ? pct(res.stats.avg, 3) : '-' }}</span>
          <span class="tiny faint">같은 날 장 시작→마감 보유 {{ pct(res.stats.same_day_open_close, 3) }}</span></div>
        <div class="card stat"><span class="k">거래 · 이긴 비율</span><span class="v">{{ res.stats.n_trades }}회 · {{ res.stats.win_rate ?? '-' }}%</span>
          <span class="tiny faint">평균 이익 {{ pct(res.stats.avg_win, 2) }} / 손실 {{ pct(res.stats.avg_loss, 2) }}</span></div>
        <div class="card stat"><span class="k">누적 · 최대 낙폭</span><span class="v"><span :class="cls(res.stats.total)">{{ pct(res.stats.total) }}</span> · <span class="down">{{ pct(res.stats.mdd) }}</span></span>
          <span class="tiny faint">{{ res.days[0] }} ~ {{ res.days[1] }} ({{ res.days[2] }}거래일)</span></div>
        <div class="card stat"><span class="k">t값 · 95% 구간</span><span class="v">{{ res.stats.t_stat ?? '-' }}</span>
          <span class="tiny faint">{{ res.stats.ci95 ? `평균이 ${pct(res.stats.ci95[0], 2)} ~ ${pct(res.stats.ci95[1], 2)} 사이` : '거래가 너무 적음' }}</span></div>
      </div>
      <div v-if="res.stats.n_trades && res.stats.n_trades < 30" class="notice warn small">거래가 {{ res.stats.n_trades }}회뿐이라 결과를 믿기 어렵습니다. "저장된 모든 종목에 돌리기"로 표본을 늘려 보세요.</div>
      <div class="card">
        <h3>{{ res.name }} — 5분봉과 매매 지점</h3>
        <PriceChart :candles="res.candles" :markers="markers" :height="420" intraday :show-volume="true" />
      </div>
      <div class="card flush" style="max-height:340px;overflow:auto"><table class="t">
        <thead><tr><th>진입</th><th>청산</th><th class="num">진입가</th><th class="num">청산가</th><th class="num">수익(비용 뺀)</th><th>사유</th></tr></thead>
        <tbody><tr v-for="(t, i) in [...res.trades].reverse()" :key="i"><td class="small">{{ tstr(t.entry_ts) }}</td><td class="small">{{ tstr(t.exit_ts).slice(11) }}</td>
          <td class="num">{{ price(t.entry_price) }}</td><td class="num">{{ price(t.exit_price) }}</td><td class="num" :class="cls(t.ret_pct)">{{ pct(t.ret_pct) }}</td><td class="small">{{ t.reason }}</td></tr>
          <tr v-if="!res.trades.length"><td colspan="6" class="empty">거래가 없었습니다</td></tr></tbody></table></div>
    </template>

    <div v-if="multi" class="card">
      <h3>저장된 {{ multi.rows.length }}종목 합산</h3>
      <div class="grid g4" style="margin-bottom:10px">
        <div class="stat"><span class="k">전체 거래</span><span class="v">{{ num(multi.total.n_trades) }}회</span></div>
        <div class="stat"><span class="k">거래당 평균 (비용 뺀)</span><span class="v" :class="cls(multi.total.avg)">{{ pct(multi.total.avg, 3) }}</span></div>
        <div class="stat"><span class="k">이긴 비율</span><span class="v">{{ multi.total.win_rate }}%</span></div>
        <div class="stat"><span class="k">t값 (거래 기준)</span><span class="v">{{ multi.total.t_stat }}</span></div>
      </div>
      <div class="tiny faint" style="margin-bottom:6px">같은 날 여러 종목이 함께 움직여 거래들이 서로 독립이 아니므로, 거래 기준 t값은 실제보다 부풀려집니다. 위 검증 표의 '날짜 기준 t값'을 함께 보세요.</div>
      <div class="scroll-x" style="max-height:320px;overflow:auto"><table class="t">
        <thead><tr><th>종목</th><th class="num">거래</th><th class="num">평균</th><th class="num">이긴 비율</th><th class="num">누적</th></tr></thead>
        <tbody><tr v-for="r in multi.rows" :key="r.symbol" class="click" @click="symbol = r.symbol; symName = r.name; run()">
          <td>{{ r.name }}</td><td class="num">{{ r.n_trades }}</td><td class="num" :class="cls(r.avg)">{{ pct(r.avg, 3) }}</td><td class="num">{{ r.win_rate }}%</td><td class="num" :class="cls(r.total)">{{ pct(r.total) }}</td></tr></tbody></table></div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import CondBuilder from './CondBuilder.vue'
import IntradayValidation from './IntradayValidation.vue'
import PriceChart from './PriceChart.vue'
import SymbolSearch from './SymbolSearch.vue'
import { api } from '../lib/api'
import { cls, num, pct, price } from '../lib/fmt'

const meta = ref(null)
const symbol = ref('KR:005930'); const symName = ref('삼성전자')
const spec = reactive({ entry: [], exit: [], stop_loss: 2, take_profit: null, first_bar: 6, last_entry_bar: 66, max_trades: 1 })
const res = ref(null); const busy = ref(false); const multi = ref(null); const multiBusy = ref(false)
api.get('/discover/intraday/meta').then(m => { meta.value = m; const p = m.presets.find(x => x.key === 'orb30'); if (p) load(p) })
function load(p) {
  const s = JSON.parse(JSON.stringify(p.spec))
  Object.assign(spec, { entry: s.entry || [], exit: s.exit || [], stop_loss: s.stop_loss ?? null, take_profit: s.take_profit ?? null,
    first_bar: s.first_bar ?? 0, last_entry_bar: s.last_entry_bar ?? 66, max_trades: s.max_trades ?? 1 })
}
async function run() { busy.value = true; try { res.value = await api.post('/discover/intraday/backtest', { symbol: symbol.value, spec }) } finally { busy.value = false } }
async function runMulti() { multiBusy.value = true; try { multi.value = await api.post('/discover/intraday/backtest/multi', { spec }) } finally { multiBusy.value = false } }
const markers = computed(() => res.value ? res.value.trades.flatMap(t => [
  { time: t.entry_ts, position: 'belowBar', color: '#e0353c', shape: 'arrowUp', text: '매수' },
  { time: t.exit_ts, position: 'aboveBar', color: '#2366d1', shape: 'arrowDown', text: `${t.ret_pct > 0 ? '+' : ''}${(+t.ret_pct).toFixed(2)}%` }]) : [])
function tstr(ts) { return new Date(ts * 1000).toISOString().slice(0, 16).replace('T', ' ') }
</script>
