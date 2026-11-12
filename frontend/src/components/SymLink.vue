<template>
  <router-link :to="'/stock/' + symbol" class="sym" @click.stop>
    <b>{{ name || symbol }}</b><span v-if="!hideCode">{{ code }}</span>
  </router-link>
</template>
<script setup>
import { computed } from 'vue'
const props = defineProps({ symbol: String, name: String, hideCode: Boolean, market: String })
const code = computed(() => (props.symbol || '').split(':')[1] + (props.market ? ' · ' + props.market : ''))
</script>
