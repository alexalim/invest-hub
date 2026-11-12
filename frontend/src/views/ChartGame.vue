<template>
  <div>
    <div class="page-h"><div><h1>차트게임</h1><div class="muted small">실제 과거 차트를 종목·날짜를 가린 채 한 봉씩 넘기며 매매를 연습합니다. 가격은 시작 시점이 10,000이 되도록 바꿔 보여 줍니다.</div></div></div>
    <div v-if="!g" class="grid g-side">
      <div class="card">
        <h3>새 게임</h3>
        <div class="col">
          <div class="seg"><button v-for="m in [['KR','국내 주식'],['US','미국 주식'],['CR','코인']]" :key="m[0]" :class="{ on: mk === m[0] }" @click="mk = m[0]">{{ m[1] }}</button></div>
          <div class="seg"><button v-for="b in [30, 50, 80, 120]" :key="b" :class="{ on: bars === b }" @click="bars = b">{{ b }}봉</button></div>
          <div class="row"><button class="primary" @click="start()">혼자 하기</button><button @click="makeComp">친구 대결 만들기</button></div>
          <div class="row"><input v-model="code" placeholder="대결 코드" class="w120" /><button @click="start(code)" :disabled="!code">코드로 참가</button></div>
          <div v-if="comp" class="notice small">대결 코드 <b style="font-size:16px">{{ comp.code }}</b> — 친구에게 알려 주세요. 같은 차트로 겨룹니다. <button class="sm" @click="start(comp.code)">나도 시작</button></div>
        </div>
      </div>
      <div class="card"><h3>최근 게임</h3>
        <div v-for="h in list?.history || []" :key="h.id" class="row between small list-item">
          <span>{{ h.finished ? h.name : '진행 중' }} <span class="tiny faint">{{ h.bars }}봉 {{ h.code ? '· 대결 ' + h.code : '' }}</span></span>
          <span v-if="h.finished" :class="cls(h.result_pct)">{{ pct(h.result_pct) }}</span><button v-else class="sm" @click="open(h.id)">이어하기</button>
          <button v-if="h.code" class="sm ghost" @click="showComp(h.code)">순위</button></div>
        <div v-if="list && !list.history.length" class="empty small">아직 게임 기록이 없습니다</div>
      </div>
    </div>

    <div v-else class="grid g-side">
      <div class="card">
        <div class="row between" style="margin-bottom:6px"><b>{{ g.finished ? `${g.name} (${g.symbol})` : '???' }}</b><span class="small muted">{{ g.step }} / {{ g.bars }}봉</span></div>
        <div class="bar-bg" style="margin-bottom:8px"><div class="bar-fg" :style="{ width: g.step / g.bars * 100 + '%' }" /></div>
        <PriceChart :candles="g.candles" :overlays="ma" :markers="marks" :price-lines="g.qty ? [{ price: g.avg, title: '평단', color: '#f59e0b' }] : []" :height="440" />
      </div>
      <div class="col" style="gap:12px">
        <div class="card">
          <dl class="kv">
            <dt>평가액</dt><dd><b>{{ won(g.equity) }}원</b></dd><dt>수익률</dt><dd :class="cls(g.return_pct)">{{ pct(g.return_pct) }}</dd>
            <dt>현재가</dt><dd>{{ num(g.price, 0) }}</dd><dt>보유</dt><dd>{{ num(g.qty) }}주 (평단 {{ num(g.avg, 0) }})</dd><dt>현금</dt><dd>{{ won(g.cash) }}원</dd>
          </dl>
        </div>
        <div class="card" v-if="!g.finished">
          <div class="row"><button class="buy grow" @click="act('buy', 1)">전액 매수</button><button class="sell grow" @click="act('sell', 1)">전량 매도</button></div>
          <div class="row" style="margin-top:6px"><button class="sm grow" @click="act('buy', 0.5)">50% 매수</button><button class="sm grow" @click="act('sell', 0.5)">50% 매도</button></div>
          <div class="row" style="margin-top:10px"><button class="primary grow" @click="act('next', 1, 1)">다음 봉 ▶</button><button class="grow" @click="act('next', 1, 5)">5봉 ▶▶</button></div>
          <button class="sm ghost" style="margin-top:8px;width:100%" @click="act('finish')">끝까지 보기</button>
          <div class="tiny faint" style="margin-top:6px">키보드: B 매수 · S 매도 · → 다음 봉</div>
        </div>
        <div class="card" v-else>
          <h3>결과</h3>
          <div class="op-big" :class="cls(g.result_pct)">{{ pct(g.result_pct) }}</div>
          <div class="small">같은 기간 보유만 했다면 <span :class="cls(g.buy_hold_pct)">{{ pct(g.buy_hold_pct) }}</span></div>
          <div class="small muted">매매 {{ g.trades.length }}회 · 차트에 실제 날짜와 가격이 표시됩니다</div>
          <div class="row" style="margin-top:10px"><button class="primary" @click="g = null; loadList()">새 게임</button>
            <router-link :to="'/stock/' + g.symbol" class="btn">종목 보기</router-link>
            <button v-if="g.competition_id" @click="showComp()">대결 순위</button></div>
        </div>
      </div>
    </div>
    <Modal v-if="compView" :title="`대결 ${compView.code}`" @close="compView = null">
      <div class="small muted" style="margin-bottom:8px">{{ compView.bars }}봉 · {{ compView.name ? '종목: ' + compView.name : '끝내면 종목이 공개됩니다' }}</div>
      <table class="t"><thead><tr><th>참가자</th><th class="num">수익률</th><th class="num">매매</th></tr></thead>
        <tbody><tr v-for="p in compView.players" :key="p.id"><td>{{ p.nickname }}</td><td class="num" :class="cls(p.result_pct)">{{ p.finished ? pct(p.result_pct) : '진행 중' }}</td><td class="num">{{ p.trades }}</td></tr></tbody></table>
    </Modal>
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import Modal from '../components/Modal.vue'
import PriceChart from '../components/PriceChart.vue'
import { api } from '../lib/api'
import { cls, num, pct, won } from '../lib/fmt'
const mk = ref('KR'); const bars = ref(50); const code = ref(''); const comp = ref(null); const g = ref(null); const list = ref(null); const compView = ref(null); let compCode = null
async function loadList() { list.value = await api.get('/trade/game') }
async function start(c) { g.value = await api.post('/trade/game', { market: mk.value, bars: bars.value, code: c || undefined }); compCode = c || null }
async function open(id) { g.value = await api.get(`/trade/game/${id}`) }
async function makeComp() { comp.value = await api.post('/trade/game/competition', { market: mk.value, bars: bars.value }) }
async function act(action, ratio = 1, count = 1) { if (g.value && !g.value.finished) g.value = await api.post(`/trade/game/${g.value.id}`, { action, ratio, count }) }
async function showComp(c) { compView.value = await api.get(`/trade/game/competition/${c || compCode || comp.value?.code}`) }
const ma = computed(() => {
  const c = g.value.candles.map(x => x[4]); const mk2 = (n, color) => ({ color, data: g.value.candles.map((x, i) => [x[0], i >= n - 1 ? c.slice(i - n + 1, i + 1).reduce((a, b) => a + b) / n : null]) })
  return [mk2(5, '#f59e0b'), mk2(20, '#10b981'), mk2(60, '#8b5cf6')]
})
const marks = computed(() => g.value.trades.map(t => ({ time: t.ts, position: t.side === 'buy' ? 'belowBar' : 'aboveBar', color: t.side === 'buy' ? '#e0353c' : '#2366d1', shape: t.side === 'buy' ? 'arrowUp' : 'arrowDown', text: t.side === 'buy' ? '매수' : '매도' })))
function key(e) {
  if (!g.value || g.value.finished || e.target.tagName === 'INPUT') return
  if (e.key === 'b' || e.key === 'B') act('buy', 1); else if (e.key === 's' || e.key === 'S') act('sell', 1); else if (e.key === 'ArrowRight') { e.preventDefault(); act('next', 1, 1) }
}
onMounted(() => window.addEventListener('keydown', key)); onBeforeUnmount(() => window.removeEventListener('keydown', key))
loadList()
</script>
<style scoped>.op-big { font-size: 28px; font-weight: 800; }</style>
