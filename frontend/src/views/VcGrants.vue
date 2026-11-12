<template>
  <div>
    <div class="page-h"><div><h1>지원사업</h1><div class="muted small">K-Startup 모집 공고 {{ d ? num(d.total) + '건' : '' }} · 6시간마다 갱신</div></div></div>
    <div class="grid g2" v-if="d" style="margin-bottom:12px">
      <div class="card"><h3>월별 마감 건수</h3><MiniChart type="bar" :series="[{ values: d.by_month.map(m => m.n), color: 'var(--accent)' }]" :labels="d.by_month.map(m => m.month)" :h="100" />
        <div class="row between tiny faint"><span v-for="m in d.by_month" :key="m.month">{{ m.month.slice(5) }}월</span></div></div>
      <div class="card"><h3>분야별</h3><div class="row wrap"><button v-for="c in d.by_category" :key="c.category" class="sm" :class="{ primary: f.category === c.category }" @click="f.category = f.category === c.category ? '' : c.category">{{ c.category }} {{ c.n }}</button></div></div>
    </div>
    <div class="card" style="margin-bottom:12px"><div class="row wrap"><input v-model="f.q" placeholder="공고명·기관·대상" style="width:240px" />
      <label class="row small"><input type="checkbox" v-model="openOnly" />모집 중만</label></div></div>
    <div class="card flush"><table class="t"><thead><tr><th>마감</th><th>공고</th><th>분야</th><th>주관</th><th>대상</th></tr></thead>
      <tbody><tr v-for="g in d?.rows || []" :key="g.id">
        <td class="nowrap"><span class="chip" :class="dday(g.end_date) <= 7 ? 'red' : ''">{{ g.end_date ? 'D-' + dday(g.end_date) : '상시' }}</span><div class="tiny faint">{{ g.end_date }}</div></td>
        <td><a :href="g.url" target="_blank" rel="noopener" class="link"><b>{{ g.title }}</b></a></td><td class="small">{{ g.category }}</td><td class="small">{{ g.org }}</td><td class="small muted">{{ g.target }}</td></tr>
        <tr v-if="d && !d.rows.length"><td colspan="5" class="empty">공고가 없습니다</td></tr></tbody></table></div>
    <Pager v-model="page" :total="d?.total || 0" />
  </div>
</template>
<script setup>
import { reactive, ref, watch } from 'vue'
import MiniChart from '../components/MiniChart.vue'
import Pager from '../components/Pager.vue'
import { api } from '../lib/api'
import { num } from '../lib/fmt'
const f = reactive({ q: '', category: '' }); const openOnly = ref(true); const page = ref(1); const d = ref(null); let t
async function load() { d.value = await api.get('/vc/grants', { ...f, open_only: openOnly.value ? 1 : 0, page: page.value }) }
function dday(e) { return Math.max(0, Math.ceil((Date.parse(e) - Date.now()) / 86400000)) }
watch([f, openOnly], () => { clearTimeout(t); t = setTimeout(() => { page.value = 1; load() }, 300) }, { deep: true }); watch(page, load); load()
</script>
