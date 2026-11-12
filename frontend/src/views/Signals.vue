<template>
  <div>
    <div class="page-h"><div><h1>매매신호</h1>
      <div class="muted small">전 종목에 신호 전략 {{ d?.strategies.length || 15 }}개를 매일 적용합니다. 과거 {{ d?.summary ? num(d.summary.simulations) : '-' }}건의 신호 발생 이후 성과를 함께 보여 줍니다.</div></div>
      <div class="row wrap">
        <div class="seg"><button v-for="s in [['', '전체'], ['buy', '매수'], ['sell', '매도']]" :key="s[0]" :class="{ on: side === s[0] }" @click="side = s[0]">{{ s[1] }}</button></div>
        <div class="seg"><button v-for="m in [['', '전체'], ['KR', '국내'], ['US', '미국'], ['CR', '코인']]" :key="m[0]" :class="{ on: mk === m[0] }" @click="mk = m[0]">{{ m[1] }}</button></div>
        <select aria-label="전략" v-model="strategy"><option value="">모든 전략</option><option v-for="s in d?.strategies || []" :key="s.key" :value="s.key">{{ s.name }}</option></select>
      </div></div>
    <ValidationNote kind="signals" style="margin-bottom:12px" />
    <div class="card" style="margin-bottom:12px" v-if="d?.summary">
      <h3>전략별 과거 성과 (신호 후 10거래일, 전 종목, 시장 평균과 비교하지 않은 단순 수익률)</h3>
      <div class="scroll-x"><table class="t"><thead><tr><th>전략</th><th>조건</th><th class="num">과거 발생</th><th class="num">평균 수익</th><th class="num">적중률</th></tr></thead>
        <tbody><tr v-for="s in d.strategies" :key="s.key" class="click" @click="strategy = s.key">
          <td class="nowrap"><span class="chip" :class="s.side === 'buy' ? 'red' : 'bluedown'">{{ s.side === 'buy' ? '매수' : '매도' }}</span> {{ s.name }}</td>
          <td class="small muted">{{ s.conds.join(' · ') }}</td>
          <td class="num">{{ num(d.summary.strategies[s.key]?.n) }}</td>
          <td class="num" :class="cls(d.summary.strategies[s.key]?.avg10)">{{ pct(d.summary.strategies[s.key]?.avg10) }}</td>
          <td class="num">{{ d.summary.strategies[s.key]?.win10 ?? '-' }}%</td></tr></tbody></table></div>
    </div>
    <div class="card flush">
      <div style="padding:12px 12px 0" class="row between"><h3>최근 3거래일 신호 {{ d ? `(${d.rows.length})` : '' }}</h3><span class="tiny faint">이 종목에서 같은 신호가 났을 때의 이후 20일 성과</span></div>
      <Loading v-if="!d" />
      <div v-else class="scroll-x"><table class="t">
        <thead><tr><th>신호일</th><th>종목</th><th>전략</th><th class="num">신호가</th><th class="num">현재가</th><th class="num">이후</th><th class="num">이 종목 과거 발생</th><th class="num" title="검증상 다음 성과를 예측하지 못함">20일 평균 (참고)</th><th class="num" title="검증상 다음 성과를 예측하지 못함">20일 적중률 (참고)</th></tr></thead>
        <tbody>
          <tr v-for="r in d.rows" :key="r.symbol + r.strategy + r.date" class="click" @click="$router.push('/stock/' + r.symbol + '?tab=analysis')">
            <td class="small">{{ barDate(r.date) }}</td><td><SymLink :symbol="r.symbol" :name="r.name" /></td>
            <td class="nowrap"><span class="chip" :class="r.side === 'buy' ? 'red' : 'bluedown'">{{ r.side === 'buy' ? '매수' : '매도' }}</span> {{ r.strategy_name }}</td>
            <td class="num">{{ price(r.sig_price, curOf(r.symbol)) }}</td><td class="num">{{ price(r.price, curOf(r.symbol)) }}</td>
            <td class="num" :class="cls(r.price / r.sig_price - 1)">{{ pct((r.price / r.sig_price - 1) * 100) }}</td>
            <td class="num">{{ r.stats['20']?.n ?? '-' }}</td>
            <td class="num" :class="cls(r.stats['20']?.avg)">{{ pct(r.stats['20']?.avg) }}</td>
            <td class="num">{{ r.stats['20']?.win == null ? '-' : r.stats['20'].win + '%' }}</td>
          </tr>
          <tr v-if="!d.rows.length"><td colspan="9" class="empty">신호가 없습니다. 일봉 수집 후 매일 자동으로 계산됩니다.</td></tr>
        </tbody></table></div>
    </div>
  </div>
</template>
<script setup>
import { ref, watch } from 'vue'
import SymLink from '../components/SymLink.vue'
import ValidationNote from '../components/ValidationNote.vue'
import { api } from '../lib/api'
import { barDate, cls, curOf, num, pct, price } from '../lib/fmt'
const side = ref(''); const mk = ref(''); const strategy = ref(''); const d = ref(null)
watch([side, mk, strategy], async () => { d.value = await api.get('/discover/signals', { side: side.value, market_: mk.value, strategy: strategy.value, limit: 400 }) }, { immediate: true })
</script>
