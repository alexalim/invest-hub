<template>
  <div>
    <div class="page-h"><div><h1>AI예측</h1>
      <div class="muted small">최근 차트와 닮은 과거 구간을 전 종목에서 찾아, 그 뒤 20거래일의 움직임으로 상승 확률·목표가·손절가를 계산합니다.</div></div>
      <div class="row wrap">
        <div class="seg"><button v-for="m in MK" :key="m[0]" :class="{ on: mk === m[0] }" @click="mk = m[0]">{{ m[1] }}</button></div>
        <div class="seg"><button v-for="w in [30, 60, 120]" :key="w" :class="{ on: win === w }" @click="win = w">{{ w }}일 패턴</button></div>
      </div></div>
    <ValidationNote kind="ai" style="margin-bottom:12px" />
    <div class="small muted" style="margin-bottom:12px">학습된 예측 모델이 아니라 패턴 유사도 통계입니다. 시가총액 상위 {{ limit }}종목을 대상으로 3시간마다 다시 계산합니다.</div>
    <div class="row" style="margin-bottom:10px"><div class="seg"><button v-for="f in FILTERS" :key="f[0]" :class="{ on: filt === f[0] }" @click="filt = f[0]">{{ f[1] }}</button></div></div>
    <div class="card flush">
      <div v-if="!d" class="row" style="padding:16px"><span class="spinner" /><span class="small muted">계산 중입니다. 처음에는 1~2분 걸릴 수 있습니다.</span></div>
      <div v-else class="scroll-x"><table class="t">
        <thead><tr><th>종목</th><th class="num">투자의견</th><th class="num">상승 확률</th><th class="num">예상 중앙값</th><th class="num">현재가</th><th class="num">목표가</th><th class="num">손절가</th><th class="num">평균 유사도</th></tr></thead>
        <tbody><tr v-for="r in rows" :key="r.symbol" class="click" @click="$router.push('/stock/' + r.symbol + '?tab=predict')">
          <td><SymLink :symbol="r.symbol" :name="r.name" /></td>
          <td class="num" :class="r.opinion.includes('매수') ? 'up' : r.opinion.includes('매도') ? 'down' : 'muted'" style="font-weight:700">{{ r.opinion }}</td>
          <td class="num">{{ r.up_prob }}%</td><td class="num" :class="cls(r.median)">{{ pct(r.median) }}</td>
          <td class="num">{{ price(r.price, curOf(r.symbol)) }} <span class="tiny" :class="cls(r.change_pct)">{{ pct(r.change_pct) }}</span></td>
          <td class="num up">{{ price(r.target, curOf(r.symbol)) }}</td><td class="num down">{{ price(r.stop, curOf(r.symbol)) }}</td><td class="num">{{ r.avg_corr }}</td></tr>
          <tr v-if="!rows.length"><td colspan="8" class="empty">해당하는 종목이 없습니다</td></tr></tbody></table></div>
    </div>
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import SymLink from '../components/SymLink.vue'
import ValidationNote from '../components/ValidationNote.vue'
import { api } from '../lib/api'
import { cls, curOf, pct, price } from '../lib/fmt'
const MK = [['KR', '국내'], ['KOSPI', '코스피'], ['KOSDAQ', '코스닥'], ['US', '미국'], ['CR', '코인']]
const FILTERS = [['all', '전체'], ['buy', '매수 의견'], ['sell', '매도 의견']]
const mk = ref('KR'); const win = ref(60); const filt = ref('all'); const d = ref(null); const limit = 150
watch([mk, win], async () => { d.value = null; d.value = await api.get('/discover/ai', { market_: mk.value, window: win.value, limit }) }, { immediate: true })
const rows = computed(() => (d.value?.rows || []).filter(r => filt.value === 'all' || (filt.value === 'buy' ? r.opinion.includes('매수') : r.opinion.includes('매도'))))
</script>
