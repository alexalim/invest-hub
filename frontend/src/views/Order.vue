<template>
  <div>
    <div class="page-h"><div><h1>모의 주문</h1><div class="muted small">모의계좌로 국내·미국 주식과 코인을 주문합니다. 국내 08~20시, 미국 정규장, 코인 24시간.</div></div>
      <SymbolSearch placeholder="주문할 종목 검색" style="width:300px;max-width:100%" @select="s => (symbol = s.symbol)" /></div>
    <div class="grid g-side">
      <div class="col" style="gap:12px">
        <div class="card" v-if="symbol">
          <div class="row between wrap"><div class="row"><h2 style="margin:0">{{ q[symbol]?.name || symbol }}</h2><router-link :to="'/stock/' + symbol" class="link small">종목 화면</router-link></div>
            <div class="num"><b style="font-size:18px">{{ price(q[symbol]?.price, curOf(symbol)) }}</b> <span :class="cls(q[symbol]?.change_pct)">{{ pct(q[symbol]?.change_pct) }}</span></div></div>
          <PriceChart :candles="candles" :height="300" :currency="curOf(symbol)" :intraday="true" />
        </div>
        <div class="card flush">
          <div style="padding:12px 12px 0" class="row between"><h3>보유 종목</h3><span class="small muted" v-if="acc">평가액 {{ won(acc.equity) }}원 · 수익률 <span :class="cls(acc.return_pct)">{{ pct(acc.return_pct) }}</span></span></div>
          <div class="scroll-x"><table class="t"><thead><tr><th>종목</th><th class="num">수량</th><th class="num">평단</th><th class="num">현재가</th><th class="num">평가손익</th><th class="num">수익률</th></tr></thead>
            <tbody><tr v-for="p in acc?.positions || []" :key="p.symbol" class="click" @click="symbol = p.symbol">
              <td class="nowrap">{{ p.name }}</td><td class="num">{{ num(p.qty, p.symbol.startsWith('CR:') ? 6 : 0) }}</td><td class="num">{{ price(p.avg_price, p.currency) }}</td><td class="num">{{ price(p.price, p.currency) }}</td>
              <td class="num" :class="cls(p.pnl_krw)">{{ won(p.pnl_krw) }}</td><td class="num" :class="cls(p.pnl_pct)">{{ pct(p.pnl_pct) }}</td></tr>
              <tr v-if="acc && !acc.positions.length"><td colspan="6" class="empty">보유 종목이 없습니다</td></tr></tbody></table></div>
        </div>
        <div class="card flush">
          <div style="padding:12px 12px 0"><h3>미체결 주문</h3></div>
          <div class="scroll-x"><table class="t"><thead><tr><th>종목</th><th>구분</th><th class="num">지정가</th><th class="num">수량</th><th>접수</th><th></th></tr></thead>
            <tbody><tr v-for="o in openOrders" :key="o.id"><td>{{ o.name }}</td><td :class="o.side === 'buy' ? 'up' : 'down'">{{ o.side === 'buy' ? '매수' : '매도' }}</td>
              <td class="num">{{ price(o.price, curOf(o.symbol)) }}</td><td class="num">{{ num(o.qty, 4) }}</td><td class="small">{{ datetime(o.created_at) }}</td>
              <td><button class="sm danger" @click="cancel(o)">취소</button></td></tr>
              <tr v-if="!openOrders.length"><td colspan="6" class="empty">미체결 주문이 없습니다</td></tr></tbody></table></div>
        </div>
      </div>
      <div class="col" style="gap:12px">
        <OrderPanel v-if="symbol" :symbol="symbol" @ordered="loadAcc" />
        <div v-else class="card empty">종목을 검색해 선택하세요</div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import OrderPanel from '../components/OrderPanel.vue'
import PriceChart from '../components/PriceChart.vue'
import SymbolSearch from '../components/SymbolSearch.vue'
import { api } from '../lib/api'
import { accountId, loadAccounts } from '../lib/accounts'
import { cls, curOf, datetime, num, pct, price, won } from '../lib/fmt'
import { useInterval, useQuotes } from '../lib/poll'
const route = useRoute()
const symbol = ref(route.query.symbol || 'KR:005930'); const candles = ref([]); const acc = ref(null)
const q = useQuotes(computed(() => [symbol.value]), 3000)
watch(symbol, async () => {
  const tf = symbol.value.startsWith('KR:') || symbol.value.startsWith('CR:') ? '5m' : 'day'
  candles.value = (await api.get(`/stock/${symbol.value}/candles`, { tf, count: 300 }, { quiet: true }).catch(() => ({ candles: [] }))).candles
}, { immediate: true })
async function loadAcc() { if (!accountId.value) await loadAccounts(); acc.value = await api.get(`/trade/accounts/${accountId.value}`, null, { quiet: true }).catch(() => acc.value) }
const openOrders = computed(() => (acc.value?.orders || []).filter(o => o.status === 'open'))
async function cancel(o) { await api.del(`/trade/orders/${o.id}`); loadAcc() }
watch(accountId, loadAcc); loadAcc(); useInterval(loadAcc, 6000)
</script>
