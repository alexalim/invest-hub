<template>
  <!-- 화면·카드가 자료를 기다리는 동안 보이는 공통 표시 -->
  <div class="loading" role="status"><span class="spinner" /><span class="small muted">{{ text }}</span></div>
</template>
<script setup>
defineProps({ text: { type: String, default: '불러오는 중…' } })
</script>
<style scoped>
.loading { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 24px 12px; }
</style>
