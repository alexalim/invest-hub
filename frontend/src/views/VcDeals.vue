<template>
  <div>
    <div class="page-h"><div><h1>투자/M&A</h1><div class="muted small">{{ d ? `${num(d.total)}건 · 공개 금액 합계 ${won(d.amount)}` : '' }}</div></div>
      <a class="btn" :href="'/api/vc/deals.csv' + qs(params)">CSV 내려받기</a></div>
    <div class="card" style="margin-bottom:12px"><div class="row wrap">
      <input v-model="f.q" placeholder="기업명·기사 제목" class="w120" style="width:180px" />
      <select aria-label="거래 종류" v-model="f.kind"><option value="">투자+M&A</option><option value="investment">투자</option><option value="mna">M&A</option></select>
      <select aria-label="투자 단계" v-model="f.round_"><option value="">모든 단계</option><option v-for="r in meta?.rounds || []" :key="r">{{ r }}</option></select>
      <select aria-label="분야" v-model="f.category"><option value="">모든 분야</option><option v-for="c in meta?.categories || []" :key="c">{{ c }}</option></select>
      <NumInput v-model="f.min_amount" class="w90" placeholder="최소(억)" /><NumInput v-model="f.max_amount" class="w90" placeholder="최대(억)" />
      <input aria-label="시작일" v-model="f.date_from" type="date" /> ~ <input aria-label="종료일" v-model="f.date_to" type="date" />
      <select aria-label="지역" v-model="f.region"><option value="kr">국내</option><option value="global">해외</option><option value="all">전체</option></select>
      <select aria-label="정렬" v-model="f.sort"><option value="date">최신순</option><option value="amount">금액순</option></select>
    </div></div>
    <div class="card flush"><Loading v-if="!d" /><DealTable v-else :rows="d.rows" admin @fix="fix" /></div>
    <Pager v-model="page" :total="d?.total || 0" />
    <div class="tiny faint" style="margin-top:8px">기사 제목·본문에서 규칙으로 뽑은 자료라 틀릴 수 있습니다. 관리자는 각 행에서 해외 표시·삭제로 바로잡을 수 있습니다.</div>
  </div>
</template>
<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import DealTable from '../components/DealTable.vue'
import Pager from '../components/Pager.vue'
import NumInput from '../components/NumInput.vue'
import { api, qs, toast } from '../lib/api'
import { num, won } from '../lib/fmt'
import { useVcMeta } from '../lib/vcmeta'
const route = useRoute(); const meta = useVcMeta()
const f = reactive({ q: '', kind: '', round_: '', category: '', min_amount: '', max_amount: '', date_from: '', date_to: '', region: 'kr', sort: route.query.sort || 'date' })
const page = ref(1); const d = ref(null)
const params = computed(() => ({ ...f, sort: undefined }))
let t
watch(f, () => { clearTimeout(t); t = setTimeout(() => { page.value = 1; load() }, 300) }, { deep: true })
watch(page, load)
async function load() { d.value = await api.get('/vc/deals', { ...f, page: page.value }) }
async function fix(deal, patch) { if (patch.delete && !window.confirm(`${deal.company} 건을 삭제할까요?`)) return; await api.patch(`/vc/deals/${deal.id}`, patch); toast('반영했습니다', 'ok'); load() }
load()
</script>
