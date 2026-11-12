<template>
  <div v-if="d">
    <router-link to="/vc/collections" class="small link">← 컬렉션</router-link>
    <div class="page-h" style="margin-top:6px"><div><div class="row"><h1>{{ d.collection.name }}</h1><span v-if="d.collection.smart_spec" class="chip orange">스마트</span></div>
      <div class="small muted" v-if="d.collection.smart_spec">조건: {{ Object.entries(d.collection.smart_spec).filter(([, v]) => v).map(([k, v]) => `${k}=${v}`).join(', ') }}</div></div>
      <div class="row"><router-link v-if="d.companies.length > 1" :to="{ path: '/vc/compare', query: { ids: d.companies.slice(0, 4).map(c => c.id).join(',') } }" class="btn">앞의 4곳 비교</router-link>
        <button class="sm" @click="rename">이름 바꾸기</button><button class="sm danger" @click="del">삭제</button></div></div>
    <div class="card flush" style="margin-bottom:12px"><div style="padding:12px 12px 0"><h3>기업 {{ d.companies.length }}</h3></div>
      <table class="t"><thead><tr><th>기업</th><th>분야</th><th>최근 단계</th><th class="num">누적 유치</th><th>최근 투자</th><th v-if="!d.collection.smart_spec"></th></tr></thead>
        <tbody><tr v-for="c in d.companies" :key="c.id" class="click" @click="$router.push('/vc/companies/' + c.id)"><td><b>{{ c.name }}</b></td><td class="small">{{ c.category }}</td>
          <td><span class="chip blue" v-if="c.last_round">{{ c.last_round }}</span></td><td class="num">{{ won(c.total_raised) }}</td><td class="small">{{ c.last_deal_date }}</td>
          <td v-if="!d.collection.smart_spec" @click.stop><button class="sm ghost danger" @click="out('company', c.id)">빼기</button></td></tr></tbody></table></div>
    <div class="card flush" v-if="d.investors.length"><div style="padding:12px 12px 0"><h3>투자자 {{ d.investors.length }}</h3></div>
      <table class="t"><tbody><tr v-for="i in d.investors" :key="i.id" class="click" @click="$router.push('/vc/investors/' + i.id)"><td><b>{{ i.name }}</b></td><td class="small">{{ i.type }}</td><td class="num">{{ i.deal_count }}건</td>
        <td @click.stop><button class="sm ghost danger" @click="out('investor', i.id)">빼기</button></td></tr></tbody></table></div>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../lib/api'
import { won } from '../lib/fmt'
const route = useRoute(); const router = useRouter(); const d = ref(null)
async function load() { d.value = await api.get(`/vc/collections/${route.params.id}`) }
async function out(type, id) { await api.post(`/vc/collections/${route.params.id}/toggle`, { entity_type: type, entity_id: id }); load() }
async function rename() { const n = window.prompt('새 이름', d.value.collection.name); if (n) { await api.post('/vc/collections', { ...d.value.collection, name: n }); load() } }
async function del() { if (window.confirm('컬렉션을 삭제할까요?')) { await api.del(`/vc/collections/${route.params.id}`); router.push('/vc/collections') } }
load()
</script>
