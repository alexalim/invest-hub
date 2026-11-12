<template>
  <div v-if="d">
    <router-link to="/vc/investors" class="small link">← 투자자 목록</router-link>
    <div class="page-h" style="margin-top:6px"><div><div class="row"><h1>{{ d.investor.name }}</h1><span class="chip blue">{{ d.investor.type }}</span></div>
      <div class="muted small">투자 {{ d.investor.deal_count }}건 · 참여 라운드 합계 {{ won(d.investor.total_amount) }} · 최근 {{ d.investor.last_deal_date }}</div></div>
      <CollectButton type="investor" :id="d.investor.id" /></div>
    <div class="grid g3">
      <div class="card"><h3>연도별</h3><MiniChart type="bar" :series="[{ values: d.by_year.map(y => y.n), color: 'var(--accent)' }]" :labels="d.by_year.map(y => y.year)" :h="100" />
        <div class="row between tiny faint"><span>{{ d.by_year[0]?.year }}</span><span>{{ d.by_year[d.by_year.length - 1]?.year }}</span></div></div>
      <div class="card"><h3>단계별</h3><div v-for="r in d.by_round" :key="r.round" class="row between small"><span>{{ r.round }}</span><span>{{ r.n }}건</span></div></div>
      <div class="card"><h3>분야별</h3><div v-for="r in d.by_category" :key="r.category" class="row between small"><span>{{ r.category }}</span><span>{{ r.n }}건</span></div></div>
    </div>
    <div class="grid g-side" style="margin-top:12px">
      <div class="card flush"><div style="padding:12px 12px 0"><h3>포트폴리오 (투자 이력)</h3></div><DealTable :rows="d.deals" /></div>
      <div class="col" style="gap:12px">
        <div class="card"><h3>공동 투자자</h3>
          <router-link v-for="r in d.co_investors" :key="r.id" :to="'/vc/investors/' + r.id" class="row between small list-item"><span>{{ r.name }}</span><span class="faint">{{ r.n }}회</span></router-link>
          <div v-if="!d.co_investors.length" class="small muted">없습니다</div></div>
        <div class="card"><h3>결성 펀드</h3>
          <a v-for="f in d.funds" :key="f.id" :href="f.source_url" target="_blank" rel="noopener" class="list-item" style="display:block"><b class="small">{{ f.name }}</b><div class="tiny faint">{{ f.date }} · {{ f.size ? won(f.size) : f.size_text || '규모 미상' }}</div></a>
          <div v-if="!d.funds.length" class="small muted">없습니다</div></div>
      </div>
    </div>
  </div>
  <div v-else class="spinner" />
</template>
<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import CollectButton from '../components/CollectButton.vue'
import DealTable from '../components/DealTable.vue'
import MiniChart from '../components/MiniChart.vue'
import { api } from '../lib/api'
import { won } from '../lib/fmt'
const route = useRoute(); const d = ref(null)
api.get(`/vc/investors/${route.params.id}`).then(r => (d.value = r))
</script>
