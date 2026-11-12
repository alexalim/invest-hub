<template>
  <div class="ss" @keydown.down.prevent="move(1)" @keydown.up.prevent="move(-1)" @keydown.enter.prevent="pick(items[cur])" @keydown.esc="open = false">
    <input v-model="q" :placeholder="placeholder" @input="search" @focus="open = !!items.length" @blur="onBlur" />
    <div v-if="open && items.length" class="dd card flush">
      <div v-for="(s, i) in items" :key="s.symbol" class="it" :class="{ cur: i === cur }" @mousedown.prevent="pick(s)">
        <div class="sym"><b>{{ s.name }}</b><span>{{ s.code }} · {{ MARKET_LABEL[s.market] || s.market }}{{ s.kind && s.kind !== 'stock' && s.kind !== 'crypto' ? ' · ' + s.kind.toUpperCase() : '' }}</span></div>
        <div class="num small"><div>{{ price(s.price, s.currency) }}</div><div :class="cls(s.change_pct)">{{ pct(s.change_pct) }}</div></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '../lib/api'
import { cls, MARKET_LABEL, pct, price } from '../lib/fmt'

defineProps({ placeholder: { type: String, default: '종목 검색' } })
const emit = defineEmits(['select'])
const q = ref('')
const items = ref([])
const open = ref(false)
const cur = ref(0)
let t = null
function search() {
  clearTimeout(t)
  t = setTimeout(async () => {
    if (!q.value.trim()) { items.value = []; open.value = false; return }
    items.value = await api.get('/search', { q: q.value, limit: 12 }, { quiet: true }).catch(() => [])
    cur.value = 0
    open.value = true
  }, 160)
}
function onBlur() { setTimeout(() => (open.value = false), 150) }
function move(d) { if (items.value.length) cur.value = (cur.value + d + items.value.length) % items.value.length }
function pick(s) { if (!s) return; emit('select', s); q.value = ''; items.value = []; open.value = false }
</script>

<style scoped>
.ss { position: relative; } .ss input { width: 100%; }
.dd { position: absolute; left: 0; right: 0; top: calc(100% + 4px); z-index: 30; max-height: 420px; overflow-y: auto; }
.it { display: flex; justify-content: space-between; gap: 10px; padding: 8px 12px; cursor: pointer; }
.it.cur, .it:hover { background: var(--panel-2); }
</style>
