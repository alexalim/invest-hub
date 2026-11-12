<template>
  <div>
    <div class="page-h"><div><h1>지수·환율·원자재</h1><div class="muted small">지수·선물·환율·원자재·금리. 항목을 누르면 차트로 이동합니다. 일부 해외 지표는 10분 지연될 수 있습니다.</div></div></div>
    <Loading v-if="!d" />
    <div v-else class="col" style="gap:14px">
      <div v-for="g in GROUPS" :key="g[0]">
        <h2>{{ g[1] }}</h2>
        <div class="tiles">
          <router-link v-for="m in d[g[0]]" :key="m.symbol" :to="'/stock/' + m.symbol" class="card tile">
            <div class="small muted">{{ m.name }}</div>
            <div class="v">{{ num(live(m).price, g[0] === 'rate' ? 3 : 2) }}</div>
            <div class="small" :class="cls(live(m).change_pct)">{{ signed(live(m).change, g[0] === 'rate' ? 3 : 2) }} ({{ pct(live(m).change_pct) }})</div>
            <MiniChart v-if="spark[m.symbol]" :series="[{ values: spark[m.symbol], color: live(m).change_pct >= 0 ? 'var(--up)' : 'var(--down)' }]" :h="40" :tip="false" />
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { computed, reactive, ref } from 'vue'
import MiniChart from '../components/MiniChart.vue'
import { api } from '../lib/api'
import { cls, num, pct, signed } from '../lib/fmt'
import { useQuotes } from '../lib/poll'
const GROUPS = [['index', '주요 지수'], ['future', '지수 선물'], ['fx', '환율'], ['commodity', '원자재'], ['rate', '금리 (%)']]
const d = ref(null); const spark = reactive({})
const q = useQuotes(computed(() => d.value ? Object.values(d.value).flat().map(m => m.symbol) : []), 15000)
function live(m) { return q[m.symbol] || m }
api.get('/market/indicators').then(async r => {
  d.value = r
  for (const m of Object.values(r).flat()) {
    api.get(`/stock/${m.symbol}/candles`, { tf: 'day', count: 60 }, { quiet: true }).then(c => (spark[m.symbol] = c.candles.map(x => x[4]))).catch(() => {})
  }
})
</script>
