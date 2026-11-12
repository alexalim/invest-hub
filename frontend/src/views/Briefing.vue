<template>
  <div>
    <div class="page-h"><div><h1>아침 브리핑</h1><div class="muted small">밤사이 미국 시장과 지금 선물, 어제 한국 수급을 한 장으로 모았습니다. 사람이 쓴 해설이 아니라 숫자를 규칙대로 문장으로 옮긴 것입니다.</div></div>
      <button class="sm" :disabled="busy" @click="load">{{ busy ? '불러오는 중…' : '새로 고침' }}</button></div>
    <Loading v-if="!d" />
    <template v-else>
      <div class="card">
        <h3>한눈에 보기 <span class="small muted">{{ mdhm(d.at) }} 기준</span></h3>
        <ul class="lines"><li v-for="(l, i) in d.lines" :key="i">{{ l }}</li></ul>
      </div>
      <div v-for="g in GROUPS" :key="g[0]" style="margin-top:14px">
        <h2>{{ g[1] }}</h2>
        <div class="tiles">
          <router-link v-for="m in d[g[0]]" :key="m.symbol" :to="'/stock/' + m.symbol" class="card tile">
            <div class="small muted">{{ m.name }}</div><div class="v">{{ macro(m.price, m.symbol) }}</div>
            <div class="small" :class="cls(m.change_pct)">{{ pct(m.change_pct) }}</div>
          </router-link>
        </div>
      </div>
      <div class="grid g2" style="margin-top:14px">
        <div class="card flush" v-for="s in MOVERS" :key="s[0]">
          <div style="padding:12px 12px 0"><h3>{{ s[1] }}</h3><div class="tiny faint">미국 시가총액 상위 150종목 안에서</div></div>
          <QuoteTable :rows="d[s[0]]" :columns="['price', 'change_pct', 'mcap']" />
        </div>
        <div class="card flush" v-for="s in SECTORS" :key="s[0]">
          <div style="padding:12px 12px 0"><h3>{{ s[1] }}</h3><div class="tiny faint">시가총액으로 가중한 평균 등락률</div></div>
          <table class="t"><thead><tr><th>업종</th><th class="num">등락</th><th class="num">종목 수</th></tr></thead>
            <tbody><tr v-for="x in d[s[0]]" :key="x.sector"><td>{{ x.sector }}</td><td class="num" :class="cls(x.change_pct)">{{ pct(x.change_pct) }}</td><td class="num">{{ x.n }}</td></tr></tbody></table>
        </div>
      </div>
      <div class="grid g2" style="margin-top:12px">
        <div class="card">
          <div class="card-h"><h3>수급·심리</h3><router-link to="/market/flow" class="link small">수급 자세히</router-link></div>
          <table class="t"><thead><tr><th>시장</th><th class="num">외국인</th><th class="num">기관</th><th class="num">개인</th></tr></thead>
            <tbody><tr v-for="(f, mk) in d.flows" :key="mk"><td>{{ mk === 'KOSPI' ? '코스피' : '코스닥' }} <span class="tiny faint">{{ md(f.date) }}</span></td>
              <td class="num" :class="cls(f.foreigner)">{{ signed(f.foreigner) }}</td><td class="num" :class="cls(f.institution)">{{ signed(f.institution) }}</td>
              <td class="num" :class="cls(f.individual)">{{ signed(f.individual) }}</td></tr></tbody></table>
          <div class="row wrap" style="margin-top:10px;gap:14px">
            <router-link v-if="d.risk" to="/market/risk" class="stat"><span class="k">미국 위험 점수</span><span class="v">{{ d.risk.score }} <span class="small muted">{{ d.risk.level }}</span></span></router-link>
            <router-link v-if="d.feargreed?.score != null" to="/market/risk" class="stat"><span class="k">코스피 공포·탐욕</span><span class="v">{{ d.feargreed.score }} <span class="small muted">{{ d.feargreed.label }}</span></span></router-link>
          </div>
        </div>
        <div class="card">
          <div class="card-h"><h3>주요 뉴스</h3><router-link to="/market/news" class="link small">더 보기</router-link></div>
          <a v-for="n in d.news" :key="n.url" :href="n.url" target="_blank" rel="noopener" class="list-item" style="display:block">{{ n.title }}</a>
          <div v-if="!d.news.length" class="empty">뉴스를 받지 못했습니다</div>
        </div>
      </div>
    </template>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import QuoteTable from '../components/QuoteTable.vue'
import { api } from '../lib/api'
import { cls, macro, md, mdhm, pct, signed } from '../lib/fmt'
const GROUPS = [['us_index', '미국 증시 (마감)'], ['futures', '지금 선물 · 한국 ETF'], ['rates', '금리 · 환율 · 원자재'], ['asia', '한국 · 아시아']]
const MOVERS = [['up', '미국 대형주 상승 상위'], ['down', '미국 대형주 하락 상위']]
const SECTORS = [['sectors', '미국 강한 업종'], ['sectors_weak', '미국 약한 업종']]
const d = ref(null); const busy = ref(false)
async function load() { busy.value = true; try { d.value = await api.get('/pulse/briefing') } finally { busy.value = false } }
load()
</script>
<style scoped>
.lines { margin: 6px 0 0 18px; padding: 0; line-height: 1.8; }
</style>
