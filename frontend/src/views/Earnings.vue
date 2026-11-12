<template>
  <div>
    <div class="page-h"><div><h1>미국 실적 일정</h1><div class="muted small">앞으로 6거래일 동안 실적을 발표하는 미국 종목입니다. 날짜마다 시가총액이 큰 순서로 최대 40개를 보여줍니다.</div></div></div>
    <Loading v-if="!d" />
    <div v-else-if="!d.days.length" class="card empty">일정을 받지 못했습니다. 잠시 뒤 다시 열어 주세요.</div>
    <div v-else class="col" style="gap:12px">
      <div v-for="day in d.days" :key="day.date" class="card flush">
        <div style="padding:12px 12px 0"><h3>{{ label(day.date) }} <span class="small muted">{{ day.total }}종목</span></h3></div>
        <div class="scroll-x"><table class="t">
          <thead><tr><th>종목</th><th>발표</th><th class="num">예상 주당순이익</th><th class="num">1년 전</th><th class="num">분기</th><th class="num">현재가</th><th class="num">오늘</th><th class="num">시가총액</th></tr></thead>
          <tbody><tr v-for="r in day.rows" :key="r.symbol" class="click" @click="$router.push('/stock/' + r.symbol)">
            <td><SymLink :symbol="r.symbol" :name="r.name" /></td><td><span class="chip" :class="{ orange: r.when === '개장 전', blue: r.when === '마감 후' }">{{ r.when }}</span></td>
            <td class="num">{{ usd(r.eps_forecast) }}</td><td class="num muted">{{ usd(r.eps_last) }}</td><td class="num small muted">{{ r.quarter }}</td>
            <td class="num">{{ price(r.price, 'USD') }}</td><td class="num" :class="cls(r.change_pct)">{{ pct(r.change_pct) }}</td><td class="num">{{ mcap(r.mcap, 'USD') }}</td></tr>
            <tr v-if="!day.rows.length"><td colspan="8" class="empty">우리 종목 목록에 있는 발표 종목이 없습니다</td></tr></tbody></table></div>
      </div>
      <div class="tiny faint">출처: 나스닥 실적 달력. 날짜는 미국 동부 기준이며 '마감 후' 발표는 한국 시간으로 다음 날 새벽입니다. 발표일은 회사 사정으로 바뀔 수 있습니다. 국내 종목의 발표 예정일은 무료 출처가 없어 넣지 못했습니다.</div>
    </div>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import SymLink from '../components/SymLink.vue'
import { api } from '../lib/api'
import { cls, mcap, pct, price } from '../lib/fmt'
const d = ref(null)
api.get('/pulse/earnings').then(r => (d.value = r)).catch(() => (d.value = { days: [] }))
const DOW = ['일', '월', '화', '수', '목', '금', '토']
function label(s) { const t = new Date(s + 'T00:00:00'); return `${t.getMonth() + 1}월 ${t.getDate()}일 (${DOW[t.getDay()]})` }
function usd(v) { return v == null ? '-' : (v < 0 ? '-$' : '$') + Math.abs(v).toFixed(2) }
</script>
