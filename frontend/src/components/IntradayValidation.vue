<template>
  <div class="card vn" v-if="v && v.at">
    <div class="row between"><b>장중 단타 검증 — 하루 안에 사고팔았다면</b>
      <span class="tiny faint">{{ date(v.at) }} 계산 · 거래대금 상위 {{ v.symbols }}종목 · {{ v.first_day }} ~ {{ v.last_day }} ({{ v.days }}거래일) · 비용 {{ v.cost }}%</span></div>
    <p class="small" style="margin:6px 0">
      자료가 <b>{{ v.days }}거래일</b>뿐이라 통계적으로 약합니다. 같은 날 여러 종목이 함께 움직이므로, 거래 건수보다 <b>거래한 날짜 수</b>로 신뢰도를 보세요.
      날짜 기준 t값이 2를 넘고 앞·뒤 기간 모두 플러스여야 "우연이 아닐 수 있다"고 볼 수 있습니다. 자료는 매일 장 마감 뒤 쌓입니다.
    </p>
    <div class="scroll-x"><table class="t">
      <thead><tr><th>전략</th><th class="num">거래</th><th class="num">거래일</th><th class="num">비용 뺀 평균</th><th class="num">이긴 비율</th>
        <th class="num" title="같은 날 거래대금 상위 종목 전체를 장 시작에 사서 마감에 판 평균과의 차이">같은 날 전체 대비</th><th class="num">앞 절반</th><th class="num">뒤 절반</th><th class="num" title="날짜별 평균으로 본 t값">t값(날짜)</th><th>판정</th></tr></thead>
      <tbody><tr v-for="s in rows" :key="s.key">
        <td><b class="small">{{ s.name }}</b><div class="tiny faint">{{ s.desc }}</div></td>
        <td class="num">{{ num(s.n) }}</td><td class="num">{{ s.days_traded ?? '-' }}</td>
        <td class="num" :class="cls(s.avg)">{{ s.avg == null ? '-' : pct(s.avg, 3) }}</td><td class="num">{{ s.win == null ? '-' : s.win + '%' }}</td>
        <td class="num" :class="cls(s.excess)">{{ s.excess == null ? '-' : pct(s.excess, 3) }}</td>
        <td class="num" :class="cls(s.first)">{{ s.first == null ? '-' : pct(s.first, 3) }}</td><td class="num" :class="cls(s.second)">{{ s.second == null ? '-' : pct(s.second, 3) }}</td>
        <td class="num">{{ s.t_day ?? '-' }}</td>
        <td><span class="chip" :class="(s.verdict || '').startsWith('양쪽 기간 모두 비용') ? 'green' : (s.verdict || '').includes('마이너스') ? 'bluedown' : ''">{{ s.verdict || '거래 부족' }}</span></td></tr></tbody></table></div>
  </div>
  <div v-else-if="v" class="notice small">장중 검증 결과가 아직 없습니다. 5분봉 수집이 끝나면 자동으로 계산합니다 (매일 15:50 이후).</div>
</template>
<script setup>
import { computed, ref } from 'vue'
import { api } from '../lib/api'
import { cls, date, num, pct } from '../lib/fmt'
const v = ref(null)
api.get('/discover/intraday/validation', null, { quiet: true }).then(r => (v.value = r)).catch(() => (v.value = {}))
const rows = computed(() => Object.entries(v.value.strategies || {}).map(([key, s]) => ({ key, ...s })).sort((a, b) => (b.avg ?? -99) - (a.avg ?? -99)))
</script>
<style scoped>.vn { border-left: 4px solid var(--warn); }</style>
