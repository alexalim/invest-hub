<template>
  <div>
    <div class="card" style="margin-bottom:12px;background:var(--panel-2)">
      <input v-if="kind !== 'timeline'" v-model="f.title" placeholder="제목" style="width:100%;margin-bottom:6px" />
      <textarea v-model="f.body" :rows="kind === 'timeline' ? 3 : 6" :placeholder="placeholder" />
      <div class="row between" style="margin-top:6px">
        <div class="row wrap">
          <span v-for="s in f.symbols" :key="s" class="chip blue">{{ names[s] || s }} <button class="ghost sm" style="padding:0 2px" @click="f.symbols = f.symbols.filter(x => x !== s)">✕</button></span>
          <SymbolSearch v-if="!symbol" placeholder="종목 태그" style="width:180px" @select="s => { if (!f.symbols.includes(s.symbol)) { f.symbols.push(s.symbol); names[s.symbol] = s.name } }" />
        </div>
        <button class="primary" :disabled="!f.body.trim()" @click="submit">올리기</button>
      </div>
    </div>
    <div v-if="!posts" class="spinner" />
    <div v-else-if="!posts.length" class="empty">아직 글이 없습니다</div>
    <div v-for="p in posts" :key="p.id" class="list-item">
      <div class="row between"><div class="row"><b>{{ p.nickname }}</b><span class="tiny faint">{{ ago(p.created_at) }}</span></div>
        <button v-if="p.mine || session.user?.is_admin" class="ghost sm danger" @click="remove(p)">삭제</button></div>
      <router-link v-if="p.title" :to="'/community/post/' + p.id" class="link" style="font-weight:700;display:block;margin:4px 0">{{ p.title }}</router-link>
      <div class="prose" :class="{ clamp: kind !== 'timeline' }">{{ p.body }}</div>
      <div class="row wrap" style="margin-top:6px">
        <router-link v-for="s in p.symbols" :key="s" :to="'/stock/' + s" class="chip blue">{{ p.symbol_names[s] || s }}</router-link>
        <button class="ghost sm" @click="like(p)">{{ p.liked ? '♥' : '♡' }} {{ p.likes }}</button>
        <router-link :to="'/community/post/' + p.id" class="small muted">댓글 {{ p.comments }}</router-link>
      </div>
    </div>
    <button v-if="posts && posts.length === 30 * page" class="sm" style="margin-top:10px" @click="more">더 보기</button>
  </div>
</template>
<script setup>
import { computed, reactive, ref } from 'vue'
import SymbolSearch from './SymbolSearch.vue'
import { api, session } from '../lib/api'
import { ago } from '../lib/fmt'

const props = defineProps({ kind: { type: String, default: 'timeline' }, symbol: String })
const posts = ref(null); const page = ref(1)
const names = reactive({})
const f = reactive({ title: '', body: '', symbols: props.symbol ? [props.symbol] : [] })
const placeholder = computed(() => ({ timeline: '시장과 종목에 대한 생각을 짧게 남겨 보세요', insight: '분석 글을 써 보세요. 근거와 출처를 함께 적으면 좋습니다', discussion: '스타트업·투자 시장에 대해 토론할 주제를 올려 보세요' })[props.kind])
async function load() { posts.value = await api.get('/community/posts', { kind: props.kind, symbol: props.symbol, page: 1 }) ; page.value = 1 }
async function more() { page.value++; posts.value.push(...await api.get('/community/posts', { kind: props.kind, symbol: props.symbol, page: page.value })) }
async function submit() { await api.post('/community/posts', { kind: props.kind, ...f }); f.title = ''; f.body = ''; f.symbols = props.symbol ? [props.symbol] : []; load() }
async function like(p) { const r = await api.post(`/community/posts/${p.id}/like`); p.likes = r.likes; p.liked = !p.liked }
async function remove(p) { if (confirmDelete()) { await api.del(`/community/posts/${p.id}`); load() } }
function confirmDelete() { return window.confirm("이 글을 삭제할까요?") }
load()
</script>
<style scoped>.clamp { display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }</style>
