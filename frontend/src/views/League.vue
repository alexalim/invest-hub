<template>
  <div>
    <div class="page-h"><div><h1>투자리그</h1><div class="muted small">{{ d?.season }} 시즌 ({{ d?.start }} 시작) · 시즌 수익률은 시즌 시작 평가액 대비</div></div></div>
    <div class="grid g2">
      <div class="card flush"><div style="padding:12px 12px 0"><h3>모의투자 순위</h3></div>
        <table class="t"><thead><tr><th class="num">순위</th><th>참가자</th><th class="num">시즌 수익률</th><th class="num">누적 수익률</th><th class="num">평가액</th><th class="num">거래</th><th class="num">승률</th></tr></thead>
          <tbody><tr v-for="r in d?.rows || []" :key="r.account_id" :style="r.user_id === session.user?.id ? 'background:var(--accent-soft)' : ''">
            <td class="num">{{ medal(r.rank) }}</td><td>{{ r.nickname }} <span class="tiny faint">{{ r.account }}</span></td>
            <td class="num" :class="cls(r.season_return)" style="font-weight:700">{{ pct(r.season_return) }}</td><td class="num" :class="cls(r.total_return)">{{ pct(r.total_return) }}</td>
            <td class="num">{{ won(r.equity) }}</td><td class="num">{{ r.trades }}</td><td class="num">{{ r.win_rate == null ? '-' : r.win_rate + '%' }}</td></tr></tbody></table></div>
      <div class="card flush"><div style="padding:12px 12px 0"><h3>차트게임 순위</h3></div>
        <table class="t"><thead><tr><th class="num">순위</th><th>참가자</th><th class="num">평균 수익률</th><th class="num">최고</th><th class="num">판 수</th><th class="num">이긴 판</th></tr></thead>
          <tbody><tr v-for="r in game || []" :key="r.user_id"><td class="num">{{ medal(r.rank) }}</td><td>{{ r.nickname }}</td><td class="num" :class="cls(r.avg_pct)">{{ pct(r.avg_pct) }}</td>
            <td class="num" :class="cls(r.best_pct)">{{ pct(r.best_pct) }}</td><td class="num">{{ r.games }}</td><td class="num">{{ num(r.win_rate, 0) }}%</td></tr>
            <tr v-if="game && !game.length"><td colspan="6" class="empty">아직 끝낸 게임이 없습니다</td></tr></tbody></table></div>
    </div>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { api, session } from '../lib/api'
import { cls, num, pct, won } from '../lib/fmt'
const d = ref(null); const game = ref(null)
api.get('/trade/league').then(r => (d.value = r)); api.get('/trade/game').then(r => (game.value = r.ranking))
function medal(n) { return ['🥇', '🥈', '🥉'][n - 1] || n }
</script>
