<template>
  <Modal :title="`알림 만들기 — ${name}`" @close="$emit('close')" :width="640">
    <div class="col">
      <div class="seg"><button v-for="k in KINDS" :key="k[0]" :class="{ on: kind === k[0] }" @click="kind = k[0]">{{ k[1] }}</button></div>
      <label v-if="kind.startsWith('price')" class="field">기준 가격 (현재 {{ price(curPrice) }})<NumInput v-model="value" decimals /></label>
      <label v-else-if="kind.startsWith('change')" class="field">등락률 (%)<input type="number" step="any" v-model.number="value" /></label>
      <template v-else>
        <div class="small muted">일봉 기준 조건식입니다. 장중에는 현재가를 오늘 봉으로 보고 20초마다 확인하며, 하루에 한 번만 알립니다.</div>
        <CondBuilder v-model="conds" />
      </template>
      <label class="field">메모 (선택)<input v-model="note" /></label>
      <label v-if="kind !== 'condition'" class="row small"><input type="checkbox" v-model="repeat" />조건이 맞을 때마다 반복 알림</label>
      <div class="small faint">알림은 오른쪽 위 종 모양 아이콘에 쌓입니다.</div>
      <button class="primary" @click="save">만들기</button>
    </div>
  </Modal>
</template>
<script setup>
import { ref } from 'vue'
import CondBuilder from './CondBuilder.vue'
import Modal from './Modal.vue'
import NumInput from './NumInput.vue'
import { api, toast } from '../lib/api'
import { price } from '../lib/fmt'

const props = defineProps({ symbol: String, name: String, price: Number })
const emit = defineEmits(['close', 'saved'])
const KINDS = [['price_above', '가격 이상'], ['price_below', '가격 이하'], ['change_above', '등락률 이상'], ['change_below', '등락률 이하'], ['condition', '지표 조건']]
const kind = ref('price_above'); const value = ref(props.price || 0); const note = ref(''); const repeat = ref(false)
const curPrice = props.price
const conds = ref([{ left: { ind: 'rsi', p: [14] }, op: '<', right: { value: 30 } }])
async function save() {
  const params = kind.value.startsWith('price') ? { price: value.value } : kind.value.startsWith('change') ? { pct: value.value } : { conds: conds.value, mode: 'and' }
  await api.post('/user/alerts', { symbol: props.symbol, kind: kind.value, params, note: note.value, repeat: repeat.value })
  toast('알림을 만들었습니다', 'ok'); emit('saved'); emit('close')
}
</script>
