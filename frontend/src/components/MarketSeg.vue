<template>
  <!-- 코스피/코스닥 전환. 선택은 화면을 옮겨도 유지된다. -->
  <div class="seg"><button v-for="m in KR_MARKETS" :key="m[0]" :class="{ on: krMarket === m[0] }" @click="krMarket = m[0]">{{ m[1] }}</button></div>
</template>
<script setup>
import { KR_MARKETS, krMarket } from '../lib/prefs'
</script>
