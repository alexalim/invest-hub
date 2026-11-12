<template>
  <!-- 조건식 편집기: [지표(파라미터).출력 n봉전 ×배수] [연산자] [지표 또는 값] -->
  <div class="col">
    <div v-for="(c, i) in modelValue" :key="i" class="cond">
      <OperandEdit v-model="c.left" :meta="metaX" />
      <select aria-label="비교 방법" v-model="c.op" class="op"><option v-for="(l, k) in metaX?.ops" :key="k" :value="k">{{ l }}</option></select>
      <OperandEdit v-model="c.right" :meta="metaX" allow-value />
      <button class="ghost sm danger" @click="remove(i)" aria-label="조건 삭제">✕</button>
    </div>
    <div class="row wrap">
      <button class="sm" @click="add">+ 조건 추가</button>
      <select aria-label="조건 예시 불러오기" v-if="allTemplates.length" class="sm" @change="e => { applyTpl(e.target.value); e.target.value = '' }">
        <option value="">자주 쓰는 조건…</option>
        <option v-for="(t, i) in allTemplates" :key="i" :value="i">{{ t.label }}</option>
      </select>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import OperandEdit from './OperandEdit.vue'
import { useMeta } from '../lib/meta'

const props = defineProps({ modelValue: { type: Array, required: true }, indicators: { type: Array, default: null }, intraday: Boolean })
const meta = useMeta()
// 장중 모드에서는 장중 전용 지표 목록을 쓴다
const metaX = computed(() => props.indicators && meta.value ? { ...meta.value, indicators: props.indicators } : meta.value)
const I = (ind, p = [], extra = {}) => ({ ind, p, ...extra })
const V = value => ({ value })
const templates = [
  { label: '5일선이 20일선 상향 돌파', c: { left: I('sma', [5]), op: 'cross_up', right: I('sma', [20]) } },
  { label: '5일선이 20일선 하향 이탈', c: { left: I('sma', [5]), op: 'cross_down', right: I('sma', [20]) } },
  { label: '종가 > 60일선', c: { left: I('close'), op: '>', right: I('sma', [60]) } },
  { label: 'RSI(14) < 30', c: { left: I('rsi', [14]), op: '<', right: V(30) } },
  { label: 'RSI(14) > 70', c: { left: I('rsi', [14]), op: '>', right: V(70) } },
  { label: 'RSI(14) 30 상향 돌파', c: { left: I('rsi', [14]), op: 'cross_up', right: V(30) } },
  { label: 'MACD > 시그널', c: { left: I('macd', [12, 26, 9], { out: 'macd' }), op: '>', right: I('macd', [12, 26, 9], { out: 'signal' }) } },
  { label: '종가가 볼린저 하단 아래', c: { left: I('close'), op: '<', right: I('bb', [20, 2], { out: 'lower' }) } },
  { label: '종가가 볼린저 상단 위', c: { left: I('close'), op: '>', right: I('bb', [20, 2], { out: 'upper' }) } },
  { label: '거래량 > 20일 평균 ×2', c: { left: I('volume'), op: '>', right: I('vol_sma', [20], { mul: 2 }) } },
  { label: '20일 신고가 돌파', c: { left: I('close'), op: '>', right: I('highest', [20], { shift: 1 }) } },
  { label: '당일 등락률 > 3%', c: { left: I('change', [1]), op: '>', right: V(3) } },
  { label: 'ADX(14) > 25', c: { left: I('adx', [14], { out: 'adx' }), op: '>', right: V(25) } },
  { label: '스토캐스틱 %K < 20', c: { left: I('stoch', [14, 3, 3], { out: 'k' }), op: '<', right: V(20) } },
]
const intradayTemplates = [
  { label: '30분 시가 범위 고가 돌파', c: { left: I('close'), op: 'cross_up', right: I('or_high', [6]) } },
  { label: '당일 VWAP 상향 돌파', c: { left: I('close'), op: 'cross_up', right: I('svwap') } },
  { label: '종가 > 당일 VWAP', c: { left: I('close'), op: '>', right: I('svwap') } },
  { label: '시초가 갭 > +2%', c: { left: I('gap'), op: '>', right: V(2) } },
  { label: '시초가 갭 < -2%', c: { left: I('gap'), op: '<', right: V(-2) } },
  { label: '당일 등락률 > +3%', c: { left: I('day_chg'), op: '>', right: V(3) } },
  { label: '당일 고가 돌파', c: { left: I('close'), op: '>', right: I('day_high') } },
  { label: '오전 10시 이후 (12봉째부터)', c: { left: I('bar_no'), op: '>=', right: V(12) } },
]
const allTemplates = computed(() => props.intraday ? [...intradayTemplates, ...templates] : templates)
function add() { props.modelValue.push({ left: I('close'), op: '>', right: I('sma', [20]) }) }
function remove(i) { props.modelValue.splice(i, 1) }
function applyTpl(i) { if (i !== '') props.modelValue.push(JSON.parse(JSON.stringify(allTemplates.value[i].c))) }
</script>

<style scoped>
.cond { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; padding: 6px 8px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel-2); }
.op { font-weight: 700; }
</style>
