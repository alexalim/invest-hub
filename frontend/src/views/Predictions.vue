<template>
  <div>
    <div class="page-h"><div><h1>종목예측</h1><div class="muted small">오를지 내릴지 예측을 남기면 만기일 종가로 자동 채점합니다.</div></div></div>
    <div class="grid g-side">
      <div class="card flush">
        <table class="t">
          <thead><tr><th>예측자</th><th>종목</th><th>방향</th><th class="num">기준가</th><th class="num">만기</th><th class="num">결과</th><th></th></tr></thead>
          <tbody>
            <tr v-for="r in d?.rows || []" :key="r.id">
              <td>{{ r.nickname }}</td><td><SymLink :symbol="r.symbol" :name="r.name" /></td>
              <td><span class="chip" :class="r.direction === 'up' ? 'red' : 'bluedown'">{{ r.direction === 'up' ? '상승' : '하락' }} · {{ r.days }}일</span>
                <div v-if="r.comment" class="tiny faint">{{ r.comment }}</div></td>
              <td class="num">{{ price(r.base_price, curOf(r.symbol)) }}</td><td class="num small">{{ r.target_date }}</td>
              <td class="num">
                <span v-if="!r.result" class="small muted">진행 중 <span :class="cls((q[r.symbol]?.price - r.base_price) * (r.direction === 'up' ? 1 : -1))">{{ q[r.symbol] ? pct((q[r.symbol].price / r.base_price - 1) * 100) : '' }}</span></span>
                <span v-else class="chip" :class="r.result === 'hit' ? 'green' : ''">{{ r.result === 'hit' ? '적중' : '빗나감' }} {{ price(r.close_price, curOf(r.symbol)) }}</span></td>
              <td><button v-if="r.mine && !r.result" class="ghost sm danger" @click="del(r)">취소</button></td>
            </tr>
            <tr v-if="d && !d.rows.length"><td colspan="7" class="empty">아직 예측이 없습니다</td></tr>
          </tbody>
        </table>
      </div>
      <div class="col">
        <div class="card">
          <h3>새 예측</h3>
          <div class="col">
            <SymbolSearch placeholder="종목 선택" @select="s => (sel = s)" />
            <div v-if="sel" class="small">선택: <b>{{ sel.name }}</b> {{ price(sel.price, sel.currency) }}</div>
            <div class="seg"><button :class="{ on: f.direction === 'up' }" @click="f.direction = 'up'">상승</button><button :class="{ on: f.direction === 'down' }" @click="f.direction = 'down'">하락</button></div>
            <div class="seg"><button v-for="n in [1, 5, 10, 20]" :key="n" :class="{ on: f.days === n }" @click="f.days = n">{{ n }}일</button></div>
            <input v-model="f.comment" placeholder="한 줄 근거 (선택)" />
            <button class="primary" :disabled="!sel" @click="submit">예측 등록</button>
          </div>
        </div>
        <div class="card"><h3>적중률 순위</h3>
          <div v-if="!d?.board.length" class="small muted">채점된 예측이 아직 없습니다</div>
          <div v-for="(b, i) in d?.board || []" :key="b.user_id" class="row between small" style="padding:3px 0"><span>{{ i + 1 }}. {{ b.nickname }}</span><span>{{ num(b.rate, 1) }}% ({{ b.hits }}/{{ b.total }})</span></div>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { computed, reactive, ref } from 'vue'
import SymLink from '../components/SymLink.vue'
import SymbolSearch from '../components/SymbolSearch.vue'
import { api, toast } from '../lib/api'
import { cls, curOf, num, pct, price } from '../lib/fmt'
import { useQuotes } from '../lib/poll'
const d = ref(null); const sel = ref(null)
const f = reactive({ direction: 'up', days: 5, comment: '' })
const q = useQuotes(computed(() => [...new Set((d.value?.rows || []).filter(r => !r.result).map(r => r.symbol))]), 8000)
async function load() { d.value = await api.get('/community/predictions') }
async function submit() { await api.post('/community/predictions', { symbol: sel.value.symbol, ...f }); toast('예측을 등록했습니다', 'ok'); f.comment = ''; load() }
async function del(r) { await api.del(`/community/predictions/${r.id}`); load() }
load()
</script>
