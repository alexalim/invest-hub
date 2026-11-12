<template>
  <!-- 워크포워드 검증 결과 안내. 서버가 주 1회 다시 계산한다. -->
  <div class="vn card" v-if="v && v.at">
    <div class="row between"><b>검증 결과 — {{ title }}</b><span class="tiny faint">{{ date(v.at) }} 계산 · 국내 시총 3천억↑ {{ v.universe }}종목 · 다음날 시가 매수 → {{ v.horizon }}거래일 뒤 종가, 비용 {{ v.cost }}% · 같은 날 시장 평균 대비</span></div>

    <template v-if="kind === 'ai'">
      <p class="small" style="margin:6px 0">
        과거 {{ v.ai.dates }}개 시점 × 시총 상위 종목 {{ num(v.ai.n) }}건을, 그 시점에 알 수 있던 정보만으로 다시 예측해 봤습니다.
        예측 점수와 실제 수익률의 순위 상관은 <b :class="v.ai.ic > 0.03 ? 'ok' : 'warn'">{{ v.ai.ic >= 0 ? '+' : '' }}{{ v.ai.ic }}</b>{{ v.ai.ic > 0.03 ? '' : ' (사실상 0)' }}입니다.
        <b v-if="v.ai.ic <= 0.03">지금 방식의 AI예측은 앞으로의 수익률을 맞히지 못했습니다. 참고용으로만 보세요.</b>
      </p>
      <div class="row wrap small"><span class="muted">의견별 실제 성과:</span>
        <span v-for="o in ORDER.filter(o => v.ai.by_opinion[o])" :key="o" class="chip" :class="v.ai.by_opinion[o].excess >= 0 ? 'red' : 'bluedown'">{{ o }} {{ pct(v.ai.by_opinion[o].excess) }} <span class="faint">({{ v.ai.by_opinion[o].n }})</span></span></div>
    </template>

    <template v-else>
      <p class="small" style="margin:6px 0">
        "이 종목에서 과거 적중률이 높았던 신호"만 고르면 <b :class="cls(sel.selected)">{{ pct(sel.selected) }}</b>({{ num(sel.selected_n) }}건),
        빠진 신호는 <b :class="cls(sel.rejected)">{{ pct(sel.rejected) }}</b>({{ num(sel.rejected_n) }}건)였습니다.
        <b v-if="sel.selected <= sel.rejected">종목별 과거 적중률은 다음 성과를 예측하지 못했으니, 그 숫자로 종목을 고르지 마세요.</b>
      </p>
      <div v-if="kind === 'signals'" class="scroll-x"><table class="t">
        <thead><tr><th>전략 (모든 매수 신호)</th><th class="num">앞 1년</th><th class="num">뒤 1년</th><th>판정</th></tr></thead>
        <tbody><tr v-for="s in per" :key="s.key"><td>{{ s.name }}</td><td class="num" :class="cls(s.first)">{{ pct(s.first) }}</td><td class="num" :class="cls(s.second)">{{ pct(s.second) }}</td>
          <td><span class="chip" :class="s.verdict.startsWith('양쪽 모두 시장보다 나음') ? 'green' : s.verdict.includes('못함') ? 'bluedown' : ''">{{ s.verdict }}</span></td></tr></tbody></table></div>
      <p class="tiny faint" style="margin-top:6px">15개 전략을 한꺼번에 시험하면 몇 개는 우연히 좋아 보일 수 있고, 현재 대형주만 대상이라 생존 편향이 있으며, 최근 2년은 강세장이었습니다.</p>
    </template>
  </div>
  <div v-else-if="v" class="notice small">검증 결과를 아직 계산하지 않았습니다. 일봉 수집이 끝나면 서버가 자동으로 계산합니다 (설정 → 작업 '전략·AI예측 검증').</div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { api } from '../lib/api'
import { cls, date, num, pct } from '../lib/fmt'

const props = defineProps({ kind: { type: String, default: 'signals' } })  // signals | ai | stock-signals
const ORDER = ['강력 매수', '매수', '중립', '매도', '강력 매도']
const v = ref(null)
api.get('/discover/validation', null, { quiet: true }).then(r => (v.value = r)).catch(() => (v.value = {}))
const title = computed(() => props.kind === 'ai' ? 'AI예측에 예측력이 있었나' : '매매신호를 따라 샀다면')
const sel = computed(() => v.value.strategies.selection)
const per = computed(() => Object.entries(v.value.strategies.per_strategy).map(([key, s]) => ({ key, ...s })).sort((a, b) => (b.first + b.second) - (a.first + a.second)))
</script>

<style scoped>.vn { border-left: 4px solid var(--warn); }</style>
