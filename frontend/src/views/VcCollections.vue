<template>
  <div>
    <div class="page-h"><div><h1>컬렉션</h1><div class="muted small">기업·투자자를 직접 담는 컬렉션과, 조건에 맞는 기업이 자동으로 채워지는 스마트 컬렉션</div></div>
      <button class="primary" @click="create">+ 컬렉션</button></div>
    <div class="grid g3">
      <router-link v-for="c in rows" :key="c.id" :to="'/vc/collections/' + c.id" class="card">
        <div class="row between"><b>{{ c.name }}</b><span class="chip" :class="c.smart_spec ? 'orange' : 'blue'">{{ c.smart_spec ? '스마트' : '일반' }}</span></div>
        <div class="small muted">{{ c.description }}</div><div class="small" style="margin-top:6px">{{ c.count }}개</div>
      </router-link>
      <div v-if="!rows.length" class="card empty">컬렉션이 없습니다. 기업 화면의 '컬렉션에 담기'나 스타트업 목록의 '스마트 컬렉션으로'로 만들 수 있습니다.</div>
    </div>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { api } from '../lib/api'
const rows = ref([])
async function load() { rows.value = await api.get('/vc/collections') }
async function create() { const n = window.prompt('컬렉션 이름'); if (n) { await api.post('/vc/collections', { name: n }); load() } }
load()
</script>
