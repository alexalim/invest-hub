<template>
  <div v-if="st">
    <div class="banner" :class="st.mode">
      <b>{{ st.mode === 'real' ? '실전투자 — 실제 돈이 움직입니다' : '모의투자 — 한국투자증권 모의 서버' }}</b>
      <span class="small">{{ st.envs[st.mode].account || '계좌 미설정' }} · 국내 주식·ETF만 · {{ st.enabled ? '주문 가능' : '주문 꺼짐' }}</span>
    </div>
    <div class="page-h"><div><h1>실계좌 (관리자 전용)</h1><div class="muted small">한국투자증권 Open API로 주문합니다. 다른 사용자에게는 이 화면과 기능이 보이지 않고 서버에서도 막습니다.</div></div>
      <div class="row">
        <template v-if="unlocked"><span class="chip green">잠금 해제 {{ left }}</span><button class="sm" @click="lock">잠그기</button></template>
        <template v-else><input v-model="pw" type="password" placeholder="비밀번호" autocomplete="current-password" class="w120" @keydown.enter="unlock" /><button class="primary" @click="unlock">잠금 해제 (10분)</button></template>
      </div></div>

    <div class="grid g-side">
      <div class="col" style="gap:12px">
        <div class="card">
          <div class="card-h"><h3>주문</h3><span class="small muted">미리보기 → 45초 안에 확정</span></div>
          <div v-if="!st.envs[st.mode].configured" class="notice warn small">{{ st.mode === 'real' ? '실전' : '모의' }}투자 키와 계좌번호를 아래 설정에서 먼저 넣어 주세요.</div>
          <div class="col">
            <div class="row wrap"><SymbolSearch placeholder="국내 종목" style="width:260px" @select="pick" />
              <span v-if="f.symbol" class="chip blue">{{ f.name }} {{ price(last) }}</span></div>
            <div class="row wrap">
              <div class="seg"><button :class="{ on: f.side === 'buy' }" @click="f.side = 'buy'">매수</button><button :class="{ on: f.side === 'sell' }" @click="f.side = 'sell'">매도</button></div>
              <div class="seg"><button :class="{ on: f.type === 'limit' }" @click="f.type = 'limit'">지정가</button><button :class="{ on: f.type === 'market' }" @click="f.type = 'market'">시장가</button></div>
              <NumInput v-if="f.type === 'limit'" v-model="f.price" placeholder="가격" class="w120" />
              <NumInput v-model="f.qty" placeholder="수량" class="w90" />
              <button :class="f.side" :disabled="!unlocked || !f.symbol || !f.qty || busy" @click="previewOrder">{{ f.side === 'buy' ? '매수' : '매도' }} 미리보기</button>
            </div>
            <div class="tiny faint">지정가는 호가 단위에 맞춰 매수는 내림, 매도는 올림합니다. 장 운영 시간·주문 가능 여부는 증권사가 판단하고, 거부되면 그 사유를 그대로 보여 줍니다.</div>
          </div>
        </div>

        <div class="card flush">
          <div style="padding:12px 12px 0" class="row between"><h3>주문 기록</h3><button class="sm" @click="loadOrders(1)">증권사 내역과 맞추기</button></div>
          <div v-if="ordersNote" class="notice warn small" style="margin:8px 12px">{{ ordersNote }}</div>
          <div class="scroll-x"><table class="t">
            <thead><tr><th>시각</th><th>환경</th><th>종목</th><th>구분</th><th class="num">수량</th><th class="num">가격</th><th>상태</th><th>주문번호</th><th>메시지</th><th></th></tr></thead>
            <tbody><tr v-for="o in orders" :key="o.id">
              <td class="small nowrap">{{ datetime(o.created_at) }}</td><td><span class="chip" :class="o.env === 'real' ? 'red' : 'blue'">{{ o.env === 'real' ? '실전' : '모의' }}</span></td>
              <td>{{ o.name }}</td><td :class="o.side === 'buy' ? 'up' : 'down'">{{ o.side === 'buy' ? '매수' : '매도' }} <span class="tiny faint">{{ o.ord_type === 'market' ? '시장' : '지정' }}</span></td>
              <td class="num">{{ o.qty }}<div v-if="o.filled_qty" class="tiny faint">체결 {{ o.filled_qty }}</div></td>
              <td class="num">{{ o.price ? price(o.price) : '시장가' }}<div v-if="o.avg_price" class="tiny faint">평균 {{ price(o.avg_price) }}</div></td>
              <td><span class="chip" :class="STATUS[o.status]?.[1]">{{ STATUS[o.status]?.[0] || o.status }}</span></td>
              <td class="small">{{ o.odno || '-' }}</td><td class="small muted" style="max-width:220px">{{ o.msg }}</td>
              <td><button v-if="['accepted','partial'].includes(o.status)" class="sm danger" :disabled="!unlocked" @click="cancelOrder(o)">취소</button></td></tr>
              <tr v-if="!orders.length"><td colspan="10" class="empty">주문 기록이 없습니다</td></tr></tbody></table></div>
          <div class="tiny faint" style="padding:8px 12px">'결과 미확인'은 증권사 응답을 받지 못한 주문입니다. 자동으로 다시 보내지 않으니, 반드시 '증권사 내역과 맞추기'나 한투 앱에서 확인한 뒤 다시 주문하세요.</div>
        </div>
      </div>

      <div class="col" style="gap:12px">
        <div class="card">
          <div class="card-h"><h3>잔고 ({{ st.mode === 'real' ? '실전' : '모의' }})</h3><button class="sm" @click="loadBalance">새로고침</button></div>
          <div v-if="!st.envs[st.mode].configured" class="small muted">아래 "환경과 키"에 {{ st.mode === 'real' ? '실전' : '모의' }}투자 키와 계좌번호를 저장하면 잔고가 표시됩니다.</div>
          <div v-else-if="balErr" class="small muted">{{ balErr }}</div>
          <template v-else-if="bal">
            <dl class="kv"><dt>예수금</dt><dd>{{ won(bal.cash) }}원</dd><dt>D+2 예수금</dt><dd>{{ won(bal.d2_cash) }}원</dd><dt>주식 평가</dt><dd>{{ won(bal.stock_value) }}원</dd><dt>총 평가</dt><dd><b>{{ won(bal.total) }}원</b></dd></dl>
            <div v-for="p in bal.positions" :key="p.code" class="list-item small">
              <div class="row between"><b>{{ p.name }}</b><span :class="cls(p.pnl)">{{ pct(p.pnl_pct) }}</span></div>
              <div class="row between muted"><span>{{ p.qty }}주 (매도 가능 {{ p.sellable }}) · 평단 {{ price(p.avg_price) }}</span><span>{{ won(p.value) }}원</span></div>
            </div>
            <div v-if="!bal.positions.length" class="small muted">보유 종목이 없습니다</div>
          </template>
        </div>

        <div class="card">
          <h3>안전장치</h3>
          <label class="row small"><input type="checkbox" :checked="st.enabled" @change="saveCfg({ enabled: $event.target.checked })" /><b>주문 실행 스위치</b> — 끄면 모든 실계좌 주문을 막습니다</label>
          <div class="col" style="margin-top:8px">
            <label class="field">1회 주문 한도 (원)<NumInput v-model="lim.per_order_krw" /></label>
            <label class="field">하루 주문 금액 한도 (원)<NumInput v-model="lim.daily_krw" /></label>
            <label class="field">하루 주문 횟수 한도<NumInput v-model="lim.daily_count" /></label>
            <button class="sm" @click="saveCfg({ limits: lim })">한도 저장</button>
            <div class="tiny faint">오늘 사용: {{ st.mode === 'real' ? '실전' : '모의' }} {{ won(st.usage[st.mode].amount) }}원 · {{ st.usage[st.mode].count }}회</div>
          </div>
        </div>

        <div class="card">
          <h3>환경과 키</h3>
          <div class="seg" style="margin-bottom:8px"><button :class="{ on: st.mode === 'demo' }" @click="saveCfg({ mode: 'demo' })">모의</button><button :class="{ on: st.mode === 'real' }" @click="toReal">실전</button></div>
          <div class="tiny faint" style="margin-bottom:8px">실전 전환과 실전 키 저장은 잠금 해제 상태에서만 됩니다.</div>
          <div v-for="e in ['demo', 'real']" :key="e" class="list-item">
            <div class="row between small"><b>{{ e === 'real' ? '실전투자' : '모의투자' }}</b><span class="chip" :class="st.envs[e].configured ? 'green' : ''">{{ st.envs[e].configured ? '설정됨 ' + st.envs[e].account : '없음' }}</span></div>
            <details :open="!st.envs[e].configured"><summary class="small link" style="cursor:pointer">{{ st.envs[e].configured ? '키 바꾸기' : '키 넣기 (앱키 · 앱시크릿 · 계좌번호)' }}</summary>
              <div class="col" style="margin-top:6px">
                <input v-model="keys[e].app_key" type="password" placeholder="앱키 (App Key)" autocomplete="off" />
                <input v-model="keys[e].app_secret" type="password" placeholder="앱시크릿 (App Secret)" autocomplete="off" />
                <div class="row"><input v-model="keys[e].cano" placeholder="계좌번호 앞 8자리" class="grow" autocomplete="off" /><span>-</span><input v-model="keys[e].prdt" placeholder="01" class="w60" autocomplete="off" /></div>
                <div class="row"><button class="sm primary" @click="saveKeys(e)">저장</button><button v-if="st.envs[e].configured" class="sm ghost danger" @click="saveCfg({ clear_env: e })">삭제</button></div>
                <div class="tiny faint">{{ e === 'real' ? '실전용' : '모의투자용' }} 앱키는 KIS Developers에서 따로 발급됩니다. 저장한 값은 서버 파일(data/kis.json, 본인만 읽기)에만 있고 화면에 다시 표시하지 않습니다.</div>
              </div></details>
          </div>
        </div>
      </div>
    </div>

    <Modal v-if="pv" :title="(pv.env === 'real' ? '[실전] ' : '[모의] ') + '주문 확인'" @close="pv = null">
      <div class="banner" :class="pv.env" style="margin-bottom:12px"><b>{{ pv.env === 'real' ? '실제 계좌에 주문이 나갑니다' : '모의투자 서버로 주문합니다' }}</b></div>
      <dl class="kv" style="font-size:15px">
        <dt>종목</dt><dd><b>{{ pv.name }}</b> ({{ pv.code }})</dd>
        <dt>구분</dt><dd :class="pv.side === 'buy' ? 'up' : 'down'"><b>{{ pv.side === 'buy' ? '매수' : '매도' }}</b> · {{ pv.type === 'market' ? '시장가' : '지정가' }}</dd>
        <dt>수량</dt><dd><b>{{ pv.qty }}주</b></dd>
        <dt>가격</dt><dd>{{ pv.price ? price(pv.price) + '원' : '시장가 (현재 ' + price(pv.last) + '원)' }}<span v-if="pv.tick_adjusted" class="tiny warn"> 호가 단위로 조정됨</span></dd>
        <dt>예상 금액</dt><dd><b>{{ won(pv.est) }}원</b></dd>
      </dl>
      <div class="row" style="margin-top:14px"><button :class="pv.side" class="grow" :disabled="busy || countdown <= 0" @click="confirmOrder">{{ countdown > 0 ? `확정 (${countdown}초)` : '시간 초과 — 다시 미리보기' }}</button><button @click="pv = null">취소</button></div>
    </Modal>
  </div>
  <div v-else-if="denied" class="empty">관리자만 쓸 수 있는 화면입니다.</div>
  <Loading v-else />
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import Modal from '../components/Modal.vue'
import NumInput from '../components/NumInput.vue'
import SymbolSearch from '../components/SymbolSearch.vue'
import { api, toast } from '../lib/api'
import { cls, datetime, pct, price, won } from '../lib/fmt'
import { useInterval } from '../lib/poll'

const STATUS = { sending: ['전송 중', 'orange'], accepted: ['접수', 'blue'], partial: ['일부 체결', 'orange'], filled: ['체결', 'green'],
  rejected: ['거부', 'red'], unknown: ['결과 미확인', 'red'], cancel_requested: ['취소 요청', 'orange'], cancelled: ['취소됨', ''] }
const st = ref(null); const denied = ref(false); const pw = ref(''); const now = ref(Date.now() / 1000)
const lim = reactive({ per_order_krw: 0, daily_krw: 0, daily_count: 0 })
const keys = reactive({ demo: { prdt: '01' }, real: { prdt: '01' } })
const f = reactive({ symbol: '', name: '', side: 'buy', type: 'limit', qty: 1, price: null })
const last = ref(null); const pv = ref(null); const busy = ref(false); const orders = ref([]); const ordersNote = ref(null)
const bal = ref(null); const balErr = ref('')
const unlocked = computed(() => st.value?.unlocked_until && st.value.unlocked_until > now.value)
const left = computed(() => { const s = Math.max(0, Math.floor(st.value.unlocked_until - now.value)); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}` })
const countdown = computed(() => pv.value ? Math.max(0, Math.floor(pv.value.until - now.value)) : 0)
const tick = setInterval(() => (now.value = Date.now() / 1000), 1000)
onBeforeUnmount(() => clearInterval(tick))

async function load() {
  try { st.value = await api.get('/live/status', null, { quiet: true }); Object.assign(lim, st.value.limits) } catch (e) { if (e.status === 403) denied.value = true }
}
async function loadBalance() { balErr.value = ''; try { bal.value = await api.get('/live/balance', null, { quiet: true }) } catch (e) { balErr.value = e.message } }
async function loadOrders(sync = 1) { const r = await api.get('/live/orders', { sync }, { quiet: true }).catch(() => null); if (r) { orders.value = r.rows; ordersNote.value = r.note } }
async function unlock() { await api.post('/live/unlock', { password: pw.value }); pw.value = ''; await load(); toast('10분 동안 실계좌 주문이 가능합니다', 'ok') }
async function lock() { await api.post('/live/lock'); load() }
async function saveCfg(p) { st.value = { ...st.value, ...(await api.post('/live/config', p)) }; await load(); toast('저장했습니다', 'ok'); if ('mode' in p) { bal.value = null; loadBalance(); loadOrders(0) } }
async function saveKeys(e) { await saveCfg({ env: e, keys: keys[e] }); keys[e] = { prdt: '01' }; if (e === st.value.mode) loadBalance() }
async function toReal() {
  if (!window.confirm('실전 모드로 바꾸면 이후 주문은 실제 계좌로 나갑니다. 바꿀까요?')) return
  saveCfg({ mode: 'real' })
}
function pick(s) {
  if (!s.symbol.startsWith('KR:')) return toast('국내 종목만 주문할 수 있습니다')
  f.symbol = s.symbol; f.name = s.name; last.value = s.price; f.price = s.price
}
async function previewOrder() {
  busy.value = true
  try { const r = await api.post('/live/preview', { symbol: f.symbol, side: f.side, type: f.type, qty: f.qty, price: f.type === 'limit' ? f.price : null }); pv.value = { ...r, until: Date.now() / 1000 + r.expires_in - 2 } }
  catch { /* 토스트 */ } finally { busy.value = false }
}
async function confirmOrder() {
  busy.value = true
  try {
    const o = await api.post('/live/order', { confirm_id: pv.value.confirm_id })
    toast(o.status === 'accepted' ? `접수됨 (주문번호 ${o.odno})` : o.status === 'unknown' ? '응답을 받지 못했습니다. 주문 기록에서 확인하세요' : `거부: ${o.msg}`, o.status === 'accepted' ? 'ok' : 'error')
    pv.value = null; loadOrders(0); load(); setTimeout(loadBalance, 1500)
  } catch { pv.value = null } finally { busy.value = false }
}
async function cancelOrder(o) { if (!window.confirm(`${o.name} 주문을 취소할까요?`)) return; const r = await api.post(`/live/orders/${o.id}/cancel`); toast(r.msg || '취소 요청', 'ok'); loadOrders(1) }
load().then(() => { if (st.value) { loadBalance(); loadOrders(1) } })
useInterval(() => { if (st.value) loadOrders(1) }, 30000)
</script>

<style scoped>
.banner { padding: 10px 14px; border-radius: 10px; margin-bottom: 14px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.banner.demo { background: var(--accent-soft); color: var(--accent); }
.banner.real { background: var(--up); color: #fff; }
</style>
