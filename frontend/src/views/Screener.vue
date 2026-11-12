<template>
  <div>
    <div class="page-h"><div><h1>종목필터</h1><div class="muted small">재무·시세 조건과 기술적 조건으로 종목을 거릅니다. 기술적 조건은 그룹 안은 AND, 그룹끼리는 OR입니다.</div></div>
      <SavedSpecs kind="screen" label="조건" :spec="spec" @load="s => Object.assign(spec, s)" /></div>
    <div class="card" style="margin-bottom:12px">
      <div class="row wrap" style="margin-bottom:10px">
        <span class="small muted">기본 필터</span>
        <button v-for="p in meta?.presets || []" :key="p.name" class="sm" @click="applyPreset(p)">{{ p.name }}</button>
      </div>
      <div class="row wrap" style="margin-bottom:10px">
        <span class="small muted">시장</span>
        <label v-for="m in MARKETS" :key="m[0]" class="row small" style="gap:3px"><input type="checkbox" :value="m[0]" v-model="spec.markets" />{{ m[1] }}</label>
        <span class="small muted" style="margin-left:12px">종류</span>
        <label v-for="k in KINDS" :key="k[0]" class="row small" style="gap:3px"><input type="checkbox" :value="k[0]" v-model="spec.kinds" />{{ k[1] }}</label>
        <input v-model="spec.query" placeholder="이름 포함" class="w120" />
      </div>
      <h3>재무·시세 조건</h3>
      <div class="col" style="margin-bottom:12px">
        <div v-for="(f, i) in spec.filters" :key="i" class="row wrap">
          <select aria-label="필터 항목" v-model="f.field"><option v-for="x in meta?.fields || []" :key="x.key" :value="x.key">{{ x.label }}</option></select>
          <NumInput class="w90" decimals negative v-model="f.min" placeholder="최소" /> ~ <NumInput class="w90" decimals negative v-model="f.max" placeholder="최대" />
          <button class="ghost sm danger" @click="spec.filters.splice(i, 1)">✕</button>
        </div>
        <div><button class="sm" @click="spec.filters.push({ field: 'mcap', min: '', max: '' })">+ 조건 추가</button></div>
      </div>
      <h3>기술적 조건 <span class="small muted">(일봉 기준, 오늘은 현재가 반영)</span></h3>
      <div v-for="(g, gi) in spec.groups" :key="gi" class="grp">
        <div class="row between small muted"><span>그룹 {{ gi + 1 }} {{ gi > 0 ? '(또는)' : '' }}</span><button class="ghost sm danger" @click="spec.groups.splice(gi, 1)">그룹 삭제</button></div>
        <CondBuilder v-model="spec.groups[gi]" />
      </div>
      <button class="sm" @click="spec.groups.push([])">+ OR 그룹 추가</button>
      <div class="row" style="margin-top:14px"><button class="primary" :disabled="busy" @click="run">{{ busy ? '검색 중…' : '검색' }}</button>
        <span v-if="res" class="small muted">{{ num(res.total) }}개 찾음 · 조건 검사 {{ num(res.scanned) }}개{{ res.no_data ? ` · 일봉 없음 ${res.no_data}개 제외` : '' }}</span></div>
    </div>
    <div class="card flush" v-if="res">
      <QuoteTable :rows="res.rows" :columns="['price','change_pct','value','mcap','per','pbr','roe','div_yield','pos52']" rank empty="조건에 맞는 종목이 없습니다" />
    </div>
  </div>
</template>
<script setup>
import { reactive, ref } from 'vue'
import CondBuilder from '../components/CondBuilder.vue'
import QuoteTable from '../components/QuoteTable.vue'
import NumInput from '../components/NumInput.vue'
import SavedSpecs from '../components/SavedSpecs.vue'
import { api } from '../lib/api'
import { num } from '../lib/fmt'
import { useMeta } from '../lib/meta'
const meta = useMeta()
const MARKETS = [['KOSPI', '코스피'], ['KOSDAQ', '코스닥'], ['NASDAQ', '나스닥'], ['NYSE', '뉴욕'], ['AMEX', '아멕스'], ['CRYPTO', '코인']]
const KINDS = [['stock', '주식'], ['etf', 'ETF'], ['crypto', '코인']]
const spec = reactive({ markets: ['KOSPI', 'KOSDAQ'], kinds: ['stock'], query: '', filters: [{ field: 'mcap', min: 1000, max: '' }], groups: [], limit: 300, sort: 'mcap' })
const res = ref(null); const busy = ref(false)
function applyPreset(p) { spec.filters = JSON.parse(JSON.stringify(p.filters)); spec.groups = JSON.parse(JSON.stringify(p.groups)); run() }
async function run() {
  busy.value = true
  const kinds = spec.markets.includes('CRYPTO') && !spec.kinds.includes('crypto') ? [...spec.kinds, 'crypto'] : spec.kinds
  try { res.value = await api.post('/discover/screener', { ...spec, kinds }) } finally { busy.value = false }
}
</script>
<style scoped>.grp { border: 1px dashed var(--line); border-radius: 8px; padding: 8px; margin-bottom: 8px; }</style>
