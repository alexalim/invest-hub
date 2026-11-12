<template>
  <!-- 종목 목록 공용 표. rows: instruments 행 형식 -->
  <div class="scroll-x">
    <table class="t">
      <thead><tr>
        <th v-if="rank" class="num">#</th><th>종목</th>
        <th v-for="c in cols" :key="c.key" class="num" :class="{ sortable: sortable }" @click="sortable && $emit('sort', c.key)">{{ c.label }}</th>
        <th v-if="$slots.extra"></th>
      </tr></thead>
      <tbody>
        <tr v-for="(r, i) in rows" :key="r.symbol" class="click" @click="$router.push('/stock/' + r.symbol)">
          <td v-if="rank" class="num faint">{{ i + 1 + offset }}</td>
          <td><SymLink :symbol="r.symbol" :name="r.name" /></td>
          <td v-for="c in cols" :key="c.key" class="num" :class="c.color ? cls(r[c.color]) : ''">{{ c.fmt(r[c.key], r) }}</td>
          <td v-if="$slots.extra" class="num" @click.stop><slot name="extra" :row="r" /></td>
        </tr>
        <tr v-if="!rows.length"><td :colspan="cols.length + 2" class="empty">{{ empty }}</td></tr>
      </tbody>
    </table>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import SymLink from './SymLink.vue'
import { cls, mcap, pct, price, vol, won, num, curOf } from '../lib/fmt'

const props = defineProps({ rows: { type: Array, default: () => [] }, columns: { type: Array, default: () => ['price', 'change_pct', 'value', 'mcap'] },
  rank: Boolean, offset: { type: Number, default: 0 }, sortable: Boolean, empty: { type: String, default: '항목이 없습니다' } })
defineEmits(['sort'])
const ALL = {
  price: { label: '현재가', fmt: (v, r) => price(v, r.currency || curOf(r.symbol)) },
  change_pct: { label: '등락률', fmt: v => pct(v), color: 'change_pct' },
  change: { label: '전일대비', fmt: (v, r) => price(v, r.currency || curOf(r.symbol)), color: 'change' },
  volume: { label: '거래량', fmt: v => vol(v) },
  value: { label: '거래대금', fmt: (v, r) => (r.currency || curOf(r.symbol)) === 'USD' ? mcap(v, 'USD') : won(v) },
  mcap: { label: '시가총액', fmt: (v, r) => mcap(v, r.currency || curOf(r.symbol)) },
  per: { label: 'PER', fmt: v => v == null ? '-' : num(v, 2) }, pbr: { label: 'PBR', fmt: v => v == null ? '-' : num(v, 2) },
  div_yield: { label: '배당률', fmt: v => v == null ? '-' : pct(v, 2, false) },
  vol_ratio: { label: '거래량 배수', fmt: v => v == null ? '-' : num(v, 1) + '배' },
  roe: { label: 'ROE(추정)', fmt: v => v == null ? '-' : pct(v, 1, false) }, pos52: { label: '52주 위치', fmt: v => v == null ? '-' : pct(v, 0, false) },
}
const cols = computed(() => props.columns.map(k => ({ key: k, ...ALL[k] })).filter(c => c.fmt))
</script>
