<template>
  <div class="scroll-x"><table class="t">
    <thead><tr><th>날짜</th><th v-if="!hideCompany">기업</th><th>단계</th><th class="num">금액</th><th>투자자</th><th>출처</th><th v-if="session.user?.is_admin && admin"></th></tr></thead>
    <tbody>
      <tr v-for="d in rows" :key="d.id">
        <td class="small nowrap">{{ d.date }}</td>
        <td v-if="!hideCompany" class="nowrap"><router-link :to="'/vc/companies/' + d.company_id" class="link"><b>{{ d.company }}</b></router-link>
          <div class="tiny faint">{{ d.category || '' }}{{ d.foreign_deal ? ' · 해외' : '' }}</div></td>
        <td><span class="chip" :class="d.kind === 'mna' ? 'orange' : 'blue'">{{ d.kind === 'mna' ? 'M&A' : (d.round || '미상') }}</span></td>
        <td class="num">{{ d.amount ? won(d.amount) : (d.amount_text || '비공개') }}<div v-if="d.valuation" class="tiny faint">기업가치 {{ won(d.valuation) }}</div></td>
        <td class="small"><template v-for="(i, k) in d.investors" :key="i.id"><router-link :to="'/vc/investors/' + i.id" class="link">{{ i.name }}</router-link><span v-if="i.lead" class="tiny faint">(리드)</span><span v-if="k < d.investors.length - 1">, </span></template>
          <span v-if="d.acquirer && !d.investors.length">인수: {{ d.acquirer }}</span><span v-if="!d.investors.length && !d.acquirer" class="faint">-</span></td>
        <td><a :href="d.source_url" target="_blank" rel="noopener" class="link small" :title="d.title">기사</a></td>
        <td v-if="session.user?.is_admin && admin" class="nowrap"><button class="sm ghost" :title="d.foreign_deal ? '국내로 표시' : '해외로 표시'" @click="$emit('fix', d, { foreign_deal: d.foreign_deal ? 0 : 1 })">{{ d.foreign_deal ? '국내로' : '해외로' }}</button>
          <button class="sm ghost danger" @click="$emit('fix', d, { delete: true })">삭제</button></td>
      </tr>
      <tr v-if="!rows.length"><td colspan="7" class="empty">투자 기록이 없습니다</td></tr>
    </tbody></table></div>
</template>
<script setup>
import { session } from '../lib/api'
import { won } from '../lib/fmt'
defineProps({ rows: { type: Array, default: () => [] }, hideCompany: Boolean, admin: Boolean })
defineEmits(['fix'])
</script>
