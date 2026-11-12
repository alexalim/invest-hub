<template>
  <div>
    <div class="page-h"><div><h1>알림</h1><div class="muted small">가격·등락률·지표 조건 알림. 서버가 20초마다 확인해 오른쪽 위 종에 알립니다.</div></div>
      <SymbolSearch placeholder="종목을 골라 알림 만들기" style="width:280px" @select="s => (pick = s)" /></div>
    <div class="card flush"><table class="t">
      <thead><tr><th>종목</th><th>조건</th><th>메모</th><th>마지막 알림</th><th>상태</th><th></th></tr></thead>
      <tbody><tr v-for="a in rows" :key="a.id">
        <td><SymLink :symbol="a.symbol" :name="a.name" /></td>
        <td class="small">{{ desc(a) }}</td><td class="small muted">{{ a.note }}</td><td class="small">{{ a.triggered_at ? datetime(a.triggered_at) : '-' }}</td>
        <td><label class="row small nowrap"><input type="checkbox" :checked="!!a.active" @change="toggle(a, $event.target.checked)" />{{ a.active ? '켜짐' : '꺼짐' }}</label></td>
        <td><button class="sm ghost danger" @click="del(a)">삭제</button></td></tr>
        <tr v-if="!rows.length"><td colspan="6" class="empty">알림이 없습니다. 종목 화면의 🔔 버튼이나 위 검색창으로 만드세요.</td></tr></tbody></table></div>
    <AlertModal v-if="pick" :symbol="pick.symbol" :name="pick.name" :price="pick.price" @close="pick = null" @saved="load" />
  </div>
</template>
<script setup>
import { ref } from 'vue'
import AlertModal from '../components/AlertModal.vue'
import SymLink from '../components/SymLink.vue'
import SymbolSearch from '../components/SymbolSearch.vue'
import { api } from '../lib/api'
import { datetime, num } from '../lib/fmt'
const rows = ref([]); const pick = ref(null)
async function load() { rows.value = await api.get('/user/alerts') }
function desc(a) {
  return { price_above: `가격 ≥ ${num(a.params.price, 2)}`, price_below: `가격 ≤ ${num(a.params.price, 2)}`, change_above: `등락률 ≥ ${a.params.pct}%`,
    change_below: `등락률 ≤ ${a.params.pct}%`, condition: a.desc }[a.kind] + (a.repeat ? ' (반복)' : '')
}
async function toggle(a, on) { await api.put(`/user/alerts/${a.id}`, { active: on }); load() }
async function del(a) { await api.del(`/user/alerts/${a.id}`); load() }
load()
</script>
