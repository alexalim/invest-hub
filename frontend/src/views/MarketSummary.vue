<template>
  <div>
    <div class="page-h"><div><h1>시장요약</h1><div class="muted small">국내·미국·코인과 주요 지표를 한눈에. 시세는 몇 초마다 갱신됩니다.</div></div>
      <span v-if="!d" class="spinner" /></div>
    <template v-if="d">
      <div class="idx">
        <router-link v-for="m in topMacro" :key="m.symbol" :to="'/stock/' + m.symbol" class="card ic">
          <div class="small muted">{{ m.name }}</div>
          <div class="v">{{ macro(live(m).price, m.symbol) }}</div>
          <div class="small" :class="cls(live(m).change_pct)">{{ signed(live(m).change, m.symbol.startsWith('RT:') ? 3 : 2) }} ({{ pct(live(m).change_pct) }})</div>
        </router-link>
      </div>
      <div class="grid g-side" style="margin-top:12px">
        <div class="col" style="gap:12px">
          <div class="grid g2">
            <div class="card" v-for="mk in ['KOSPI', 'KOSDAQ']" :key="mk">
              <div class="card-h"><h3>{{ mk === 'KOSPI' ? '코스피' : '코스닥' }} 투자자별 순매수 (억)</h3></div>
              <div v-if="d.trends[mk]" class="row between">
                <div class="stat" v-for="k in [['individual','개인'],['foreign','외국인'],['institution','기관']]" :key="k[0]">
                  <span class="k">{{ k[1] }}</span><span class="v" style="font-size:16px" :class="cls(d.trends[mk][k[0]])">{{ signed(d.trends[mk][k[0]]) }}</span></div>
              </div>
              <div class="small muted" style="margin-top:8px" v-if="d.breadth[mk]">상승 <b class="up">{{ d.breadth[mk].up }}</b> · 하락 <b class="down">{{ d.breadth[mk].down }}</b> · 보합 {{ d.breadth[mk].flat }}</div>
              <div class="bar-bg" style="margin-top:6px" v-if="d.breadth[mk]"><div class="bar-fg" :style="{ width: (d.breadth[mk].up / ((d.breadth[mk].up + d.breadth[mk].down) || 1) * 100) + '%', background: 'var(--up)' }" /></div>
            </div>
          </div>
          <div class="card">
            <div class="card-h"><h3>{{ HEAT[heatTab] }} 히트맵</h3>
              <div class="row"><span class="small muted">색: 등락률</span>
                <div class="seg"><button :class="{ on: heatTab === 'kr' }" @click="setHeat('kr')">국내</button><button :class="{ on: heatTab === 'us' }" @click="setHeat('us')">미국</button><button :class="{ on: heatTab === 'cr' }" @click="setHeat('cr')">코인</button></div></div></div>
            <div class="heat">
              <router-link v-for="r in heatRows" :key="r.symbol" :to="'/stock/' + r.symbol" :style="{ background: heat(r.change_pct), color: Math.abs(r.change_pct || 0) < 1.5 ? 'var(--text)' : '#fff' }">
                <div class="ellipsis"><b>{{ r.name }}</b></div><div>{{ pct(r.change_pct) }}</div></router-link>
            </div>
          </div>
          <div class="grid g3">
            <div class="card flush"><div style="padding:12px 12px 0"><h3>거래대금 상위</h3></div><QuoteTable :rows="d.kr_value" :columns="['price','change_pct']" /></div>
            <div class="card flush"><div style="padding:12px 12px 0"><h3>상승률 상위</h3></div><QuoteTable :rows="d.kr_up" :columns="['price','change_pct']" /></div>
            <div class="card flush"><div style="padding:12px 12px 0"><h3>하락률 상위</h3></div><QuoteTable :rows="d.kr_down" :columns="['price','change_pct']" /></div>
          </div>
          <div class="grid g2">
            <div class="card flush"><div style="padding:12px 12px 0"><h3>미국 시가총액 상위</h3></div><QuoteTable :rows="d.us_top" :columns="['price','change_pct','mcap']" /></div>
            <div class="card flush"><div style="padding:12px 12px 0"><h3>코인 거래대금 상위</h3></div><QuoteTable :rows="cryptoLive" :columns="['price','change_pct','value']" /></div>
          </div>
        </div>
        <div class="col" style="gap:12px">
          <div class="card">
            <div class="card-h"><h3>업종 등락</h3><router-link to="/market/groups/industry" class="link small">전체</router-link></div>
            <div v-for="s in sectorsShown" :key="s.no" class="row between small" style="padding:3px 0">
              <router-link :to="`/market/groups/industry/${s.no}`" class="ellipsis grow">{{ s.name }}</router-link>
              <span class="num" :class="cls(s.change_pct)">{{ pct(s.change_pct) }}</span></div>
          </div>
          <div class="card">
            <div class="card-h"><h3>강세 테마</h3><router-link to="/market/groups/theme" class="link small">전체</router-link></div>
            <div v-for="s in d.themes_up" :key="s.no" class="row between small" style="padding:3px 0">
              <router-link :to="`/market/groups/theme/${s.no}`" class="ellipsis grow">{{ s.name }}</router-link>
              <span class="num" :class="cls(s.change_pct)">{{ pct(s.change_pct) }}</span></div>
          </div>
          <div class="card">
            <div class="card-h"><h3>주요 뉴스</h3><router-link to="/market/news" class="link small">더 보기</router-link></div>
            <a v-for="n in d.news" :key="n.url" :href="n.url" target="_blank" rel="noopener" class="list-item" style="display:block">
              <div class="small" style="font-weight:600">{{ n.title }}</div><div class="tiny faint">{{ n.office }} · {{ n.datetime }}</div></a>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import QuoteTable from '../components/QuoteTable.vue'
import { api } from '../lib/api'
import { cls, macro, pct, price, signed } from '../lib/fmt'
import { useInterval, useQuotes } from '../lib/poll'

const d = ref(null)
async function load() { d.value = await api.get('/market/summary', null, { quiet: !!d.value }) }
load()
useInterval(load, 60000)
const TOP = ['IX:KOSPI', 'IX:KOSDAQ', 'IX:SPX', 'IX:NASDAQ', 'IX:SOX', 'FX:USDKRW', 'CM:WTI', 'CM:GOLD', 'RT:US10Y']
const topMacro = computed(() => TOP.map(s => d.value.macro.find(m => m.symbol === s)).filter(Boolean))
const watchSyms = computed(() => d.value ? [...TOP, ...d.value.crypto.map(r => r.symbol)] : [])
const q = useQuotes(watchSyms, 5000)
function live(r) { return q[r.symbol] || r }
const cryptoLive = computed(() => d.value.crypto.map(r => ({ ...r, ...(q[r.symbol] ? { price: q[r.symbol].price, change_pct: q[r.symbol].change_pct } : {}) })))
const sectorsShown = computed(() => { const s = d.value.sectors; return s.length > 12 ? [...s.slice(0, 6), ...s.slice(-6)] : s })
const HEAT = { kr: '국내 시가총액 상위', us: '미국 시가총액 상위', cr: '코인 거래대금 상위' }
let saved = 'kr'
try { saved = localStorage.getItem('heatTab') || 'kr' } catch { /* 저장소를 못 쓰면 기본값 */ }
const heatTab = ref(HEAT[saved] ? saved : 'kr')
function setHeat(k) { heatTab.value = k; try { localStorage.setItem('heatTab', k) } catch { /* 무시 */ } }
const heatRows = computed(() => (d.value.heatmap[heatTab.value] || []).map(r => q[r.symbol] ? { ...r, change_pct: q[r.symbol].change_pct } : r))
function heat(p) {
  const a = Math.min(1, Math.abs(p || 0) / 5)
  // 변동이 작으면 옅은 바탕 + 본문색 글자, 크면 진한 바탕 + 흰 글자 (가독성)
  return p > 0 ? `rgba(224,53,60,${0.14 + a * 0.86})` : p < 0 ? `rgba(35,102,209,${0.14 + a * 0.86})` : 'rgba(120,128,140,.22)'
}
</script>
<style scoped>
.idx { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; }
.ic { padding: 10px 12px; } .ic .v { font-size: 17px; font-weight: 700; font-variant-numeric: tabular-nums; }
</style>
