<template>
  <div>
    <div class="page-h"><div><h1>특징종목</h1><div class="muted small">급등·급락, 거래량 급증, 52주 신고가·신저가</div></div>
      <div class="seg"><button v-for="m in MK" :key="m[0]" :class="{ on: mk === m[0] }" @click="mk = m[0]">{{ m[1] }}</button></div></div>
    <Loading v-if="!d" />
    <div v-else class="grid g2">
      <div class="card flush" v-for="s in SECTIONS" :key="s.key">
        <div style="padding:12px 12px 0"><h3>{{ s.label }}</h3><div class="tiny faint" v-if="s.hint">{{ s.hint }}</div></div>
        <QuoteTable :rows="d[s.key]" :columns="s.cols" rank :empty="s.empty || '해당 종목이 없습니다'" />
      </div>
    </div>
  </div>
</template>
<script setup>
import { ref, watch } from 'vue'
import QuoteTable from '../components/QuoteTable.vue'
import { api } from '../lib/api'
const MK = [['KR', '국내'], ['KOSPI', '코스피'], ['KOSDAQ', '코스닥'], ['ETF', 'ETF'], ['US', '미국'], ['CR', '코인']]
const SECTIONS = [
  { key: 'up', label: '상승률 상위', cols: ['price', 'change_pct', 'value'], hint: '국내는 거래대금 5억 원 이상' },
  { key: 'down', label: '하락률 상위', cols: ['price', 'change_pct', 'value'] },
  { key: 'surge', label: '거래량 급증', cols: ['price', 'change_pct', 'vol_ratio'], hint: '오늘 거래량 ÷ 최근 한 달 평균 (2배 이상)', empty: '일봉 수집이 끝나면 표시됩니다' },
  { key: 'value', label: '거래대금 상위', cols: ['price', 'change_pct', 'value'] },
  { key: 'high52', label: '52주 신고가', cols: ['price', 'change_pct', 'value'], empty: '일봉 수집이 끝나면 표시됩니다' },
  { key: 'low52', label: '52주 신저가', cols: ['price', 'change_pct', 'value'], empty: '일봉 수집이 끝나면 표시됩니다' },
]
const mk = ref('KR'); const d = ref(null)
watch(mk, async () => { d.value = null; d.value = await api.get('/market/movers', { market_: mk.value, limit: 20 }) }, { immediate: true })
</script>
