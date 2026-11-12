<template>
  <div>
    <div class="page-h"><div><h1>스타트업</h1><div class="muted small">{{ d ? num(d.total) + '개 기업' : '' }}</div></div>
      <router-link v-if="sel.length" :to="{ path: '/vc/compare', query: { ids: sel.join(',') } }" class="btn primary">선택한 {{ sel.length }}곳 비교</router-link></div>
    <div class="card" style="margin-bottom:12px"><div class="row wrap">
      <input v-model="f.q" placeholder="기업명·소개" style="width:200px" />
      <select aria-label="분야" v-model="f.category"><option value="">모든 분야</option><option v-for="c in meta?.categories || []" :key="c">{{ c }}</option></select>
      <select aria-label="투자 단계" v-model="f.round_"><option value="">최근 단계 전체</option><option v-for="r in meta?.rounds || []" :key="r">{{ r }}</option></select>
      <NumInput v-model="f.min_raised" class="w120" placeholder="누적 유치 ≥ (억)" />
      <select aria-label="지역" v-model="f.region"><option value="kr">국내</option><option value="all">해외 포함</option></select>
      <select aria-label="정렬" v-model="f.sort"><option value="recent">최근 투자순</option><option value="raised">누적 유치순</option><option value="deals">투자 횟수순</option><option value="name">이름순</option></select>
      <button class="sm" @click="saveSmart">이 조건을 스마트 컬렉션으로</button>
    </div></div>
    <div class="card flush"><Loading v-if="!d" />
      <div v-else class="scroll-x"><table class="t">
        <thead><tr><th></th><th>기업</th><th>분야</th><th>최근 단계</th><th class="num">누적 유치</th><th class="num">투자 횟수</th><th class="num">기업가치</th><th>최근 투자</th></tr></thead>
        <tbody><tr v-for="c in d.rows" :key="c.id" class="click" @click="$router.push('/vc/companies/' + c.id)">
          <td @click.stop><input type="checkbox" :value="c.id" v-model="sel" :disabled="sel.length >= 4 && !sel.includes(c.id)" /></td>
          <td><b>{{ c.name }}</b><div class="tiny faint ellipsis" style="max-width:360px">{{ c.description }}</div></td>
          <td class="small">{{ c.category || '-' }}</td><td><span class="chip blue" v-if="c.last_round">{{ c.last_round }}</span></td>
          <td class="num">{{ c.total_raised ? won(c.total_raised) : '-' }}</td><td class="num">{{ c.deal_count }}</td>
          <td class="num">{{ c.valuation ? won(c.valuation) : '-' }}</td><td class="small">{{ c.last_deal_date }}</td></tr></tbody></table></div></div>
    <Pager v-model="page" :total="d?.total || 0" />
  </div>
</template>
<script setup>
import { reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import Pager from '../components/Pager.vue'
import NumInput from '../components/NumInput.vue'
import { api, toast } from '../lib/api'
import { num, won } from '../lib/fmt'
import { useVcMeta } from '../lib/vcmeta'
const route = useRoute(); const meta = useVcMeta()
const f = reactive({ q: '', category: route.query.category || '', round_: '', min_raised: '', region: 'kr', sort: 'recent' })
const page = ref(1); const d = ref(null); const sel = ref([])
let t
watch(f, () => { clearTimeout(t); t = setTimeout(() => { page.value = 1; load() }, 300) }, { deep: true })
watch(page, load)
async function load() { d.value = await api.get('/vc/companies', { ...f, page: page.value }) }
async function saveSmart() {
  const name = window.prompt('스마트 컬렉션 이름 (조건에 맞는 기업이 자동으로 담깁니다)'); if (!name) return
  await api.post('/vc/collections', { name, smart_spec: { q: f.q, category: f.category, round: f.round_, min_raised: f.min_raised, sort: f.sort } }); toast('저장했습니다', 'ok')
}
load()
</script>
