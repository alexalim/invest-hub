<template>
  <span class="opnd">
    <select aria-label="지표 선택" :value="isValue ? '__value' : modelValue.ind" @change="setInd($event.target.value)">
      <option v-if="allowValue" value="__value">숫자 값</option>
      <option v-for="i in meta?.indicators || []" :key="i.key" :value="i.key">{{ i.label }}</option>
    </select>
    <template v-if="isValue"><input aria-label="비교할 값" class="w90" type="number" step="any" :value="modelValue.value" @input="set({ value: +$event.target.value })" /></template>
    <template v-else>
      <input v-for="(p, k) in params" :key="k" class="w60" type="number" step="any" :title="p[0]" :placeholder="p[0]"
        :value="(modelValue.p || [])[k] ?? p[1]" @input="setP(k, $event.target.value)" />
      <select aria-label="지표 출력값" v-if="outs.length" :value="modelValue.out || outs[0]" @change="set({ out: $event.target.value })">
        <option v-for="o in outs" :key="o" :value="o">{{ OUT_LABEL[o] || o }}</option>
      </select>
      <details class="more"><summary class="small faint">옵션</summary>
        <label class="small">n봉 전 <input class="w60" type="number" min="0" :value="modelValue.shift || 0" @input="set({ shift: +$event.target.value || 0 })" /></label>
        <label class="small">× 배수 <input class="w60" type="number" step="any" :value="modelValue.mul ?? 1" @input="set({ mul: +$event.target.value || 1 })" /></label>
      </details>
    </template>
  </span>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ modelValue: Object, meta: Object, allowValue: Boolean })
const emit = defineEmits(['update:modelValue'])
const OUT_LABEL = { upper: '상단', mid: '중심', lower: '하단', macd: 'MACD선', signal: '시그널', hist: '히스토그램', k: '%K', d: '%D', adx: 'ADX', pdi: '+DI', ndi: '-DI' }
const isValue = computed(() => !('ind' in props.modelValue))
const cat = computed(() => (props.meta?.indicators || []).find(i => i.key === props.modelValue.ind))
const params = computed(() => cat.value?.params || [])
const outs = computed(() => cat.value?.outs || [])
function set(patch) { emit('update:modelValue', { ...props.modelValue, ...patch }) }
function setInd(k) {
  if (k === '__value') return emit('update:modelValue', { value: 0 })
  const c = props.meta.indicators.find(i => i.key === k)
  emit('update:modelValue', { ind: k, p: c.params.map(p => p[1]), ...(c.outs.length ? { out: c.outs[0] } : {}) })
}
function setP(k, v) { const p = [...(props.modelValue.p || params.value.map(x => x[1]))]; p[k] = +v; set({ p }) }
</script>

<style scoped>
.opnd { display: inline-flex; gap: 4px; align-items: center; flex-wrap: wrap; }
.more { position: relative; } .more[open] { display: inline-flex; gap: 6px; align-items: center; }
.more summary { cursor: pointer; list-style: none; padding: 0 4px; }
</style>
