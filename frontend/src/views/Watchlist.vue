<template>
  <div>
    <div class="page-h"><div><h1>관심종목</h1><div class="muted small">그룹별로 모아 보고, 시세는 몇 초마다 갱신됩니다.</div></div>
      <div class="row"><SymbolSearch placeholder="종목 추가" style="width:240px" @select="add" /><button @click="newGroup">+ 그룹</button></div></div>
    <div class="tabs"><button v-for="g in groups" :key="g.id" :class="{ on: gid === g.id }" @click="gid = g.id">{{ g.name }} <span class="faint">{{ g.items.length }}</span></button></div>
    <div v-if="cur" class="card flush">
      <div class="row between" style="padding:10px 12px"><span class="small muted">{{ cur.name }}</span>
        <div class="row"><button class="sm ghost" @click="rename">이름 바꾸기</button><button class="sm ghost danger" v-if="groups.length > 1" @click="removeGroup">그룹 삭제</button></div></div>
      <div class="scroll-x"><table class="t"><thead><tr><th>종목</th><th class="num">현재가</th><th class="num">등락</th><th class="num">등락률</th><th class="num">거래량</th><th>메모</th><th></th></tr></thead>
        <tbody><tr v-for="i in cur.items" :key="i.symbol" class="click" @click="$router.push('/stock/' + i.symbol)">
          <td><SymLink :symbol="i.symbol" :name="i.name" /></td><td class="num">{{ price(lv(i).price, i.currency) }}</td>
          <td class="num" :class="cls(lv(i).change)">{{ signed(lv(i).change, i.currency === 'USD' ? 2 : 0) }}</td><td class="num" :class="cls(lv(i).change_pct)">{{ pct(lv(i).change_pct) }}</td>
          <td class="num">{{ vol(lv(i).volume) }}</td><td class="small muted ellipsis" style="max-width:240px">{{ i.memo }}</td>
          <td @click.stop><button class="sm ghost danger" @click="remove(i)">빼기</button></td></tr>
          <tr v-if="!cur.items.length"><td colspan="7" class="empty">위 검색창에서 종목을 추가하세요</td></tr></tbody></table></div>
    </div>
  </div>
</template>
<script setup>
import { computed, ref } from 'vue'
import SymLink from '../components/SymLink.vue'
import SymbolSearch from '../components/SymbolSearch.vue'
import { api } from '../lib/api'
import { cls, pct, price, signed, vol } from '../lib/fmt'
import { useQuotes } from '../lib/poll'
const groups = ref([]); const gid = ref(null)
const cur = computed(() => groups.value.find(g => g.id === gid.value))
async function load() { groups.value = await api.get('/user/watchlist'); if (!cur.value) gid.value = groups.value[0]?.id }
const q = useQuotes(computed(() => cur.value ? cur.value.items.map(i => i.symbol) : []), 3000)
function lv(i) { return q[i.symbol] || i }
async function add(s) { if (cur.value.items.find(i => i.symbol === s.symbol)) return; await api.post('/user/watchlist/toggle', { symbol: s.symbol, group_id: gid.value }); load() }
async function remove(i) { await api.post('/user/watchlist/toggle', { symbol: i.symbol, group_id: gid.value }); load() }
async function newGroup() { const n = window.prompt('그룹 이름'); if (n) { const r = await api.post('/user/watchlist/groups', { name: n }); await load(); gid.value = r.id } }
async function rename() { const n = window.prompt('새 이름', cur.value.name); if (n) { await api.put(`/user/watchlist/groups/${gid.value}`, { name: n }); load() } }
async function removeGroup() { if (window.confirm('그룹을 삭제할까요?')) { await api.del(`/user/watchlist/groups/${gid.value}`); gid.value = null; load() } }
load()
</script>
