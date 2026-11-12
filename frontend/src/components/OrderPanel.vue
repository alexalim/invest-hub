<template>
  <div class="card">
    <div class="card-h"><h3 class="nowrap">모의 주문</h3>
      <select aria-label="모의계좌 선택" v-if="accounts.length > 1" :value="accountId" @change="selectAccount(+$event.target.value); refresh()" class="sm" style="min-width:0;max-width:60%">
        <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.name }}</option></select>
      <span v-else class="small muted">{{ accounts[0]?.name }}</span>
    </div>
    <div v-if="!tradable" class="small muted">지수·환율·원자재는 주문할 수 없습니다.</div>
    <template v-else-if="info">
      <div class="seg" style="width:100%;margin-bottom:10px"><button style="flex:1" :class="{ on: side === 'buy' }" @click="side = 'buy'">매수</button><button style="flex:1" :class="{ on: side === 'sell' }" @click="side = 'sell'">매도</button></div>
      <div class="col">
        <div class="seg"><button :class="{ on: type === 'market' }" @click="type = 'market'">시장가</button><button :class="{ on: type === 'limit' }" @click="type = 'limit'; if (!limitPrice) limitPrice = info.price">지정가</button></div>
        <label v-if="type === 'limit'" class="field">지정가 ({{ info.currency }})<NumInput v-model="limitPrice" :decimals="info.currency === 'USD'" /></label>
        <label class="field">수량 <span class="faint">{{ side === 'buy' ? '최대 ' + num(maxQty, isCrypto ? 6 : 0) : '매도 가능 ' + num(info.sellable, isCrypto ? 6 : 0) }}</span>
          <NumInput v-model="qty" :decimals="isCrypto" /></label>
        <div class="row">
          <button v-for="r in [0.1, 0.25, 0.5, 1]" :key="r" class="sm grow" @click="setRatio(r)">{{ r === 1 ? '최대' : r * 100 + '%' }}</button>
        </div>
        <dl class="kv">
          <dt>현재가</dt><dd>{{ price(info.price, info.currency) }}</dd>
          <dt>주문 금액</dt><dd>{{ won(estimate) }}원</dd>
          <dt>수수료{{ side === 'sell' && info.tax_rate ? '·세금' : '' }}</dt><dd>{{ won(fees) }}원</dd>
          <dt>주문 가능 현금</dt><dd>{{ won(info.available) }}원</dd>
          <dt v-if="info.held">보유 / 평단</dt><dd v-if="info.held">{{ num(info.held, isCrypto ? 6 : 0) }} / {{ price(info.avg_price, info.currency) }}</dd>
          <dt v-if="info.currency === 'USD'">환율</dt><dd v-if="info.currency === 'USD'">{{ num(info.fx, 2) }}</dd>
        </dl>
        <div v-if="!info.open && type === 'market'" class="notice warn small">장 운영 시간이 아닙니다. 지정가로 접수하면 장중에 가격이 닿을 때 체결됩니다.</div>
        <button :class="side" :disabled="busy || !qty" @click="submit">{{ side === 'buy' ? '매수' : '매도' }} 주문</button>
      </div>
    </template>
    <Loading v-else />
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import NumInput from './NumInput.vue'
import { api, toast } from '../lib/api'
import { accountId, accounts, loadAccounts, selectAccount } from '../lib/accounts'
import { num, price, won } from '../lib/fmt'
import { useInterval } from '../lib/poll'

const props = defineProps({ symbol: String, tradable: { type: Boolean, default: true } })
const emit = defineEmits(['ordered'])
const info = ref(null); const side = ref('buy'); const type = ref('market'); const qty = ref(0); const limitPrice = ref(null); const busy = ref(false)
const isCrypto = computed(() => props.symbol?.startsWith('CR:'))
const px = computed(() => type.value === 'limit' ? (limitPrice.value || 0) : (info.value?.price || 0))
const estimate = computed(() => px.value * (qty.value || 0) * (info.value?.fx || 1))
const fees = computed(() => estimate.value * ((info.value?.fee_rate || 0) + (side.value === 'sell' ? info.value?.tax_rate || 0 : 0)))
const maxQty = computed(() => {
  if (!info.value || !px.value) return 0
  const m = info.value.available / (px.value * info.value.fx * (1 + info.value.fee_rate))
  return isCrypto.value ? Math.floor(m * 1e6) / 1e6 : Math.floor(m)
})
async function refresh() {
  if (!props.tradable || !props.symbol) return
  if (!accounts.value.length) await loadAccounts()
  if (accountId.value) info.value = await api.get(`/trade/tradable/${props.symbol}`, { account_id: accountId.value }, { quiet: true }).catch(() => info.value)
}
function setRatio(r) {
  const base = side.value === 'buy' ? maxQty.value : info.value.sellable
  qty.value = isCrypto.value ? Math.floor(base * r * 1e6) / 1e6 : Math.floor(base * r)
}
async function submit() {
  busy.value = true
  try {
    const o = await api.post('/trade/orders', { account_id: accountId.value, symbol: props.symbol, side: side.value, type: type.value, qty: qty.value, price: type.value === 'limit' ? limitPrice.value : null })
    toast(o.status === 'filled' ? `체결: ${num(o.qty, isCrypto.value ? 6 : 0)} @ ${price(o.fill_price, info.value.currency)}` : o.status === 'open' ? '지정가 주문을 접수했습니다' : `주문 ${o.status}: ${o.note || ''}`, o.status === 'rejected' ? 'error' : 'ok')
    qty.value = 0
    emit('ordered', o)
    await refresh(); loadAccounts()
  } catch { /* 토스트 */ } finally { busy.value = false }
}
watch(() => props.symbol, () => { info.value = null; qty.value = 0; limitPrice.value = null; refresh() }, { immediate: true })
useInterval(refresh, 5000)
</script>
