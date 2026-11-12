<template>
  <div>
    <div class="page-h"><div><h1>상대강도 순위</h1><div class="muted small">최근 1년 수익률로 전체 종목을 줄 세운 점수(1~99)입니다. 99는 상위 1%라는 뜻이고, 최근 3개월에 두 배 가중을 줍니다.</div></div>
      <div class="row wrap"><div class="seg"><button v-for="m in MK" :key="m[0]" :class="{ on: mk === m[0] }" @click="mk = m[0]">{{ m[1] }}</button></div>
        <select v-model.number="minCap" aria-label="최소 시가총액"><option v-for="c in CAPS[mk]" :key="c[0]" :value="c[0]">{{ c[1] }}</option></select></div></div>
    <div v-if="!d" class="spinner" />
    <div v-else class="card flush">
      <div class="scroll-x"><table class="t">
        <thead><tr><th class="num">#</th><th>종목</th><th class="num">RS</th><th class="num">한 달 전</th><th class="num">3개월</th><th class="num">1년</th><th class="num">현재가</th><th class="num">오늘</th><th class="num">시가총액</th><th></th></tr></thead>
        <tbody><tr v-for="(r, i) in d.rows" :key="r.symbol" class="click" @click="$router.push('/stock/' + r.symbol)">
          <td class="num faint">{{ i + 1 }}</td><td><SymLink :symbol="r.symbol" :name="r.name" /></td>
          <td class="num"><b>{{ r.rs }}</b></td>
          <td class="num"><span v-if="r.rs_prev != null">{{ r.rs_prev }} <span class="tiny" :class="cls(r.rs - r.rs_prev)">{{ r.rs === r.rs_prev ? '' : signed(r.rs - r.rs_prev) }}</span></span><span v-else>-</span></td>
          <td class="num" :class="cls(r.r3m)">{{ pct(r.r3m, 1) }}</td><td class="num" :class="cls(r.r12m)">{{ pct(r.r12m, 1) }}</td>
          <td class="num">{{ price(r.price, curOf(r.symbol)) }}</td><td class="num" :class="cls(r.change_pct)">{{ pct(r.change_pct) }}</td>
          <td class="num">{{ mcap(r.mcap, curOf(r.symbol)) }}</td><td><span v-if="r.near_high" class="chip red">52주 고점 근처</span></td></tr>
          <tr v-if="!d.rows.length"><td colspan="10" class="empty">일봉 수집이 끝나면 표시됩니다</td></tr></tbody></table></div>
      <div class="tiny faint" style="padding:10px 12px">{{ d.asof ? d.asof.slice(0, 4) + '-' + d.asof.slice(4, 6) + '-' + d.asof.slice(6) : '' }} 종가 기준 · 대상 {{ num(d.total) }}종목 중 상위 {{ d.rows.length }}개.
        많이 오른 종목을 순서대로 보여줄 뿐이며, 이 순위대로 샀을 때의 성과는 따로 검증하지 않았습니다. 급등 직후 종목은 변동이 큽니다.</div>
    </div>
  </div>
</template>
<script setup>
import { ref, watch } from 'vue'
import SymLink from '../components/SymLink.vue'
import { api } from '../lib/api'
import { cls, curOf, mcap, num, pct, price, signed } from '../lib/fmt'
const MK = [['KR', '국내'], ['US', '미국']]
const CAPS = { KR: [[1000, '시총 1천억 원 이상'], [3000, '3천억 원 이상'], [10000, '1조 원 이상'], [0, '전체']], US: [[100, '시총 100억 달러 이상'], [10, '10억 달러 이상'], [0, '전체']] }
const mk = ref('KR'); const minCap = ref(1000); const d = ref(null)
watch(mk, () => { minCap.value = CAPS[mk.value][0][0] })
watch([mk, minCap], async () => { d.value = null; d.value = await api.get('/pulse/rs', { market_: mk.value, min_mcap: minCap.value, limit: 100 }) }, { immediate: true })
</script>
