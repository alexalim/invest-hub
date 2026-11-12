<template>
  <div>
    <div class="page-h"><div><h1>기업 비교</h1><div class="muted small">최대 4곳. 스타트업 목록에서 체크하거나 아래에서 이름으로 추가하세요.</div></div>
      <div class="row"><input v-model="q" placeholder="기업 이름" @keydown.enter="find" /><button @click="find">추가</button></div></div>
    <div v-if="!rows.length" class="card empty">비교할 기업을 고르세요</div>
    <div v-else class="card flush scroll-x"><table class="t">
      <thead><tr><th>항목</th><th v-for="c in rows" :key="c.id"><router-link :to="'/vc/companies/' + c.id" class="link">{{ c.name }}</router-link> <button class="ghost sm" @click="remove(c.id)">✕</button></th></tr></thead>
      <tbody>
        <tr v-for="r in ROWS" :key="r[0]"><td class="muted">{{ r[1] }}</td><td v-for="c in rows" :key="c.id">{{ r[2](c) }}</td></tr>
        <tr><td class="muted">투자 이력</td><td v-for="c in rows" :key="c.id" class="small"><div v-for="d in c.deals" :key="d.date + d.round">{{ d.date }} {{ d.round || '' }} {{ d.amount ? won(d.amount) : d.amount_text || '' }}</div></td></tr>
        <tr><td class="muted">매출 추이</td><td v-for="c in rows" :key="c.id"><MiniChart v-if="c.financials.length" type="bar" :series="[{ values: c.financials.map(f => f.revenue || 0), color: 'var(--accent)' }]" :h="60" /><span v-else class="faint small">자료 없음</span></td></tr>
      </tbody></table></div>
  </div>
</template>
<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MiniChart from '../components/MiniChart.vue'
import { api, toast } from '../lib/api'
import { won } from '../lib/fmt'
const route = useRoute(); const router = useRouter(); const rows = ref([]); const q = ref('')
const lastFin = c => c.financials[c.financials.length - 1] || {}
const ROWS = [['category', '분야', c => c.category || '-'], ['founded', '설립', c => c.founded || '-'], ['ceo', '대표', c => c.ceo || '-'],
  ['employees', '임직원', c => c.employees ? c.employees + '명' : '-'], ['raised', '누적 유치', c => won(c.total_raised)], ['deals', '투자 횟수', c => c.deal_count],
  ['round', '최근 단계', c => c.last_round || '-'], ['last', '최근 투자일', c => c.last_deal_date || '-'],
  ['rev', '최근 매출', c => lastFin(c).revenue != null ? `${won(lastFin(c).revenue)} (${lastFin(c).year})` : '-'], ['op', '최근 영업이익', c => lastFin(c).op_income != null ? won(lastFin(c).op_income) : '-']]
const ids = () => (route.query.ids || '').split(',').filter(Boolean)
watch(() => route.query.ids, async () => { rows.value = ids().length ? await api.get('/vc/compare', { ids: ids().join(',') }) : [] }, { immediate: true })
async function find() {
  const r = await api.get('/vc/companies', { q: q.value, has_deal: 0, region: 'all' })
  if (!r.rows.length) return toast('찾지 못했습니다')
  const next = [...new Set([...ids(), String(r.rows[0].id)])].slice(0, 4); q.value = ''
  router.replace({ query: { ids: next.join(',') } })
}
function remove(id) { router.replace({ query: { ids: ids().filter(x => +x !== id).join(',') } }) }
</script>
