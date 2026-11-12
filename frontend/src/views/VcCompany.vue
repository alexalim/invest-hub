<template>
  <div v-if="d">
    <router-link to="/vc/companies" class="small link">← 스타트업 목록</router-link>
    <div class="page-h" style="margin-top:6px">
      <div><div class="row wrap"><h1>{{ c.name }}</h1><span v-if="c.category" class="chip blue">{{ c.category }}</span><span v-if="c.last_round" class="chip">{{ c.last_round }}</span>
        <span v-if="c.foreign_co" class="chip orange">해외</span><span v-if="c.stock_code" class="chip green">상장 {{ c.stock_code }}</span></div>
        <div class="muted small" style="max-width:760px">{{ c.description || '소개 문구가 아직 없습니다' }}</div></div>
      <div class="row wrap">
        <router-link v-if="c.stock_code" :to="'/stock/KR:' + c.stock_code" class="btn">주가 보기</router-link>
        <a v-if="c.homepage" :href="c.homepage.startsWith('http') ? c.homepage : 'http://' + c.homepage" target="_blank" rel="noopener" class="btn">홈페이지</a>
        <button class="sm" :disabled="busy" @click="enrich">{{ busy ? '불러오는 중…' : '공시·재무·고용 정보 불러오기' }}</button>
        <CollectButton type="company" :id="c.id" :initial="d.collections" />
        <router-link :to="{ path: '/vc/compare', query: { ids: [c.id, ...d.similar.slice(0, 3).map(s => s.id)].join(',') } }" class="btn">유사 기업과 비교</router-link>
      </div>
    </div>
    <div v-if="log.length" class="notice small" style="margin-bottom:12px">{{ log.join(' · ') }}</div>
    <div class="grid g4">
      <div class="card stat"><span class="k">누적 투자 유치 (공개분)</span><span class="v">{{ c.total_raised ? won(c.total_raised) : '-' }}</span><span class="tiny faint">{{ c.deal_count }}회</span></div>
      <div class="card stat"><span class="k">기업가치 (보도 기준)</span><span class="v">{{ c.valuation ? won(c.valuation) : '-' }}</span></div>
      <div class="card stat"><span class="k">설립 · 대표</span><span class="v" style="font-size:15px">{{ c.founded || '-' }} · {{ c.ceo || '-' }}</span></div>
      <div class="card stat"><span class="k">임직원 (국민연금 기준)</span><span class="v">{{ c.employees ? num(c.employees) + '명' : '-' }}</span><span class="tiny faint ellipsis">{{ c.address }}</span></div>
    </div>
    <div class="grid g-side" style="margin-top:12px">
      <div class="col" style="gap:12px">
        <div class="card flush"><div style="padding:12px 12px 0"><h3>투자 유치 이력</h3></div><DealTable :rows="d.deals" hide-company /></div>
        <div class="card" v-if="d.financials.length">
          <h3>재무 ({{ d.financials[d.financials.length - 1].source }})</h3>
          <div class="scroll-x"><table class="t"><thead><tr><th>연도</th><th class="num">매출</th><th class="num">영업이익</th><th class="num">순이익</th><th class="num">자산</th><th class="num">부채</th><th class="num">자본</th><th class="num">현금</th></tr></thead>
            <tbody><tr v-for="f in d.financials" :key="f.year"><td>{{ f.year }}</td><td class="num">{{ won(f.revenue) }}</td><td class="num" :class="cls(f.op_income)">{{ won(f.op_income) }}</td><td class="num" :class="cls(f.net_income)">{{ won(f.net_income) }}</td>
              <td class="num">{{ won(f.assets) }}</td><td class="num">{{ won(f.liabilities) }}</td><td class="num">{{ won(f.equity) }}</td><td class="num">{{ won(f.cash) }}</td></tr></tbody></table></div>
          <MiniChart type="bar" :series="[{ values: d.financials.map(f => f.revenue || 0), color: 'var(--accent)' }]" :labels="d.financials.map(f => f.year)" :h="100" />
        </div>
        <div class="card" v-if="d.analysis">
          <h3>재무 분석 <span class="small muted">({{ d.analysis.year }}년 기준, 규칙 기반 해설)</span></h3>
          <div class="grid g4" style="margin-bottom:8px">
            <div class="stat"><span class="k">월평균 번레이트</span><span class="v" style="font-size:16px">{{ d.analysis.burn_monthly ? won(d.analysis.burn_monthly) : '흑자' }}</span></div>
            <div class="stat"><span class="k">예상 런웨이</span><span class="v" style="font-size:16px">{{ d.analysis.runway_months ? num(d.analysis.runway_months) + '개월' : '-' }}</span></div>
            <div class="stat"><span class="k">유동비율</span><span class="v" style="font-size:16px">{{ d.analysis.current_ratio ? num(d.analysis.current_ratio) + '%' : '-' }}</span></div>
            <div class="stat"><span class="k">매출 성장률</span><span class="v" style="font-size:16px" :class="cls(d.analysis.revenue_growth)">{{ pct(d.analysis.revenue_growth, 1) }}</span></div>
          </div>
          <ul class="small" style="margin:0;padding-left:18px"><li v-for="n in d.analysis.notes" :key="n">{{ n }}</li></ul>
        </div>
        <div class="card" v-if="d.employment.length"><h3>고용 추이</h3>
          <MiniChart :series="[{ values: d.employment.map(e => e.total), color: 'var(--accent)' }]" :h="110" />
          <div class="row between tiny faint"><span>{{ d.employment[0].ym }}</span><span>{{ d.employment[d.employment.length - 1].ym }}</span></div></div>
        <div class="card"><h3>관련 뉴스</h3>
          <div v-if="!d.news.length" class="small muted">연결된 기사가 없습니다</div>
          <a v-for="n in d.news" :key="n.id" :href="n.url" target="_blank" rel="noopener" class="list-item" style="display:block">
            <div class="row"><span class="chip" :class="SENT[n.sentiment][1]">{{ SENT[n.sentiment][0] }}</span><b class="small">{{ n.title }}</b></div>
            <div class="tiny faint">{{ n.source }} · {{ n.published }}</div></a></div>
        <div class="card" v-if="d.filings.length"><h3>전자공시</h3>
          <a v-for="f in d.filings" :key="f.url" :href="f.url" target="_blank" rel="noopener" class="row between small list-item"><span>{{ f.title }}</span><span class="faint">{{ f.date }}</span></a></div>
      </div>
      <div class="col" style="gap:12px">
        <div class="card"><h3>투자자</h3>
          <div v-for="i in d.investors" :key="i.id" class="row between small" style="padding:3px 0"><router-link :to="'/vc/investors/' + i.id" class="link">{{ i.name }}</router-link><span class="faint">{{ i.type }} · {{ i.n }}회</span></div>
          <div v-if="!d.investors.length" class="small muted">기사에서 투자자를 찾지 못했습니다</div></div>
        <div class="card"><h3>같은 분야 비슷한 규모</h3>
          <router-link v-for="s in d.similar" :key="s.id" :to="'/vc/companies/' + s.id" class="row between small list-item"><span>{{ s.name }}</span><span class="faint">{{ s.last_round || '' }} {{ won(s.total_raised) }}</span></router-link>
          <div v-if="!d.similar.length" class="small muted">없습니다</div></div>
        <div class="card"><h3>기본 정보</h3>
          <dl class="kv"><dt>사업자번호</dt><dd>{{ c.bizno || '-' }}</dd><dt>법인번호</dt><dd>{{ c.extra?.jurir_no || '-' }}</dd><dt>DART 코드</dt><dd>{{ c.corp_code || '-' }}</dd>
            <dt>정보 갱신</dt><dd>{{ c.enriched_at ? datetime(c.enriched_at) : '-' }}</dd></dl>
          <div class="tiny faint" style="margin-top:6px">특허·국가 R&D·공공조달·등기 임원·웹 트래픽은 아직 연동하지 않았습니다.</div></div>
      </div>
    </div>
  </div>
  <Loading v-else />
</template>
<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import CollectButton from '../components/CollectButton.vue'
import DealTable from '../components/DealTable.vue'
import MiniChart from '../components/MiniChart.vue'
import { api } from '../lib/api'
import { cls, datetime, num, pct, won } from '../lib/fmt'
const route = useRoute(); const d = ref(null); const busy = ref(false); const log = ref([])
const c = computed(() => d.value.company)
const SENT = { positive: ['긍정', 'red'], negative: ['부정', 'bluedown'], neutral: ['중립', ''] }
async function load() { d.value = await api.get(`/vc/companies/${route.params.id}`) }
async function enrich() { busy.value = true; try { const r = await api.post(`/vc/companies/${route.params.id}/enrich`); log.value = r.log; await load() } finally { busy.value = false } }
load()
</script>
