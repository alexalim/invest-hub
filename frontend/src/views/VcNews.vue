<template>
  <div>
    <div class="page-h"><div><h1>스타트업 뉴스</h1><div class="muted small">스타트업 매체와 뉴스 검색에서 모은 기사 {{ d ? num(d.total) + '건' : '' }}. 주제와 긍·부정은 제목 기준 자동 분류입니다.</div></div></div>
    <div class="card" style="margin-bottom:12px"><div class="row wrap">
      <input v-model="f.q" placeholder="제목 검색" style="width:200px" />
      <div class="seg"><button v-for="k in KINDS" :key="k[0]" :class="{ on: f.kind === k[0] }" @click="f.kind = k[0]">{{ k[1] }}</button></div>
      <div class="seg"><button v-for="s in SENTS" :key="s[0]" :class="{ on: f.sentiment === s[0] }" @click="f.sentiment = s[0]">{{ s[1] }}</button></div>
    </div></div>
    <div class="card"><div v-if="!d" class="spinner" />
      <div v-for="n in d?.rows || []" :key="n.id" class="list-item">
        <div class="row wrap"><span class="chip">{{ KL[n.kind] }}</span><span class="chip" :class="n.sentiment === 'positive' ? 'red' : n.sentiment === 'negative' ? 'bluedown' : ''">{{ SL[n.sentiment] }}</span>
          <a :href="n.url" target="_blank" rel="noopener" style="font-weight:600">{{ n.title }}</a></div>
        <div class="small muted" v-if="n.summary">{{ n.summary.slice(0, 160) }}</div>
        <div class="row wrap tiny faint"><span>{{ n.source }} · {{ n.published }}</span><router-link v-for="c in n.companies" :key="c.id" :to="'/vc/companies/' + c.id" class="chip blue">{{ c.name }}</router-link></div>
      </div></div>
    <Pager v-model="page" :total="d?.total || 0" />
  </div>
</template>
<script setup>
import { reactive, ref, watch } from 'vue'
import Pager from '../components/Pager.vue'
import { api } from '../lib/api'
import { num } from '../lib/fmt'
const KINDS = [['', '전체'], ['funding', '투자'], ['mna', 'M&A'], ['fund', '펀드'], ['general', '일반']]
const KL = { funding: '투자', mna: 'M&A', fund: '펀드', general: '일반' }; const SL = { positive: '긍정', negative: '부정', neutral: '중립' }
const SENTS = [['', '전체'], ['positive', '긍정'], ['negative', '부정'], ['neutral', '중립']]
const f = reactive({ q: '', kind: '', sentiment: '' }); const page = ref(1); const d = ref(null); let t
async function load() { d.value = await api.get('/vc/news', { ...f, page: page.value }) }
watch(f, () => { clearTimeout(t); t = setTimeout(() => { page.value = 1; load() }, 300) }, { deep: true }); watch(page, load); load()
</script>
