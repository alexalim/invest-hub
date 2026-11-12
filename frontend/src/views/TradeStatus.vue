<template>
  <div>
    <div class="page-h"><div><h1>투자현황</h1><div class="muted small">모의계좌 평가액·보유 종목·주문·체결 내역</div></div>
      <div class="row wrap">
        <select aria-label="모의계좌 선택" :value="accountId" @change="selectAccount(+$event.target.value)"><option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.name }}</option></select>
        <button class="sm" @click="newOpen = true" :disabled="accounts.length >= 5">+ 계좌</button>
        <button class="sm" @click="reset">초기화</button>
        <button class="sm danger" v-if="accounts.length > 1" @click="removeAcc">삭제</button>
      </div></div>
    <Loading v-if="!acc" />
    <template v-else>
      <div class="grid g4">
        <div class="card stat"><span class="k">총 평가액</span><span class="v">{{ won(acc.equity) }}원</span><span class="tiny faint">시작 {{ won(acc.initial) }}원</span></div>
        <div class="card stat"><span class="k">총 수익률</span><span class="v" :class="cls(acc.return_pct)">{{ pct(acc.return_pct) }}</span><span class="tiny" :class="cls(acc.pnl)">{{ won(acc.pnl) }}원</span></div>
        <div class="card stat"><span class="k">실현 손익</span><span class="v" :class="cls(acc.realized)">{{ won(acc.realized) }}원</span></div>
        <div class="card stat"><span class="k">현금 · 주문 가능</span><span class="v">{{ won(acc.cash) }}원</span><span class="tiny faint">주문 가능 {{ won(acc.available) }}원 · 달러 {{ num(acc.usdkrw, 1) }}원</span></div>
      </div>
      <div class="grid g2" style="margin-top:12px">
        <div class="card"><h3>평가액 추이</h3>
          <MiniChart v-if="acc.equity_curve.length > 1" :series="[{ values: acc.equity_curve.map(e => e.equity), color: 'var(--accent)' }]" :h="180" />
          <div v-else class="empty small">하루 이상 지나면 그래프가 그려집니다 (30분마다 기록)</div></div>
        <div class="card"><h3>자산 구성</h3>
          <div v-for="s in allocation" :key="s.name" class="row small" style="padding:3px 0"><span class="grow ellipsis">{{ s.name }}</span>
            <div class="bar-bg" style="width:45%"><div class="bar-fg" :style="{ width: s.pct + '%' }" /></div><span class="num" style="width:56px">{{ num(s.pct, 1) }}%</span></div></div>
      </div>
      <div class="card flush" style="margin-top:12px">
        <div style="padding:12px 12px 0"><h3>보유 종목 ({{ acc.positions.length }})</h3></div>
        <div class="scroll-x"><table class="t"><thead><tr><th>종목</th><th class="num">수량</th><th class="num">평단</th><th class="num">현재가</th><th class="num">오늘</th><th class="num">평가금액</th><th class="num">평가손익</th><th class="num">수익률</th><th></th></tr></thead>
          <tbody><tr v-for="p in acc.positions" :key="p.symbol" class="click" @click="$router.push('/stock/' + p.symbol)">
            <td><SymLink :symbol="p.symbol" :name="p.name" /></td><td class="num">{{ num(p.qty, p.symbol.startsWith('CR:') ? 6 : 0) }}</td><td class="num">{{ price(p.avg_price, p.currency) }}</td>
            <td class="num">{{ price(p.price, p.currency) }}</td><td class="num" :class="cls(p.change_pct)">{{ pct(p.change_pct) }}</td><td class="num">{{ won(p.value_krw) }}</td>
            <td class="num" :class="cls(p.pnl_krw)">{{ won(p.pnl_krw) }}</td><td class="num" :class="cls(p.pnl_pct)">{{ pct(p.pnl_pct) }}</td>
            <td @click.stop><router-link :to="{ path: '/trade/order', query: { symbol: p.symbol } }" class="btn sm">주문</router-link></td></tr>
            <tr v-if="!acc.positions.length"><td colspan="9" class="empty">보유 종목이 없습니다. <router-link to="/trade/order" class="link">주문하러 가기</router-link></td></tr></tbody></table></div>
      </div>
      <div class="grid g2" style="margin-top:12px">
        <div class="card flush" style="max-height:420px;overflow:auto"><div style="padding:12px 12px 0"><h3>주문 내역</h3></div>
          <table class="t"><thead><tr><th>시각</th><th>종목</th><th>구분</th><th class="num">가격</th><th class="num">수량</th><th>상태</th><th></th></tr></thead>
            <tbody><tr v-for="o in acc.orders" :key="o.id"><td class="small">{{ datetime(o.created_at) }}</td><td>{{ o.name }}</td>
              <td :class="o.side === 'buy' ? 'up' : 'down'">{{ o.side === 'buy' ? '매수' : '매도' }} <span class="tiny faint">{{ o.type === 'limit' ? '지정' : '시장' }}</span></td>
              <td class="num">{{ price(o.fill_price ?? o.price, curOf(o.symbol)) }}</td><td class="num">{{ num(o.qty, 4) }}</td>
              <td><span class="chip" :class="{ green: o.status === 'filled', orange: o.status === 'open' }">{{ STATUS[o.status] }}</span> <span class="tiny faint">{{ o.note }}</span></td>
              <td><button v-if="o.status === 'open'" class="sm danger" @click="cancel(o)">취소</button></td></tr></tbody></table></div>
        <div class="card flush" style="max-height:420px;overflow:auto"><div style="padding:12px 12px 0"><h3>체결 내역</h3></div>
          <table class="t"><thead><tr><th>시각</th><th>종목</th><th>구분</th><th class="num">체결가</th><th class="num">수량</th><th class="num">실현손익</th></tr></thead>
            <tbody><tr v-for="t in acc.trades" :key="t.id"><td class="small">{{ datetime(t.ts) }}</td><td>{{ t.name }}</td><td :class="t.side === 'buy' ? 'up' : 'down'">{{ t.side === 'buy' ? '매수' : '매도' }}</td>
              <td class="num">{{ price(t.price, curOf(t.symbol)) }}</td><td class="num">{{ num(t.qty, 4) }}</td><td class="num" :class="cls(t.pnl)">{{ t.pnl == null ? '' : won(t.pnl) }}</td></tr></tbody></table></div>
      </div>
    </template>
    <Modal v-if="newOpen" title="새 모의계좌" @close="newOpen = false">
      <div class="col"><label class="field">이름<input v-model="nf.name" /></label><label class="field">시작 금액 (원)<NumInput v-model="nf.cash" /></label>
        <button class="primary" @click="create">만들기</button></div>
    </Modal>
  </div>
</template>
<script setup>
import { computed, reactive, ref, watch } from 'vue'
import MiniChart from '../components/MiniChart.vue'
import NumInput from '../components/NumInput.vue'
import Modal from '../components/Modal.vue'
import SymLink from '../components/SymLink.vue'
import { api, toast } from '../lib/api'
import { accountId, accounts, loadAccounts, selectAccount } from '../lib/accounts'
import { cls, curOf, datetime, num, pct, price, won } from '../lib/fmt'
import { useInterval } from '../lib/poll'
const STATUS = { open: '대기', filled: '체결', cancelled: '취소', rejected: '거부' }
const acc = ref(null); const newOpen = ref(false); const nf = reactive({ name: '', cash: 100000000 })
async function load() { if (!accounts.value.length) await loadAccounts(); if (accountId.value) acc.value = await api.get(`/trade/accounts/${accountId.value}`, null, { quiet: !!acc.value }) }
watch(accountId, () => { acc.value = null; load() }); load(); useInterval(load, 6000)
const allocation = computed(() => {
  if (!acc.value) return []
  const tot = acc.value.equity || 1
  return [{ name: '현금', pct: acc.value.cash / tot * 100 }, ...acc.value.positions.map(p => ({ name: p.name, pct: p.value_krw / tot * 100 }))].sort((a, b) => b.pct - a.pct)
})
async function cancel(o) { await api.del(`/trade/orders/${o.id}`); load() }
async function create() { const r = await api.post('/trade/accounts', nf); await loadAccounts(); selectAccount(r.id); newOpen.value = false }
async function reset() { if (!window.confirm('이 계좌의 보유 종목과 거래 기록을 모두 지우고 시작 금액으로 되돌릴까요?')) return; await api.post(`/trade/accounts/${accountId.value}/reset`); toast('초기화했습니다', 'ok'); load() }
async function removeAcc() { if (!window.confirm('이 계좌를 삭제할까요?')) return; await api.del(`/trade/accounts/${accountId.value}`); await loadAccounts(); load() }
</script>
