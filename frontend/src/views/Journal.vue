<template>
  <div>
    <div class="page-h"><div><h1>매매일지</h1><div class="muted small">체결 내역마다 이유와 느낌을 남기고, 직접 일지를 쓸 수도 있습니다.</div></div>
      <button class="primary" @click="edit({})">+ 일지 쓰기</button></div>
    <div v-if="!d" class="spinner" />
    <template v-else>
      <div class="grid g4">
        <div class="card stat"><span class="k">체결 · 청산</span><span class="v">{{ d.stats.trades }} · {{ d.stats.closed }}</span></div>
        <div class="card stat"><span class="k">승률</span><span class="v">{{ d.stats.win_rate == null ? '-' : d.stats.win_rate + '%' }}</span></div>
        <div class="card stat"><span class="k">실현 손익</span><span class="v" :class="cls(d.stats.realized)">{{ won(d.stats.realized) }}원</span><span class="tiny faint">수수료·세금 {{ won(d.stats.fees) }}원</span></div>
        <div class="card stat"><span class="k">평균 이익 / 손실</span><span class="v small"><span class="up">{{ won(d.stats.avg_win) }}</span> / <span class="down">{{ won(d.stats.avg_loss) }}</span></span></div>
      </div>
      <div class="card" style="margin-top:12px" v-if="d.by_day.length">
        <h3>일별 실현 손익</h3>
        <MiniChart type="bar" :series="[{ values: d.by_day.map(x => x.pnl), colors: d.by_day.map(x => x.pnl >= 0 ? 'var(--up)' : 'var(--down)') }]" :labels="d.by_day.map(x => x.date)" :h="120" />
        <div class="row between tiny faint"><span>{{ d.by_day[0].date }}</span><span>{{ d.by_day[d.by_day.length - 1].date }}</span></div>
      </div>
      <div class="grid g2" style="margin-top:12px">
        <div class="card"><h3>체결 기록</h3>
          <div v-if="!d.trades.length" class="empty small">체결 내역이 없습니다</div>
          <div v-for="t in d.trades" :key="t.id" class="list-item">
            <div class="row between"><div class="row"><span class="chip" :class="t.side === 'buy' ? 'red' : 'bluedown'">{{ t.side === 'buy' ? '매수' : '매도' }}</span>
              <router-link :to="'/stock/' + t.symbol" class="link"><b>{{ t.name }}</b></router-link><span class="small">{{ num(t.qty, 4) }} @ {{ price(t.price, curOf(t.symbol)) }}</span></div>
              <span class="tiny faint">{{ datetime(t.ts) }}</span></div>
            <div v-if="t.pnl != null" class="small" :class="cls(t.pnl)">실현 {{ won(t.pnl) }}원</div>
            <div v-if="t.note" class="small" style="margin-top:4px"><b>{{ t.note.title }}</b> <span class="chip" v-if="t.note.emotion">{{ t.note.emotion }}</span><div class="prose muted">{{ t.note.body }}</div></div>
            <button class="sm ghost" @click="edit({ trade_id: t.id, ...(t.note || {}) }, t)">{{ t.note ? '메모 고치기' : '메모 남기기' }}</button>
          </div></div>
        <div class="card"><h3>직접 쓴 일지</h3>
          <div v-if="!d.entries.length" class="empty small">아직 없습니다</div>
          <div v-for="e in d.entries" :key="e.id" class="list-item">
            <div class="row between"><b>{{ e.title || '(제목 없음)' }}</b><span class="tiny faint">{{ e.date }}</span></div>
            <div class="row wrap small"><router-link v-if="e.symbol" :to="'/stock/' + e.symbol" class="chip blue">{{ e.symbol }}</router-link><span v-if="e.emotion" class="chip">{{ e.emotion }}</span><span v-for="tg in (e.tags || '').split(',').filter(Boolean)" :key="tg" class="chip">#{{ tg.trim() }}</span></div>
            <div class="prose small muted">{{ e.body }}</div>
            <div class="row"><button class="sm ghost" @click="edit(e)">고치기</button><button class="sm ghost danger" @click="del(e)">삭제</button></div>
          </div></div>
      </div>
    </template>
    <Modal v-if="form" :title="form.trade_id ? '체결 메모' : '매매일지'" @close="form = null">
      <div class="col">
        <div v-if="tradeRef" class="small muted">{{ tradeRef.name }} {{ tradeRef.side === 'buy' ? '매수' : '매도' }} {{ num(tradeRef.qty, 4) }} @ {{ price(tradeRef.price, curOf(tradeRef.symbol)) }}</div>
        <template v-if="!form.trade_id">
          <div class="row"><SymbolSearch placeholder="종목 (선택)" class="grow" @select="s => (form.symbol = s.symbol)" /><span v-if="form.symbol" class="chip blue">{{ form.symbol }}</span></div>
          <label class="field">날짜<input type="date" v-model="form.date" /></label>
        </template>
        <label class="field">제목<input v-model="form.title" /></label>
        <label class="field">내용 (매매 이유, 계획, 복기)<textarea v-model="form.body" rows="6" /></label>
        <label class="field">감정<select v-model="form.emotion"><option value="">-</option><option v-for="e in EMO" :key="e">{{ e }}</option></select></label>
        <label class="field">태그 (쉼표로 구분)<input v-model="form.tags" placeholder="돌파, 눌림목" /></label>
        <button class="primary" @click="save">저장</button>
      </div>
    </Modal>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import MiniChart from '../components/MiniChart.vue'
import Modal from '../components/Modal.vue'
import SymbolSearch from '../components/SymbolSearch.vue'
import { api } from '../lib/api'
import { cls, curOf, datetime, num, price, won } from '../lib/fmt'
const EMO = ['확신', '차분', '불안', '조급', '욕심', '후회', '만족']
const d = ref(null); const form = ref(null); const tradeRef = ref(null)
async function load() { d.value = await api.get('/trade/journal') }
function edit(e, t = null) { tradeRef.value = t; form.value = { date: new Date().toISOString().slice(0, 10), title: '', body: '', tags: '', emotion: '', ...e } }
async function save() { await api.post('/trade/journal', form.value); form.value = null; load() }
async function del(e) { if (window.confirm('삭제할까요?')) { await api.del(`/trade/journal/${e.id}`); load() } }
load()
</script>
