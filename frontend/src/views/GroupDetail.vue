<template>
  <div>
    <router-link :to="`/market/groups/${route.params.kind}`" class="small link">← {{ route.params.kind === 'industry' ? '업종' : '테마' }} 목록</router-link>
    <div class="page-h" style="margin-top:6px" v-if="d"><div><h1>{{ d.info?.name }}</h1>
      <div class="small"><span :class="cls(d.info?.change_pct)">{{ pct(d.info?.change_pct) }}</span> · {{ d.stocks.length }}종목</div></div></div>
    <div class="card flush"><div v-if="!d" class="spinner" style="margin:16px" /><QuoteTable v-else :rows="live" :columns="['price','change_pct','value','mcap','per','pbr']" /></div>
  </div>
</template>
<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import QuoteTable from '../components/QuoteTable.vue'
import { api } from '../lib/api'
import { cls, pct } from '../lib/fmt'
import { useQuotes } from '../lib/poll'
const route = useRoute(); const d = ref(null)
api.get(`/market/groups/${route.params.kind}/${route.params.no}`).then(r => (d.value = r))
const q = useQuotes(computed(() => d.value ? d.value.stocks.map(r => r.symbol) : []), 6000)
const live = computed(() => d.value.stocks.map(r => q[r.symbol] ? { ...r, price: q[r.symbol].price, change_pct: q[r.symbol].change_pct } : r))
</script>
