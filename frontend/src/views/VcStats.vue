<template>
  <div>
    <div class="page-h"><div><h1>스타트업 투자 통계</h1>
      <div class="muted small">투자 유치 기사에서 자동으로 뽑은 국내 라운드 집계입니다. 정부 통계(투자기관 집행 실적)와 정의가 달라 직접 비교할 수 없고, 자동 추출이라 일부 금액은 기업가치를 투자금으로 잘못 읽었거나 같은 라운드가 두 번 잡혔을 수 있습니다.</div></div>
      <div class="seg"><button v-for="m in [3, 6, 12, 24]" :key="m" :class="{ on: months === m }" @click="months = m">{{ m }}개월</button></div></div>
    <div v-if="!s" class="spinner" />
    <template v-else>
      <div class="grid g4">
        <div class="card stat"><span class="k">투자 건수</span><span class="v">{{ num(s.total.n) }}건</span><span class="tiny faint">금액 비공개 {{ num(s.total.undisclosed) }}건 포함</span></div>
        <div class="card stat"><span class="k">공개 투자 금액 합계</span><span class="v">{{ won(s.total.amount) }}</span></div>
        <div class="card stat"><span class="k">M&A</span><span class="v">{{ num(s.mna.n) }}건</span><span class="tiny faint">공개 금액 {{ won(s.mna.amount) }}</span></div>
        <div class="card stat"><span class="k">펀드 결성</span><span class="v">{{ num(s.funds.n) }}건</span><span class="tiny faint">{{ won(s.funds.amount) }} · 해외 딜 {{ s.foreign.n }}건은 제외</span></div>
      </div>
      <div class="grid g2" style="margin-top:12px">
        <div class="card"><h3>월별 투자 건수</h3>
          <MiniChart type="bar" :series="[{ values: s.monthly.map(m => m.n), color: 'var(--accent)' }]" :labels="s.monthly.map(m => m.month)" :h="160" />
          <div class="row between tiny faint"><span>{{ s.monthly[0]?.month }}</span><span>{{ s.monthly[s.monthly.length - 1]?.month }}</span></div></div>
        <div class="card"><h3>월별 투자 금액 (억 원)</h3>
          <MiniChart type="bar" :series="[{ values: s.monthly.map(m => Math.round(m.amount / 1e8)), color: '#10b981' }]" :labels="s.monthly.map(m => m.month)" :h="160" />
          <div class="row between tiny faint"><span>{{ s.monthly[0]?.month }}</span><span>{{ s.monthly[s.monthly.length - 1]?.month }}</span></div></div>
      </div>
      <div class="grid g3" style="margin-top:12px">
        <div class="card"><h3>단계별</h3>
          <div v-for="r in s.by_round" :key="r.round" class="row small" style="padding:3px 0"><span style="width:110px">{{ r.round }}</span>
            <div class="bar-bg grow"><div class="bar-fg" :style="{ width: r.n / maxRound * 100 + '%' }" /></div><span class="num" style="width:44px">{{ r.n }}</span></div></div>
        <div class="card"><h3>분야별 (금액순)</h3>
          <div v-for="r in s.by_category" :key="r.category" class="row small" style="padding:3px 0"><router-link :to="{ path: '/vc/companies', query: { category: r.category } }" style="width:110px" class="ellipsis">{{ r.category }}</router-link>
            <div class="bar-bg grow"><div class="bar-fg" :style="{ width: r.amount / maxCat * 100 + '%', background: '#10b981' }" /></div><span class="num" style="width:70px">{{ won(r.amount) }}</span></div></div>
        <div class="card"><h3>규모별 건수</h3>
          <div v-for="r in s.size_buckets" :key="r.bucket" class="row small" style="padding:3px 0"><span style="width:110px">{{ r.bucket }}</span>
            <div class="bar-bg grow"><div class="bar-fg" :style="{ width: r.n / maxSize * 100 + '%', background: '#8b5cf6' }" /></div><span class="num" style="width:44px">{{ r.n }}</span></div></div>
      </div>
      <div class="grid g-side" style="margin-top:12px">
        <div class="card flush"><div style="padding:12px 12px 0" class="row between"><h3>큰 투자</h3><router-link to="/vc/deals?sort=amount" class="link small">전체</router-link></div><DealTable :rows="s.top_deals" /></div>
        <div class="card"><h3>활발한 투자자</h3>
          <div v-for="(r, i) in s.top_investors" :key="r.id" class="row between small" style="padding:3px 0">
            <router-link :to="'/vc/investors/' + r.id" class="link">{{ i + 1 }}. {{ r.name }}</router-link><span>{{ r.n }}건</span></div>
          <div v-if="!s.top_investors.length" class="small muted">투자자 정보가 추출된 기사가 아직 적습니다</div></div>
      </div>
    </template>
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import DealTable from '../components/DealTable.vue'
import MiniChart from '../components/MiniChart.vue'
import { api } from '../lib/api'
import { num, won } from '../lib/fmt'
const months = ref(12); const s = ref(null)
watch(months, async () => { s.value = await api.get('/vc/stats', { months: months.value }) }, { immediate: true })
const maxRound = computed(() => Math.max(1, ...s.value.by_round.map(r => r.n)))
const maxCat = computed(() => Math.max(1, ...s.value.by_category.map(r => r.amount)))
const maxSize = computed(() => Math.max(1, ...s.value.size_buckets.map(r => r.n)))
</script>
