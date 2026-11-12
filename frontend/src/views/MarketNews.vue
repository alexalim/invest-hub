<template>
  <div>
    <div class="page-h"><div><h1>시장 뉴스</h1><div class="muted small">증시 주요 뉴스</div></div>
      <div class="seg"><button v-for="c in CATS" :key="c[0]" :class="{ on: cat === c[0] }" @click="cat = c[0]">{{ c[1] }}</button></div></div>
    <div class="card">
      <Loading v-if="!items" />
      <div v-else-if="!items.length" class="empty">뉴스가 없습니다</div>
      <a v-for="n in items" :key="n.url" :href="n.url" target="_blank" rel="noopener" class="list-item row" style="align-items:flex-start;gap:12px">
        <img v-if="n.image" :src="n.image" alt="" class="thumb" loading="lazy" referrerpolicy="no-referrer" />
        <div class="grow"><div style="font-weight:700">{{ n.title }}</div><div class="small muted clamp">{{ n.summary }}</div><div class="tiny faint">{{ n.office }} · {{ n.datetime }}</div></div>
      </a>
      <button v-if="items && items.length" class="sm" @click="more">더 보기</button>
    </div>
  </div>
</template>
<script setup>
import { ref, watch } from 'vue'
import { api } from '../lib/api'
const CATS = [['mainnews', '주요'], ['flashnews', '속보'], ['ranknews', '많이 본']]
const cat = ref('mainnews'); const items = ref(null); let page = 1
watch(cat, async () => { items.value = null; page = 1; items.value = await api.get('/market/news', { category: cat.value, page }).catch(() => []) }, { immediate: true })
async function more() { page++; items.value.push(...await api.get('/market/news', { category: cat.value, page }).catch(() => [])) }
</script>
<style scoped>
.thumb { width: 110px; height: 72px; object-fit: cover; border-radius: 6px; flex: none; }
.clamp { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
</style>
