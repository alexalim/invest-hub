<template>
  <div>
    <div class="page-h"><div><h1>투자자</h1><div class="muted small">{{ d ? num(d.total) + '곳' : '' }} · 투자 기사에서 이름이 확인된 투자자만 보입니다</div></div></div>
    <div class="card" style="margin-bottom:12px"><div class="row wrap">
      <input v-model="f.q" placeholder="투자사 이름" style="width:200px" />
      <select aria-label="투자자 유형" v-model="f.type_"><option value="">모든 유형</option><option v-for="t in meta?.investor_types || []" :key="t">{{ t }}</option></select>
      <select aria-label="정렬" v-model="f.sort"><option value="deals">투자 건수순</option><option value="amount">참여 금액순</option><option value="recent">최근 투자순</option><option value="name">이름순</option></select>
    </div></div>
    <div class="card flush"><Loading v-if="!d" />
      <div v-else class="scroll-x"><table class="t"><thead><tr><th>투자자</th><th>유형</th><th class="num">투자 건수</th><th class="num">참여 라운드 금액</th><th>최근 포트폴리오</th><th>최근 투자</th></tr></thead>
        <tbody><tr v-for="r in d.rows" :key="r.id" class="click" @click="$router.push('/vc/investors/' + r.id)">
          <td><b>{{ r.name }}</b></td><td class="small">{{ r.type }}</td><td class="num">{{ r.deal_count }}</td><td class="num">{{ won(r.total_amount) }}</td>
          <td class="small muted">{{ r.portfolio.join(', ') }}</td><td class="small">{{ r.last_deal_date }}</td></tr></tbody></table></div></div>
    <Pager v-model="page" :total="d?.total || 0" />
  </div>
</template>
<script setup>
import { reactive, ref, watch } from 'vue'
import Pager from '../components/Pager.vue'
import { api } from '../lib/api'
import { num, won } from '../lib/fmt'
import { useVcMeta } from '../lib/vcmeta'
const meta = useVcMeta(); const f = reactive({ q: '', type_: '', sort: 'deals' }); const page = ref(1); const d = ref(null)
let t
watch(f, () => { clearTimeout(t); t = setTimeout(() => { page.value = 1; load() }, 300) }, { deep: true }); watch(page, load)
async function load() { d.value = await api.get('/vc/investors', { ...f, page: page.value }) }
load()
</script>
