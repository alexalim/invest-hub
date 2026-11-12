<template>
  <div class="col" style="gap:12px">
    <div class="card">
      <div class="card-h"><h3>그때 샀더라면 / 팔았더라면</h3><span class="small muted">차트를 클릭하면 사는 날 → 파는 날 순서로 찍힙니다</span></div>
      <div class="row wrap">
        <label class="field">사는 날<input type="date" v-model="buy" :max="today" /></label>
        <label class="field">파는 날 <span class="faint">(비우면 오늘)</span><input type="date" v-model="sell" :max="today" /></label>
        <label class="field">투자 금액 ({{ currency === 'USD' ? '달러' : '원' }})<NumInput v-model="amount" class="w120" :decimals="currency === 'USD'" /></label>
        <div class="row" style="align-self:flex-end">
          <button v-for="p in PRESETS" :key="p[0]" class="sm" @click="preset(p[1])">{{ p[0] }}</button>
        </div>
      </div>
      <PriceChart ref="chartRef" :candles="candles" :markers="markers" :height="340" :currency="currency" :line="line" style="margin-top:10px" @click="onClick" />
      <div class="tiny faint">사는 날·파는 날 모두 그날 종가로 계산합니다. 휴장일을 고르면 사는 날은 다음 거래일, 파는 날은 직전 거래일로 맞춥니다.</div>
    </div>

    <div v-if="err" class="card empty">{{ err }}</div>
    <template v-else-if="r">
      <div class="grid g4">
        <div class="card stat"><span class="k">수익률 (수수료·세금 뺀 뒤)</span><span class="v" :class="cls(r.ret_pct)">{{ pct(r.ret_pct) }}</span>
          <span class="tiny faint">가격만 보면 {{ pct(r.price_ret_pct) }}</span></div>
        <div class="card stat"><span class="k">손익</span><span class="v" :class="cls(r.pnl)">{{ money(r.pnl, true) }}</span>
          <span class="tiny faint">{{ money(r.cost) }} → {{ money(r.proceeds) }}</span></div>
        <div class="card stat"><span class="k">보유 기간 · 연환산</span><span class="v">{{ num(r.days) }}일</span>
          <span class="tiny faint">{{ r.cagr_pct == null ? '30일 미만은 연환산 생략' : '연 ' + pct(r.cagr_pct) }}</span></div>
        <div class="card stat"><span class="k">{{ r.bench ? r.bench.name + '에 넣었다면' : '비교 지수' }}</span>
          <span class="v" :class="cls(r.bench?.ret_pct)">{{ r.bench ? pct(r.bench.ret_pct) : '-' }}</span>
          <span v-if="r.bench" class="tiny" :class="cls(r.price_ret_pct - r.bench.ret_pct)">지수보다 {{ pct(r.price_ret_pct - r.bench.ret_pct) }}p</span></div>
      </div>
      <div class="card">
        <dl class="kv">
          <dt>산 날 · 가격</dt><dd>{{ barDate(r.buy_ts) }} · {{ price(r.buy_price, currency) }}</dd>
          <dt>판 날 · 가격</dt><dd>{{ barDate(r.sell_ts) }}{{ r.sell_is_today ? ' (오늘)' : '' }} · {{ price(r.sell_price, currency) }}</dd>
          <dt>수량</dt><dd>{{ num(r.qty, currency === 'KRW' && !isCrypto ? 0 : 4) }}{{ isCrypto ? '' : '주' }}</dd>
          <dt>수수료·세금</dt><dd>{{ money(r.fees) }}</dd>
          <dt>보유 중 가장 쌌던 때</dt><dd>{{ barDate(r.low.ts) }} · {{ price(r.low.price, currency) }} <span class="down">({{ pct((r.low.price / r.buy_price - 1) * 100) }})</span></dd>
          <dt>보유 중 가장 비쌌던 때</dt><dd>{{ barDate(r.high.ts) }} · {{ price(r.high.price, currency) }} <span class="up">({{ pct((r.high.price / r.buy_price - 1) * 100) }})</span></dd>
          <dt>최대 낙폭</dt><dd class="down">{{ pct(r.mdd_pct) }}</dd>
          <dt>이 기간 최고의 매수·매도</dt><dd>{{ barDate(r.best.buy_ts) }} 사서 {{ barDate(r.best.sell_ts) }} 팔았다면 <span class="up">{{ pct(r.best.ret_pct) }}</span></dd>
        </dl>
        <div class="tiny faint" style="margin-top:8px">배당은 포함하지 않습니다 (배당이 많은 종목은 실제보다 낮게 나옵니다). 액면분할은 가격 자료에 반영돼 있습니다.{{ currency === 'USD' ? ' 환율 변동은 반영하지 않은 달러 기준입니다.' : '' }}</div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import NumInput from './NumInput.vue'
import PriceChart from './PriceChart.vue'
import { api } from '../lib/api'
import { barDate, cls, curOf, num, pct, price, won } from '../lib/fmt'

const props = defineProps({ symbol: String, line: Boolean })
const currency = computed(() => curOf(props.symbol))
const isCrypto = computed(() => props.symbol.startsWith('CR:'))
const today = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10)
const ago = days => new Date(Date.now() + 9 * 3600e3 - days * 86400e3).toISOString().slice(0, 10)
const PRESETS = [['1개월 전', 30], ['6개월 전', 182], ['1년 전', 365], ['3년 전', 1095]]
const buy = ref(ago(365)); const sell = ref(''); const amount = ref(currency.value === 'USD' ? 10000 : 10_000_000)
const candles = ref([]); const r = ref(null); const err = ref(''); const chartRef = ref(null)
let clickStep = 0

api.get(`/stock/${props.symbol}/candles`, { tf: 'day', count: 1500 }, { quiet: true }).then(x => (candles.value = x.candles)).catch(() => {})
function preset(d) { buy.value = ago(d); sell.value = '' }
function onClick({ time }) {
  if (!time) return
  const d = barDate(time)
  if (clickStep === 0) { buy.value = d; sell.value = ''; clickStep = 1 } else { if (d > buy.value) sell.value = d; else buy.value = d; clickStep = 0 }
}
let t
async function calc() {
  err.value = ''
  if (!buy.value || !amount.value) return
  try {
    r.value = await api.get(`/stock/${props.symbol}/whatif`, { buy: buy.value, sell: sell.value, amount: amount.value }, { quiet: true })
    setTimeout(() => chartRef.value?.showRange(r.value.buy_ts, r.value.sell_ts), 50)
  }
  catch (e) { err.value = e.message; r.value = null }
}
watch([buy, sell, amount], () => { clearTimeout(t); t = setTimeout(calc, 250) }, { immediate: true })
const markers = computed(() => r.value ? [
  { time: r.value.buy_ts, position: 'belowBar', color: '#e0353c', shape: 'arrowUp', text: '샀다면' },
  { time: r.value.sell_ts, position: 'aboveBar', color: '#2366d1', shape: 'arrowDown', text: r.value.sell_is_today ? '오늘' : '팔았다면' },
  ...(r.value.best.buy_ts !== r.value.buy_ts ? [{ time: r.value.best.buy_ts, position: 'belowBar', color: '#f59e0b', shape: 'circle', text: '최저점' }] : []),
  ...(r.value.best.sell_ts !== r.value.sell_ts ? [{ time: r.value.best.sell_ts, position: 'aboveBar', color: '#f59e0b', shape: 'circle', text: '최고점' }] : []),
] : [])
function money(v, sign = false) {
  if (v == null) return '-'
  const s = sign && v > 0 ? '+' : ''
  return currency.value === 'USD' ? `${s}$${num(v, 2)}` : `${s}${won(v)}원`
}
</script>
