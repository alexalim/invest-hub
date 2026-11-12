<template>
  <div>
    <div class="page-h"><div><h1>테마·업종</h1><div class="muted small">그룹 평균 등락률 순</div></div>
      <div class="seg"><router-link to="/market/groups/theme" class="btn" :class="{ on: kind === 'theme' }">테마</router-link><router-link to="/market/groups/industry" class="btn" :class="{ on: kind === 'industry' }">업종</router-link></div></div>
    <input v-model="filter" placeholder="이름으로 찾기" style="margin-bottom:10px;width:240px" />
    <div class="card flush"><table class="t">
      <thead><tr><th>{{ kind === 'theme' ? '테마' : '업종' }}</th><th class="num">등락률</th><th class="num">종목 수</th><th>상승 / 하락</th></tr></thead>
      <tbody><tr v-for="g in shown" :key="g.no" class="click" @click="$router.push(`/market/groups/${kind}/${g.no}`)">
        <td>{{ g.name }}</td><td class="num" :class="cls(g.change_pct)">{{ pct(g.change_pct) }}</td><td class="num">{{ g.total }}</td>
        <td style="width:30%"><div class="row small"><span class="up">{{ g.rise }}</span><div class="bar-bg grow"><div class="bar-fg" :style="{ width: (g.rise / (g.total || 1) * 100) + '%', background: 'var(--up)' }" /></div><span class="down">{{ g.fall }}</span></div></td></tr></tbody>
    </table></div>
  </div>
</template>
<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../lib/api'
import { cls, pct } from '../lib/fmt'
const route = useRoute(); const kind = computed(() => route.params.kind === 'industry' ? 'industry' : 'theme')
const rows = ref([]); const filter = ref('')
api.get(`/market/groups/${kind.value}`).then(r => (rows.value = r))
const shown = computed(() => rows.value.filter(g => !filter.value || g.name.includes(filter.value)))
</script>
<style scoped>.seg .btn { border: 0; border-radius: 0; } .seg .btn.on { background: var(--accent); color: #fff; }</style>
