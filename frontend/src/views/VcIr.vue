<template>
  <div>
    <div class="page-h"><div><h1>IR</h1><div class="muted small">투자를 유치 중인 라운드를 올려 두고 함께 검토합니다.</div></div><button class="primary" @click="form = { round: 'Seed', status: 'open' }">+ 라운드 등록</button></div>
    <div class="grid g3">
      <div v-for="r in rows" :key="r.id" class="card">
        <div class="row between"><b>{{ r.company_name }}</b><span class="chip" :class="r.status === 'open' ? 'green' : ''">{{ r.status === 'open' ? '유치 중' : '마감' }}</span></div>
        <div class="row wrap small" style="margin:6px 0"><span class="chip blue">{{ r.round }}</span><span>목표 {{ won(r.target_amount) }}</span><span v-if="r.valuation" class="muted">가치 {{ won(r.valuation) }}</span></div>
        <div class="prose small muted">{{ r.description }}</div>
        <div class="row wrap small" style="margin-top:8px"><a v-if="r.deck_url" :href="r.deck_url" target="_blank" rel="noopener" class="link">IR 덱</a><span v-if="r.contact" class="faint">{{ r.contact }}</span></div>
        <div class="row between tiny faint" style="margin-top:6px"><span>{{ r.nickname }} · {{ date(r.created_at) }}</span>
          <span v-if="r.mine"><button class="sm ghost" @click="form = { ...r }">수정</button><button class="sm ghost danger" @click="del(r)">삭제</button></span></div>
      </div>
      <div v-if="!rows.length" class="card empty">등록된 라운드가 없습니다</div>
    </div>
    <Modal v-if="form" title="IR 라운드" @close="form = null">
      <div class="col">
        <label class="field">기업명<input v-model="form.company_name" /></label>
        <div class="row"><label class="field grow">단계<select v-model="form.round"><option v-for="r in ['Pre-Seed','Seed','Pre-A','Series A','Series B','Series C','Pre-IPO']" :key="r">{{ r }}</option></select></label>
          <label class="field grow">상태<select v-model="form.status"><option value="open">유치 중</option><option value="closed">마감</option></select></label></div>
        <div class="row"><label class="field grow">목표 금액 (억 원)<NumInput decimals :model-value="form.target_amount ? form.target_amount / 1e8 : null" @update:model-value="v => (form.target_amount = v == null ? null : v * 1e8)" /></label>
          <label class="field grow">기업가치 (억 원)<NumInput decimals :model-value="form.valuation ? form.valuation / 1e8 : null" @update:model-value="v => (form.valuation = v == null ? null : v * 1e8)" /></label></div>
        <label class="field">소개<textarea v-model="form.description" rows="4" /></label>
        <label class="field">IR 덱 링크<input v-model="form.deck_url" placeholder="https://" /></label>
        <label class="field">연락처<input v-model="form.contact" /></label>
        <button class="primary" @click="save">저장</button>
      </div>
    </Modal>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import Modal from '../components/Modal.vue'
import NumInput from '../components/NumInput.vue'
import { api } from '../lib/api'
import { date, won } from '../lib/fmt'
const rows = ref([]); const form = ref(null)
async function load() { rows.value = await api.get('/vc/ir') }
async function save() { await api.post('/vc/ir', form.value); form.value = null; load() }
async function del(r) { if (window.confirm('삭제할까요?')) { await api.del(`/vc/ir/${r.id}`); load() } }
load()
</script>
