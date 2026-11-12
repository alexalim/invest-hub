<template>
  <!-- 천 단위 쉼표를 보여 주는 숫자 입력칸. v-model은 숫자(비어 있으면 null)로 주고받는다. -->
  <input ref="el" type="text" :inputmode="decimals ? 'decimal' : 'numeric'" :value="shown" :placeholder="placeholder"
    autocomplete="off" @input="onInput" @blur="onBlur" />
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: [Number, String], default: null },
  decimals: { type: Boolean, default: false },   // 소수점 허용
  negative: { type: Boolean, default: false },   // 음수 허용
  placeholder: String,
})
const emit = defineEmits(['update:modelValue'])
const el = ref(null)
const shown = ref(format(props.modelValue))

function format(v) {
  if (v === null || v === undefined || v === '') return ''
  const s = String(v)
  const neg = s.startsWith('-')
  const [i, d] = s.replace('-', '').split('.')
  const int = (i || '').replace(/^0+(?=\d)/, '').replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return (neg ? '-' : '') + int + (d !== undefined ? '.' + d : '')
}
function clean(raw) {
  let s = raw.replace(/[^\d.-]/g, '')
  const neg = props.negative && s.startsWith('-')
  s = s.replace(/-/g, '')
  if (props.decimals) { const p = s.indexOf('.'); if (p >= 0) s = s.slice(0, p + 1) + s.slice(p + 1).replace(/\./g, '') } else s = s.replace(/\./g, '')
  return (neg ? '-' : '') + s
}
function onInput(e) {
  const t = e.target
  const caret = t.selectionStart ?? t.value.length
  const digitsBefore = t.value.slice(0, caret).replace(/[^\d.-]/g, '').length  // 커서 앞 숫자 개수로 위치를 되찾는다
  const c = clean(t.value)
  const f = format(c)
  shown.value = f
  t.value = f
  let pos = 0, seen = 0
  while (pos < f.length && seen < digitsBefore) { if (/[\d.-]/.test(f[pos])) seen++; pos++ }
  nextTick(() => { try { t.setSelectionRange(pos, pos) } catch { /* 일부 입력 방식은 지원 안 함 */ } })
  const n = c === '' || c === '-' || c === '.' ? null : Number(c)
  emit('update:modelValue', Number.isFinite(n) ? n : null)
}
function onBlur() { shown.value = format(props.modelValue) }
watch(() => props.modelValue, v => {
  // 바깥에서 값이 바뀌었을 때만 다시 그린다 (입력 중인 '1,000.' 같은 표시는 유지)
  const cur = clean(shown.value)
  if ((v === null || v === '') ? cur !== '' : Number(cur) !== Number(v)) shown.value = format(v)
})
</script>
