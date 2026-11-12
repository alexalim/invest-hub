<template>
  <div>
    <div class="page-h"><div><h1>공시 속보</h1><div class="muted small">금융감독원 전자공시(DART)에 올라온 상장사 공시를 종류별로 모았습니다. 제목을 누르면 원문이 열립니다.</div></div>
      <div class="row wrap"><label class="row small" style="gap:4px"><input type="checkbox" v-model="mine" /> 내 관심종목만</label>
        <input v-model.trim="q" placeholder="회사·제목 검색" aria-label="회사·제목 검색" style="width:180px" @keyup.enter="reload" /></div></div>
    <div class="row wrap" style="gap:6px;margin-bottom:10px">
      <button class="sm" :class="{ primary: cat === '' }" @click="cat = ''">주요 공시</button>
      <button v-for="c in cats" :key="c.cat" class="sm" :class="{ primary: cat === c.cat }" @click="cat = c.cat">{{ names[c.cat] || c.cat }} <span class="tiny">{{ c.n }}</span></button>
    </div>
    <Loading v-if="!d" />
    <div v-else class="card flush">
      <div class="scroll-x"><table class="t">
        <thead><tr><th>시각</th><th>회사</th><th>종류</th><th>제목</th><th class="num">현재가</th><th class="num">오늘</th></tr></thead>
        <tbody><tr v-for="r in d.rows" :key="r.rcept_no">
          <td class="small muted nowrap">{{ mdhm(r.at) }}</td>
          <td class="nowrap"><SymLink v-if="r.symbol" :symbol="r.symbol" :name="r.corp" hide-code /><span v-else>{{ r.corp }} <span class="tiny faint">{{ r.market }}</span></span></td>
          <td><span class="chip" :class="CHIP[r.cat]">{{ names[r.cat] }}</span></td>
          <td class="title"><a :href="'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=' + r.rcept_no" target="_blank" rel="noopener" class="link">{{ r.title }}</a></td>
          <td class="num">{{ r.price == null ? '-' : num(r.price) }}</td><td class="num" :class="cls(r.change_pct)">{{ r.change_pct == null ? '-' : pct(r.change_pct) }}</td></tr>
          <tr v-if="!d.rows.length"><td colspan="6" class="empty">{{ mine ? '관심종목의 공시가 아직 없습니다' : '해당하는 공시가 없습니다' }}</td></tr></tbody></table></div>
      <Pager v-model="page" :total="d.total" :size="50" />
    </div>
    <div class="tiny faint" style="margin-top:10px">
      {{ d?.since ? mdhm(d.since) + '부터 쌓인 ' : '' }}공시입니다. 서버가 켜져 있는 동안 2분마다 최근 공시를 읽어 모으며, 꺼져 있던 시간의 공시는 빠질 수 있습니다.
      <template v-if="d && !d.has_key"> 설정에서 DART 인증키를 넣으면 지난 30일치를 한꺼번에 채웁니다(이 경로는 키가 없어 아직 실제로 시험하지 못했습니다).</template>
      '주요 공시'에는 건수만 많은 정기보고서와 증권 발행 서류를 뺐습니다.
    </div>
  </div>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import Pager from '../components/Pager.vue'
import SymLink from '../components/SymLink.vue'
import { api } from '../lib/api'
import { cls, mdhm, num, pct } from '../lib/fmt'
const CHIP = { major: 'orange', guarantee: 'orange', holder5: 'blue', insider: 'blue', buyback: 'green', earnings: 'orange', contract: 'green', capital: 'red', warning: 'red', deal: 'orange' }
const d = ref(null); const cat = ref(''); const q = ref(''); const mine = ref(false); const page = ref(1)
const cats = computed(() => d.value?.cats || []); const names = computed(() => d.value?.names || {})
async function load() { d.value = await api.get('/pulse/disclosures', { cat: cat.value, q: q.value, page: page.value, mine: mine.value }) }
function reload() { if (page.value !== 1) page.value = 1; else load() }
watch([cat, mine], reload, { immediate: true })
watch(page, load)
</script>
<style scoped>.nowrap { white-space: nowrap; } td.title { min-width: 240px; }</style>
