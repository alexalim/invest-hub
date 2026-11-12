<template>
  <div class="modal-back" @click.self="$emit('close')">
    <div class="modal" role="dialog" aria-modal="true" :aria-label="title" :style="{ width: width ? `min(${width}px, 100%)` : undefined }">
      <div class="card-h"><h2>{{ title }}</h2><button class="ghost" @click="$emit('close')" aria-label="닫기">✕</button></div>
      <slot />
    </div>
  </div>
</template>
<script setup>
import { onBeforeUnmount, onMounted } from 'vue'
defineProps({ title: String, width: Number })
const emit = defineEmits(['close'])
// Esc 키로 닫기 (키보드만 쓰는 경우에도 빠져나올 수 있게)
function onKey(e) { if (e.key === 'Escape') emit('close') }
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>
