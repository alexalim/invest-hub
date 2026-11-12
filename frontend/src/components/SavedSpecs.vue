<template>
  <div class="row wrap">
    <select aria-label="저장한 설정 불러오기" @change="e => { pick(e.target.value); e.target.value = '' }"><option value="">저장한 {{ label }} 불러오기…</option>
      <option v-for="s in items" :key="s.id" :value="s.id">{{ s.name }}</option></select>
    <button class="sm" @click="save">현재 {{ label }} 저장</button>
    <button v-if="current" class="sm ghost danger" @click="remove">"{{ current.name }}" 삭제</button>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { api, toast } from '../lib/api'
const props = defineProps({ kind: String, label: String, spec: Object })
const emit = defineEmits(['load'])
const items = ref([]); const current = ref(null)
async function load() { items.value = await api.get(`/discover/saved/${props.kind}`) }
function pick(id) { const s = items.value.find(x => x.id === +id); if (s) { current.value = s; emit('load', JSON.parse(JSON.stringify(s.spec))) } }
async function save() {
  const name = window.prompt(`${props.label} 이름`, current.value?.name || '')
  if (!name) return
  const r = await api.post(`/discover/saved/${props.kind}`, { id: current.value?.name === name ? current.value.id : undefined, name, spec: props.spec })
  toast('저장했습니다', 'ok'); await load(); current.value = items.value.find(x => x.id === r.id)
}
async function remove() { await api.del(`/discover/saved/${props.kind}/${current.value.id}`); current.value = null; load() }
load()
</script>
