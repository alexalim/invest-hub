<template>
  <div class="cb">
    <button class="sm" @click="open = !open">📁 컬렉션에 담기</button>
    <div v-if="open" class="card dd">
      <div v-for="c in cols" :key="c.id" class="row small" style="padding:3px 0"><label class="row"><input type="checkbox" :checked="inSet.includes(c.id)" @change="toggle(c)" />{{ c.name }}</label></div>
      <div v-if="!cols.length" class="small muted">컬렉션이 없습니다</div>
      <div class="row" style="margin-top:6px"><input v-model="nm" placeholder="새 컬렉션" class="grow" /><button class="sm" @click="create">추가</button></div>
    </div>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { api, toast } from '../lib/api'
const props = defineProps({ type: String, id: Number, initial: { type: Array, default: () => [] } })
const open = ref(false); const cols = ref([]); const inSet = ref([...props.initial]); const nm = ref('')
async function load() { cols.value = (await api.get('/vc/collections')).filter(c => !c.smart_spec) }
async function toggle(c) { const r = await api.post(`/vc/collections/${c.id}/toggle`, { entity_type: props.type, entity_id: props.id }); inSet.value = r.added ? [...inSet.value, c.id] : inSet.value.filter(x => x !== c.id); toast(r.added ? `'${c.name}'에 담았습니다` : '뺐습니다', 'ok') }
async function create() { if (!nm.value) return; const r = await api.post('/vc/collections', { name: nm.value }); nm.value = ''; await load(); toggle(cols.value.find(c => c.id === r.id)) }
load()
</script>
<style scoped>.cb { position: relative; } .dd { position: absolute; right: 0; top: 34px; z-index: 20; width: 240px; }</style>
