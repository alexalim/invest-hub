<template>
  <div class="row" style="justify-content:center;margin-top:10px" v-if="total > size">
    <button class="sm" :disabled="modelValue <= 1" @click="$emit('update:modelValue', modelValue - 1)">이전</button>
    <span class="small">{{ modelValue }} / {{ Math.ceil(total / size) }}</span>
    <button class="sm" :disabled="modelValue * size >= total" @click="$emit('update:modelValue', modelValue + 1)">다음</button>
  </div>
</template>
<script setup>
defineProps({ modelValue: Number, total: Number, size: { type: Number, default: 50 } })
defineEmits(['update:modelValue'])
</script>
