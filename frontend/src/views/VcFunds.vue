<template>
  <div>
    <div class="page-h"><div><h1>펀드</h1><div class="muted small">벤처펀드·투자조합 결성 소식 {{ d ? num(d.total) + '건' : '' }}</div></div><input v-model="q" placeholder="펀드·운용사" style="width:200px" /></div>
    <div class="card flush"><table class="t"><thead><tr><th>결성일</th><th>펀드</th><th>운용사</th><th class="num">규모</th><th>출처</th></tr></thead>
      <tbody><tr v-for="f in d?.rows || []" :key="f.id"><td class="small">{{ f.date }}</td><td><b>{{ f.name }}</b><div class="tiny faint ellipsis" style="max-width:420px">{{ f.title }}</div></td>
        <td><router-link v-if="f.investor_id" :to="'/vc/investors/' + f.investor_id" class="link small">{{ f.manager }}</router-link></td>
        <td class="num">{{ f.size ? won(f.size) : f.size_text || '-' }}</td><td><a :href="f.source_url" target="_blank" rel="noopener" class="link small">기사</a></td></tr>
        <tr v-if="d && !d.rows.length"><td colspan="5" class="empty">없습니다</td></tr></tbody></table></div>
    <Pager v-model="page" :total="d?.total || 0" />
  </div>
</template>
<script setup>
import { ref, watch } from 'vue'
import Pager from '../components/Pager.vue'
import { api } from '../lib/api'
import { num, won } from '../lib/fmt'
const q = ref(''); const page = ref(1); const d = ref(null); let t
async function load() { d.value = await api.get('/vc/funds', { q: q.value, page: page.value }) }
watch(q, () => { clearTimeout(t); t = setTimeout(() => { page.value = 1; load() }, 300) }); watch(page, load); load()
</script>
