<template>
  <div v-if="p" class="col" style="max-width:820px">
    <router-link :to="back" class="small link">← 목록</router-link>
    <div class="card">
      <h1 v-if="p.title">{{ p.title }}</h1>
      <div class="row small muted" style="margin-bottom:10px"><b>{{ p.nickname }}</b><span>{{ datetime(p.created_at) }}</span></div>
      <template v-if="editing">
        <input aria-label="제목" v-if="p.kind !== 'timeline'" v-model="p.title" style="width:100%;margin-bottom:6px" />
        <textarea v-model="p.body" rows="10" />
        <div class="row" style="margin-top:6px"><button class="primary" @click="saveEdit">저장</button><button @click="editing = false; load()">취소</button></div>
      </template>
      <div v-else class="prose">{{ p.body }}</div>
      <div class="row wrap" style="margin-top:10px">
        <router-link v-for="s in p.symbols" :key="s" :to="'/stock/' + s" class="chip blue">{{ p.symbol_names[s] || s }}</router-link>
        <button class="ghost sm" @click="like">{{ p.liked ? '♥' : '♡' }} {{ p.likes }}</button>
        <button v-if="p.mine && !editing" class="ghost sm" @click="editing = true">수정</button>
      </div>
    </div>
    <div class="card">
      <h3>댓글 {{ p.comment_list.length }}</h3>
      <div v-for="c in p.comment_list" :key="c.id" class="list-item">
        <div class="row between"><div class="row"><b class="small">{{ c.nickname }}</b><span class="tiny faint">{{ ago(c.created_at) }}</span></div>
          <button v-if="c.mine" class="ghost sm danger" @click="delComment(c)">삭제</button></div>
        <div class="prose small">{{ c.body }}</div>
      </div>
      <div class="row" style="margin-top:8px"><input v-model="comment" class="grow" placeholder="댓글 쓰기" @keydown.enter="addComment" /><button class="primary" @click="addComment">등록</button></div>
    </div>
  </div>
</template>
<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../lib/api'
import { ago, datetime } from '../lib/fmt'
const route = useRoute()
const p = ref(null); const comment = ref(''); const editing = ref(false)
const back = computed(() => ({ timeline: '/community/timeline', insight: '/community/insight', discussion: '/vc/discussions' })[p.value?.kind] || '/community/timeline')
async function load() { p.value = await api.get(`/community/posts/${route.params.id}`) }
async function like() { const r = await api.post(`/community/posts/${p.value.id}/like`); p.value.likes = r.likes; p.value.liked = !p.value.liked }
async function addComment() { if (!comment.value.trim()) return; await api.post(`/community/posts/${p.value.id}/comments`, { body: comment.value }); comment.value = ''; load() }
async function delComment(c) { await api.del(`/community/comments/${c.id}`); load() }
async function saveEdit() { await api.post('/community/posts', { id: p.value.id, kind: p.value.kind, title: p.value.title, body: p.value.body, symbols: p.value.symbols }); editing.value = false; load() }
load()
</script>
