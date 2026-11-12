<template>
  <div>
    <div class="page-h"><div><h1>{{ TITLE[kind][0] }}</h1><div class="muted small">{{ TITLE[kind][1] }}</div></div></div>
    <div class="card"><PostList :kind="kind" :key="kind" /></div>
  </div>
</template>
<script setup>
import PostList from '../components/PostList.vue'
defineProps({ kind: String })
const TITLE = { timeline: ['타임라인', '짧은 의견과 종목 이야기'], insight: ['인사이트', '긴 분석 글'], discussion: ['토론', '스타트업·벤처 투자 시장 이야기'] }
</script>
