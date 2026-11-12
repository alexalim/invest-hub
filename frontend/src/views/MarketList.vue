<template>
  <div>
    <div class="page-h"><div><h1>전체 종목</h1><div class="muted small">{{ num(d?.total) }}개 · 열 제목을 누르면 정렬</div></div>
      <div class="row wrap">
        <div class="seg"><button v-for="m in MK" :key="m[0]" :class="{ on: mk === m[0] }" @click="mk = m[0]; page = 1">{{ m[1] }}</button></div>
        <select aria-label="종목 종류" v-if="mk === 'KOSPI'" v-model="kind" @change="page = 1"><option value="stock">주식</option><option value="etf">ETF</option><option value="etn">ETN</option></select>
      </div></div>
    <div class="card flush">
      <Loading v-if="!d" />
      <QuoteTable v-else :rows="live" :columns="cols" rank :offset="(page - 1) * 50" sortable @sort="setSort" />
    </div>
    <div class="row" style="margin-top:10px;justify-content:center" v-if="d">
      <button class="sm" :disabled="page === 1" @click="page--">이전</button><span class="small">{{ page }} / {{ Math.ceil(d.total / 50) }}</span>
      <button class="sm" :disabled="page * 50 >= d.total" @click="page++">다음</button></div>
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import QuoteTable from '../components/QuoteTable.vue'
import { api } from '../lib/api'
import { num } from '../lib/fmt'
import { useQuotes } from '../lib/poll'
const MK = [['KOSPI', '코스피'], ['KOSDAQ', '코스닥'], ['US', '미국'], ['CRYPTO', '코인']]
const mk = ref('KOSPI'); const kind = ref('stock'); const sort = ref('mcap'); const desc = ref(true); const page = ref(1); const d = ref(null)
const cols = computed(() => mk.value === 'CRYPTO' ? ['price', 'change_pct', 'value'] : ['price', 'change_pct', 'value', 'mcap', 'per', 'pbr', 'div_yield'])
function setSort(k) { if (sort.value === k) desc.value = !desc.value; else { sort.value = k; desc.value = true } page.value = 1 }
watch([mk, kind, sort, desc, page], async () => { d.value = await api.get('/market/list', { market_: mk.value, kind: kind.value, sort: sort.value === 'change_pct' ? 'change_pct' : sort.value, desc: desc.value, page: page.value, size: 50 }) }, { immediate: true })
const q = useQuotes(computed(() => d.value ? d.value.rows.map(r => r.symbol) : []), 6000)
const live = computed(() => d.value.rows.map(r => q[r.symbol] ? { ...r, price: q[r.symbol].price, change_pct: q[r.symbol].change_pct } : r))
</script>
