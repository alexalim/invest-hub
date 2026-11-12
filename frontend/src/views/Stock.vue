<template>
  <div v-if="d">
    <div class="page-h">
      <div>
        <div class="row wrap"><h1>{{ inst.name }}</h1><span class="chip">{{ inst.code }}</span><span class="chip blue">{{ MARKET_LABEL[inst.market] || inst.market }}</span>
          <span v-if="inst.kind && !['stock','crypto','index','fx','commodity','rate'].includes(inst.kind)" class="chip">{{ inst.kind.toUpperCase() }}</span>
          <span v-if="inst.sector" class="chip">{{ inst.sector }}</span></div>
        <div class="row wrap" style="align-items:baseline;margin-top:4px">
          <span class="bigp">{{ isMacro ? macro(q.price, symbol) : price(q.price, cur) }}</span>
          <span :class="cls(q.change_pct)" style="font-weight:600">{{ signed(q.change, isMacro ? (symbol.startsWith('RT:') ? 3 : 2) : cur === 'USD' ? 2 : 0) }} ({{ pct(q.change_pct) }})</span>
          <span v-if="q.over_price && q.over_price !== q.price" class="small muted">시간외 {{ price(q.over_price, cur) }}</span>
          <span class="small faint">{{ q.market_status === 'OPEN' ? '장중' : q.market_status === 'CLOSE' ? '장 마감' : '' }}{{ q.stale ? ' · 저장된 시세' : '' }}</span>
        </div>
      </div>
      <div class="row">
        <button @click="toggleWatch">{{ d.watched ? '★ 관심종목' : '☆ 관심 추가' }}</button>
        <button @click="alertOpen = true">🔔 알림</button>
        <router-link v-if="d.tradable" :to="{ path: '/discover/backtest', query: { symbol } }" class="btn">백테스트</router-link>
      </div>
    </div>

    <div class="tabs">
      <button v-for="t in tabs" :key="t[0]" :class="{ on: tab === t[0] }" @click="tab = t[0]">{{ t[1] }}</button>
    </div>

    <div class="grid" :class="{ 'g-side': hasSide }">
      <div class="col" style="gap:12px;min-width:0">
        <!-- 차트 -->
        <template v-if="tab === 'chart'">
          <div class="card">
            <div class="row wrap between" style="margin-bottom:8px">
              <div class="seg"><button v-for="t in tfs" :key="t[0]" :class="{ on: tf === t[0] }" @click="tf = t[0]">{{ t[1] }}</button></div>
              <div class="row wrap small">
                <label v-for="o in OVERLAYS" :key="o.key" class="row" style="gap:3px"><input type="checkbox" v-model="ov[o.key]" />{{ o.label }}</label>
                <select aria-label="보조지표 선택" v-model="osc" class="sm"><option value="">보조지표 없음</option><option v-for="o in OSCS" :key="o.key" :value="o.key">{{ o.label }}</option></select>
                <label class="row" style="gap:3px" v-if="isDaily"><input type="checkbox" v-model="showSignals" />신호</label>
                <label class="row" style="gap:3px"><input type="checkbox" v-model="showTrades" />내 매매</label>
              </div>
            </div>
            <div class="row wrap small" style="margin-bottom:6px">
              <span class="muted">그리기:</span>
              <div class="seg"><button :class="{ on: draw === '' }" @click="draw = ''">끄기</button><button :class="{ on: draw === 'hline' }" @click="draw = 'hline'">수평선</button><button :class="{ on: draw === 'trend' }" @click="draw = 'trend'; pending = null">추세선</button></div>
              <button class="sm" @click="addAvgLine" v-if="myPos">평단가선</button>
              <button class="sm ghost danger" @click="clearDrawings" v-if="drawings.length">모두 지우기 ({{ drawings.length }})</button>
              <span v-if="draw" class="faint">{{ draw === 'hline' ? '차트를 클릭한 가격에 선을 긋습니다' : pending ? '두 번째 점을 클릭하세요' : '첫 점을 클릭하세요' }}</span>
            </div>
            <div v-if="chartErr" class="empty">{{ chartErr }}</div>
            <PriceChart v-else :candles="candles" :overlays="overlaySeries" :oscillators="oscSeries" :markers="markers" :price-lines="priceLines" :trend-lines="trendLines"
              :intraday="!isDaily" :currency="cur" :line="isMacro" :show-volume="!isMacro" :height="520" @click="onChartClick" />
          </div>
          <div class="grid g2">
            <div class="card">
              <h3>시세 정보</h3>
              <dl class="kv">
                <dt>시가</dt><dd>{{ price(q.open ?? info.open, cur) }}</dd><dt>고가</dt><dd class="up">{{ price(q.high ?? info.high, cur) }}</dd>
                <dt>저가</dt><dd class="down">{{ price(q.low ?? info.low, cur) }}</dd><dt>거래량</dt><dd>{{ vol(q.volume ?? inst.volume) }}</dd>
                <dt>52주 최고</dt><dd>{{ price(inst.high52 ?? q.high52, cur) }}</dd><dt>52주 최저</dt><dd>{{ price(inst.low52 ?? q.low52, cur) }}</dd>
                <template v-if="inst.mcap"><dt>시가총액</dt><dd>{{ mcapFmt(inst.mcap, cur) }}</dd></template>
                <template v-if="inst.per != null"><dt>PER / PBR</dt><dd>{{ num(inst.per, 2) }} / {{ num(inst.pbr, 2) }}</dd></template>
                <template v-if="inst.eps != null"><dt>EPS / BPS</dt><dd>{{ price(inst.eps, cur) }} / {{ price(inst.bps, cur) }}</dd></template>
                <template v-if="info.est_per != null"><dt>추정 PER</dt><dd>{{ num(info.est_per, 2) }}</dd></template>
                <template v-if="inst.div_yield != null"><dt>배당수익률</dt><dd>{{ pct(inst.div_yield, 2, false) }}</dd></template>
                <template v-if="info.foreign_rate != null"><dt>외국인 소진율</dt><dd>{{ pct(info.foreign_rate, 2, false) }}</dd></template>
              </dl>
            </div>
            <div class="card">
              <div class="card-h"><h3>종목 메모</h3><button class="sm" @click="saveMemo">저장</button></div>
              <textarea v-model="memo" rows="7" placeholder="매수 이유, 목표가, 손절 기준 등" />
              <div v-if="info.description" class="small muted" style="margin-top:8px">{{ info.description }}</div>
            </div>
          </div>
          <div class="card" v-if="info.peers?.length">
            <h3>동종 업계</h3>
            <div class="row wrap">
              <router-link v-for="p in info.peers" :key="p.symbol" :to="'/stock/' + p.symbol" class="chip" style="padding:4px 10px">{{ p.name }} <span :class="cls(p.change_pct)">{{ pct(p.change_pct) }}</span></router-link>
            </div>
          </div>
        </template>

        <WhatIf v-else-if="tab === 'whatif'" :symbol="symbol" :line="isMacro" />

        <!-- 재무 -->
        <div v-else-if="tab === 'finance'" class="card">
          <div class="card-h"><h3>재무정보</h3><div class="seg"><button :class="{ on: finPeriod === 'annual' }" @click="finPeriod = 'annual'">연간</button><button :class="{ on: finPeriod === 'quarter' }" @click="finPeriod = 'quarter'">분기</button></div></div>
          <Loading v-if="!fin" />
          <div v-else-if="!fin.rows.length" class="empty">재무 자료가 없는 종목입니다</div>
          <template v-else>
            <div class="small faint" style="margin-bottom:6px">{{ fin.unit || (cur === 'KRW' ? '단위: 억원, %, 배' : '') }} · 음영 열은 증권사 추정치</div>
            <div class="scroll-x"><table class="t">
              <thead><tr><th>항목</th><th v-for="c in fin.columns" :key="c.key" class="num" :style="c.consensus ? 'background:var(--accent-soft)' : ''">{{ c.title }}</th></tr></thead>
              <tbody><tr v-for="r in fin.rows" :key="r.title"><td class="nowrap">{{ r.title }}</td>
                <td v-for="c in fin.columns" :key="c.key" class="num" :class="cls(r.values[c.key] < 0 ? -1 : 0)">{{ r.values[c.key] == null ? '-' : num(r.values[c.key], Math.abs(r.values[c.key]) < 100 ? 2 : 0) }}</td></tr></tbody>
            </table></div>
            <div v-if="revRow" style="margin-top:12px">
              <div class="small muted">매출액 추이 — 가로: 회계연도(분기) 말일 · 세로: 매출액 ({{ cur === 'USD' ? 'USD 백만' : '억 원' }})</div>
              <div class="bar-axis" :style="{ gridTemplateColumns: `repeat(${fin.columns.length}, 1fr)` }">
                <span v-for="c in fin.columns" :key="c.key" class="num-c small"><b>{{ revRow.values[c.key] == null ? '-' : num(revRow.values[c.key]) }}</b></span>
              </div>
              <MiniChart type="bar" :series="[{ values: fin.columns.map(c => revRow.values[c.key] ?? 0), colors: fin.columns.map(c => c.consensus ? 'var(--faint)' : 'var(--accent)') }]" :labels="fin.columns.map(c => c.title)" :h="120" />
              <div class="bar-axis" :style="{ gridTemplateColumns: `repeat(${fin.columns.length}, 1fr)` }">
                <span v-for="c in fin.columns" :key="c.key" class="num-c tiny muted">{{ c.title }}{{ c.consensus ? ' (추정)' : '' }}</span>
              </div>
            </div>
          </template>
        </div>

        <!-- 뉴스·공시·리포트 -->
        <div v-else-if="tab === 'news'" class="card">
          <div class="seg" style="margin-bottom:10px"><button v-for="k in [['news','뉴스'],['disclosures','공시'],['research','리포트']]" :key="k[0]" :class="{ on: newsTab === k[0] }" @click="newsTab = k[0]">{{ k[1] }} {{ news ? `(${news[k[0]].length})` : '' }}</button></div>
          <Loading v-if="!news" />
          <div v-else-if="!news[newsTab].length" class="empty">항목이 없습니다</div>
          <a v-for="n in news?.[newsTab] || []" :key="n.url" :href="n.url" target="_blank" rel="noopener" class="list-item" style="display:block">
            <div style="font-weight:600">{{ n.title }}</div>
            <div v-if="n.summary || n.preview" class="small muted ellipsis">{{ n.summary || n.preview }}</div>
            <div class="tiny faint">{{ n.office || n.author || n.broker }} · {{ n.datetime || n.date }}</div>
          </a>
        </div>

        <!-- 지표분석 -->
        <template v-else-if="tab === 'analysis'">
          <div v-if="!ana" class="card"><span class="spinner" /></div>
          <template v-else>
            <div class="grid g3">
              <div class="card" v-for="k in [['overall','종합'],['oscillators','오실레이터'],['moving_averages','이동평균']]" :key="k[0]">
                <div class="small muted">{{ k[1] }}</div>
                <div class="op-big" :class="opCls(ana.summary[k[0]].opinion)">{{ ana.summary[k[0]].opinion }}</div>
                <div class="small">매수 <b class="up">{{ ana.summary[k[0]].buy }}</b> · 중립 {{ ana.summary[k[0]].neutral }} · 매도 <b class="down">{{ ana.summary[k[0]].sell }}</b></div>
              </div>
            </div>
            <div class="grid g2">
              <div class="card flush"><table class="t"><thead><tr><th>오실레이터</th><th class="num">값</th><th class="num">판정</th></tr></thead>
                <tbody><tr v-for="o in ana.oscillators" :key="o.name" :title="o.rule"><td>{{ o.name }}<div class="tiny faint">{{ o.rule }}</div></td><td class="num">{{ o.value == null ? '-' : num(o.value, 2) }}</td><td class="num" :class="opCls(o.signal)">{{ o.signal }}</td></tr></tbody></table></div>
              <div class="card flush"><table class="t"><thead><tr><th>이동평균</th><th class="num">값</th><th class="num">판정</th></tr></thead>
                <tbody><tr v-for="o in ana.moving_averages" :key="o.name"><td>{{ o.name }}</td><td class="num">{{ price(o.value, cur) }}</td><td class="num" :class="opCls(o.signal)">{{ o.signal }}</td></tr></tbody></table></div>
            </div>
            <div class="card">
              <h3>피봇 지지·저항 (전일 기준)</h3>
              <div class="row wrap">
                <div v-for="k in ['s3','s2','s1','pp','r1','r2','r3']" :key="k" class="stat card" style="padding:8px 12px">
                  <span class="k">{{ k.toUpperCase() }}</span><span class="v" style="font-size:15px" :class="k[0] === 's' ? 'down' : k[0] === 'r' ? 'up' : ''">{{ price(ana.pivots[k], cur) }}</span></div>
              </div>
              <div class="small muted" style="margin-top:8px">ATR(14) {{ price(ana.atr, cur) }} · 최근 60일 연환산 변동성 {{ ana.volatility ?? '-' }}%</div>
            </div>
            <div class="card">
              <h3>이 종목의 매매신호 과거 성과</h3>
              <Loading v-if="!sigs" />
              <div class="scroll-x" v-else><table class="t">
                <thead><tr><th>전략</th><th class="num">발생</th><th class="num">5일 평균</th><th class="num">10일 평균</th><th class="num">20일 평균</th><th class="num">20일 적중률</th><th class="num">지금</th></tr></thead>
                <tbody><tr v-for="s in sigs" :key="s.strategy"><td><span class="chip" :class="s.side === 'buy' ? 'red' : 'bluedown'">{{ s.side === 'buy' ? '매수' : '매도' }}</span> {{ s.name }}</td>
                  <td class="num">{{ s.stats['20'].n }}</td>
                  <td v-for="h in ['5','10','20']" :key="h" class="num" :class="cls(s.stats[h].avg)">{{ pct(s.stats[h].avg) }}</td>
                  <td class="num">{{ s.stats['20'].win == null ? '-' : s.stats['20'].win + '%' }}</td>
                  <td class="num">{{ s.active ? '● 발생' : '' }}</td></tr></tbody>
              </table></div>
              <div class="tiny faint" style="margin-top:6px">적중률: 매수 신호는 이후 상승, 매도 신호는 이후 하락한 비율.</div>
              <ValidationNote kind="stock-signals" style="margin-top:10px" />
            </div>
          </template>
        </template>

        <!-- AI예측 -->
        <template v-else-if="tab === 'predict'">
          <div class="card">
            <div class="card-h"><h3>AI예측 — 비슷한 과거 차트가 이후 20거래일 동안 움직인 경로</h3>
              <div class="seg"><button v-for="w in [30, 60, 120]" :key="w" :class="{ on: win === w }" @click="win = w">최근 {{ w }}일</button></div></div>
            <div v-if="predErr" class="empty">{{ predErr }}</div>
            <div v-else-if="!pred" class="row"><span class="spinner" /><span class="small muted">전 종목 과거 차트에서 닮은 구간을 찾는 중입니다 (처음엔 수십 초 걸립니다)</span></div>
            <template v-else>
              <div class="grid g4" style="margin-bottom:12px">
                <div class="stat"><span class="k">투자의견</span><span class="v" :class="opCls(pred.opinion)">{{ pred.opinion }}</span></div>
                <div class="stat"><span class="k">20일 뒤 상승 확률</span><span class="v">{{ pred.up_prob }}%</span></div>
                <div class="stat"><span class="k">목표가 (상위 25%)</span><span class="v up">{{ price(pred.target, cur) }}</span></div>
                <div class="stat"><span class="k">손절가 (하위 25%)</span><span class="v down">{{ price(pred.stop, cur) }}</span></div>
              </div>
              <MiniChart :series="predSeries" :band-low="bandLow" :band-high="bandHigh" :split="pred.window - 1" :h="240" zero label="예측 경로" />
              <div class="small muted">왼쪽: 최근 {{ pred.window }}일 (현재가 = 0%). 점선 오른쪽: 닮은 구간 {{ pred.n_matches }}개의 이후 경로 중앙값과 25~75% 범위. 평균 유사도 {{ pred.avg_corr }} · 비교한 과거 구간 {{ num(pred.index_size) }}개</div>
              <div class="small" style="margin-top:6px">중앙값 {{ pct(pred.median) }} · 가중 기대값 {{ pct(pred.expected) }} · 범위 {{ pct(pred.p25) }} ~ {{ pct(pred.p75) }}</div>
            </template>
          </div>
          <div class="card" v-if="pred">
            <h3>가장 닮은 과거 구간</h3>
            <div class="grid g3">
              <div v-for="m in pred.matches" :key="m.symbol + m.start_ts" class="card" style="padding:10px">
                <div class="row between"><router-link :to="'/stock/' + m.symbol" class="link small"><b>{{ m.name }}</b></router-link><span class="tiny faint">유사도 {{ m.corr }}</span></div>
                <div class="tiny faint">{{ barDate(m.start_ts) }} ~ {{ barDate(m.end_ts) }}</div>
                <MiniChart :series="[{ values: m.series, color: 'var(--accent)' }]" :split="pred.window - 1" :h="70" zero />
                <div class="tiny">이후 5·10·20일: <span v-for="(f, i) in m.fwd" :key="i" :class="cls(f)">{{ pct(f, 1) }} </span></div>
              </div>
            </div>
          </div>
          <ValidationNote kind="ai" />
        </template>

        <!-- 유사차트 -->
        <div v-else-if="tab === 'similar'" class="card">
          <div class="card-h"><h3>지금 이 종목과 차트가 닮은 종목</h3>
            <div class="seg"><button v-for="w in [30, 60, 120]" :key="w" :class="{ on: win === w }" @click="win = w">최근 {{ w }}일</button></div></div>
          <Loading v-if="!sim" />
          <div v-else-if="!sim.length" class="empty">결과가 없습니다</div>
          <div class="grid g3">
            <router-link v-for="s in sim" :key="s.symbol" :to="'/stock/' + s.symbol" class="card" style="padding:10px">
              <div class="row between"><b class="small">{{ s.name }}</b><span class="tiny faint">유사도 {{ s.corr }}</span></div>
              <MiniChart :series="[{ values: s.series, color: 'var(--accent)' }, { values: mySeries, color: 'var(--faint)', dashed: true }]" :h="70" />
              <div class="tiny"><span :class="cls(s.change_pct)">{{ pct(s.change_pct) }}</span> <span class="faint">점선 = {{ inst.name }}</span></div>
            </router-link>
          </div>
        </div>

        <!-- 토론 -->
        <div v-else-if="tab === 'posts'" class="card">
          <PostList kind="timeline" :symbol="symbol" />
        </div>
      </div>

      <!-- 오른쪽 -->
      <div v-if="hasSide" class="col" style="gap:12px">
        <OrderPanel :symbol="symbol" :tradable="d.tradable" @ordered="loadMyTrades" />
        <div class="card" v-if="d.has_orderbook">
          <div class="card-h"><h3>호가</h3><span class="tiny faint">{{ symbol.startsWith('KR:') ? '5단계' : '10단계' }}</span></div>
          <div v-if="ob">
            <div v-for="a in ob.asks" :key="'a' + a.price" class="ob"><span class="bar" :style="{ width: barW(a.qty) }" style="background:var(--down-soft)" /><span class="num grow">{{ vol(a.qty) }}</span><span class="num down" style="width:42%">{{ price(a.price, cur) }}</span><span class="grow" /></div>
            <div v-for="b in ob.bids" :key="'b' + b.price" class="ob"><span class="grow" /><span class="num up" style="width:42%">{{ price(b.price, cur) }}</span><span class="num grow">{{ vol(b.qty) }}</span><span class="bar r" :style="{ width: barW(b.qty) }" style="background:var(--up-soft)" /></div>
            <div class="row between tiny muted" style="margin-top:6px"><span>매도잔량 {{ vol(ob.total_ask) }}</span><span>매수잔량 {{ vol(ob.total_bid) }}</span></div>
          </div>
        </div>
        <div class="card" v-if="trend.length">
          <h3>투자자별 매매 (주)</h3>
          <table class="t"><thead><tr><th>일자</th><th class="num">외국인</th><th class="num">기관</th><th class="num">개인</th></tr></thead>
            <tbody><tr v-for="t in trend.slice(0, 10)" :key="t.date"><td class="small">{{ t.date.slice(4, 6) }}/{{ t.date.slice(6) }}</td>
              <td class="num small" :class="cls(t.foreign)">{{ vol(t.foreign) }}</td><td class="num small" :class="cls(t.organ)">{{ vol(t.organ) }}</td><td class="num small" :class="cls(t.individual)">{{ vol(t.individual) }}</td></tr></tbody></table>
        </div>
      </div>
    </div>

    <AlertModal v-if="alertOpen" :symbol="symbol" :name="inst.name" :price="q.price" @close="alertOpen = false" />
  </div>
  <div v-else-if="err" class="empty">{{ err }}</div>
  <Loading v-else />
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AlertModal from '../components/AlertModal.vue'
import WhatIf from '../components/WhatIf.vue'
import ValidationNote from '../components/ValidationNote.vue'
import MiniChart from '../components/MiniChart.vue'
import OrderPanel from '../components/OrderPanel.vue'
import PostList from '../components/PostList.vue'
import PriceChart from '../components/PriceChart.vue'
import { api, toast } from '../lib/api'
import { accountId } from '../lib/accounts'
import { barDate, cls, curOf, macro, MARKET_LABEL, mcap as mcapFmt, num, pct, price, signed, vol } from '../lib/fmt'
import { useInterval, useQuotes } from '../lib/poll'

const route = useRoute()
const symbol = computed(() => route.params.symbol)
const cur = computed(() => curOf(symbol.value))
const isMacro = computed(() => /^(IX|FX|CM|RT):/.test(symbol.value))
const d = ref(null); const err = ref('')
const inst = computed(() => d.value?.instrument || {})
const info = computed(() => d.value?.info || {})
const quotes = useQuotes(computed(() => [symbol.value]), 3000)
const q = computed(() => quotes[symbol.value] || d.value?.quote || {})
const TABS = [['chart', '차트'], ['whatif', '샀더라면'], ['finance', '재무'], ['news', '뉴스·공시'], ['analysis', '지표분석'], ['predict', 'AI예측'], ['similar', '유사차트'], ['posts', '토론']]
const tab = ref(route.query.tab || 'chart')
// 종목 종류에 맞는 탭만 보인다: 재무·뉴스는 국내·미국 주식, 지수·환율은 차트 위주
const tabs = computed(() => TABS.filter(t => {
  const p = symbol.value.split(':')[0]
  if (t[0] === 'finance' || t[0] === 'news') return p === 'KR' || p === 'US'
  if (t[0] === 'predict' || t[0] === 'similar') return !isMacro.value
  return true
}))
const hasSide = computed(() => !!d.value && (d.value.tradable || d.value.has_orderbook))

async function load() {
  try { d.value = await api.get(`/stock/${symbol.value}`); memo.value = d.value.memo || '' } catch (e) { err.value = e.message }
}
load()

// ── 차트 ──
const tfs = computed(() => {
  const base = [['day', '일'], ['week', '주'], ['month', '월']]
  if (symbol.value.startsWith('KR:') || symbol.value.startsWith('CR:') || symbol.value === 'IX:KOSPI' || symbol.value === 'IX:KOSDAQ') return [['1m', '1분'], ['5m', '5분'], ['15m', '15분'], ['60m', '60분'], ...base]
  if (symbol.value.startsWith('US:')) return [['5m', '5분'], ['15m', '15분'], ['60m', '60분'], ...base]
  return base
})
const tf = ref('day')
const isDaily = computed(() => ['day', 'week', 'month'].includes(tf.value))
const candles = ref([]); const chartErr = ref('')
const OVERLAYS = [{ key: 'ma5', label: 'MA5', spec: { ind: 'sma', p: [5] }, color: '#f59e0b' }, { key: 'ma20', label: 'MA20', spec: { ind: 'sma', p: [20] }, color: '#10b981' },
  { key: 'ma60', label: 'MA60', spec: { ind: 'sma', p: [60] }, color: '#8b5cf6' }, { key: 'ma120', label: 'MA120', spec: { ind: 'sma', p: [120] }, color: '#64748b' },
  { key: 'bb', label: '볼린저', spec: { ind: 'bb', p: [20, 2] }, color: '#94a3b8' }, { key: 'vwap', label: 'VWAP', spec: { ind: 'vwap', p: [20] }, color: '#ec4899' }]
const OSCS = [{ key: 'rsi', label: 'RSI(14)', spec: { ind: 'rsi', p: [14] } }, { key: 'macd', label: 'MACD', spec: { ind: 'macd', p: [12, 26, 9] } },
  { key: 'stoch', label: '스토캐스틱', spec: { ind: 'stoch', p: [14, 3, 3] } }, { key: 'cci', label: 'CCI', spec: { ind: 'cci', p: [20] } },
  { key: 'mfi', label: 'MFI', spec: { ind: 'mfi', p: [14] } }, { key: 'obv', label: 'OBV', spec: { ind: 'obv', p: [] } }, { key: 'adx', label: 'ADX', spec: { ind: 'adx', p: [14] } }]
const ov = reactive({ ma5: true, ma20: true, ma60: true, ma120: false, bb: false, vwap: false })
const osc = ref('rsi')
const indData = ref([])
const showSignals = ref(!isMacro.value); const showTrades = ref(true)
const sigs = ref(null); const myTrades = ref([])

async function loadCandles() {
  chartErr.value = ''
  try {
    const r = await api.get(`/stock/${symbol.value}/candles`, { tf: tf.value, count: isDaily.value ? 800 : 600 }, { quiet: true })
    candles.value = r.candles
    if (!r.candles.length) chartErr.value = '이 주기의 차트 데이터가 없습니다'
  } catch { chartErr.value = '차트를 불러오지 못했습니다' }
  loadInd()
}
async function loadInd() {
  const specs = [...OVERLAYS.filter(o => ov[o.key]).map(o => o.spec), ...OSCS.filter(o => o.key === osc.value).map(o => o.spec)]
  indData.value = specs.length ? await api.post(`/stock/${symbol.value}/indicators`, { tf: tf.value, count: isDaily.value ? 800 : 600, specs }, { quiet: true }).catch(() => []) : []
}
watch(tf, loadCandles)
watch([ov, osc], loadInd, { deep: true })
loadCandles()
// 장중에는 마지막 봉을 현재가로 갱신하고, 분봉은 주기적으로 다시 받는다
watch(() => q.value.price, p => {
  if (!p || !candles.value.length || !isDaily.value || tf.value !== 'day') return
  const last = [...candles.value[candles.value.length - 1]]
  last[4] = p; last[2] = Math.max(last[2], p); last[3] = Math.min(last[3], p)
  candles.value = [...candles.value.slice(0, -1), last]
})
useInterval(() => { if (!isDaily.value && tab.value === 'chart') loadCandles() }, 20000)

const overlaySeries = computed(() => indData.value.filter(s => s.ind !== OSCS.find(o => o.key === osc.value)?.spec.ind).map(s => {
  const o = OVERLAYS.find(x => x.spec.ind === s.ind && JSON.stringify(x.spec.p) === JSON.stringify(s.p)) || OVERLAYS.find(x => x.spec.ind === s.ind)
  return { data: s.data, color: o?.color || '#888', dashed: s.ind === 'bb' && s.out !== 'mid' }
}))
const oscSeries = computed(() => {
  const spec = OSCS.find(o => o.key === osc.value)?.spec
  if (!spec) return []
  const colors = ['#2563eb', '#f59e0b', '#10b981']
  return indData.value.filter(s => s.ind === spec.ind).map((s, i) => ({ data: s.data, color: colors[i % 3], histogram: s.out === 'hist', title: s.out || spec.ind.toUpperCase() }))
})
const markers = computed(() => {
  const out = []
  if (showSignals.value && tf.value === 'day' && sigs.value && candles.value.length) {
    // 최근 60봉만, 한 봉에 방향별로 하나씩 (여러 전략이 겹치면 개수만 표시)
    const since = candles.value[Math.max(0, candles.value.length - 60)][0]
    const byBar = new Map()
    for (const s of sigs.value) for (const p of s.points) if (p.ts >= since) {
      const k = p.ts + s.side; const e = byBar.get(k) || { ts: p.ts, side: s.side, names: [] }; e.names.push(s.name.split(' ')[0]); byBar.set(k, e)
    }
    for (const e of byBar.values()) out.push({ time: e.ts, position: e.side === 'buy' ? 'belowBar' : 'aboveBar', color: e.side === 'buy' ? '#e0353c' : '#2366d1',
      shape: e.side === 'buy' ? 'arrowUp' : 'arrowDown', text: e.names.length > 1 ? `${e.names.length}개` : e.names[0] })
  }
  if (showTrades.value && isDaily.value) {
    for (const t of myTrades.value) {
      const day = Math.floor((t.ts + 9 * 3600) / 86400) * 86400
      const bar = [...candles.value].reverse().find(c => c[0] <= day)
      if (bar) out.push({ time: bar[0], position: t.side === 'buy' ? 'belowBar' : 'aboveBar', color: '#f59e0b', shape: 'circle', text: (t.side === 'buy' ? '매수 ' : '매도 ') + num(t.qty, symbol.value.startsWith('CR:') ? 4 : 0) })
    }
  }
  // 같은 봉에 여러 마커가 겹치면 시간 순서만 맞춘다
  return out.sort((a, b) => a.time - b.time)
})
async function loadSignals() { if (!isMacro.value || true) sigs.value = await api.get(`/stock/${symbol.value}/signals`, null, { quiet: true }).catch(() => []) }
async function loadMyTrades() {
  if (!accountId.value) return
  const a = await api.get(`/trade/accounts/${accountId.value}`, null, { quiet: true }).catch(() => null)
  if (!a) return
  myTrades.value = a.trades.filter(t => t.symbol === symbol.value)
  myPos.value = a.positions.find(p => p.symbol === symbol.value) || null
}
const myPos = ref(null)
loadSignals(); loadMyTrades()

// ── 그리기 ──
const drawings = ref([]); const draw = ref(''); const pending = ref(null)
api.get(`/stock/${symbol.value}/drawings`, null, { quiet: true }).then(r => (drawings.value = r)).catch(() => {})
const priceLines = computed(() => drawings.value.filter(x => x.type === 'hline').map(x => ({ price: x.price, title: x.title || '', color: x.color })))
const trendLines = computed(() => drawings.value.filter(x => x.type === 'trend').map(x => ({ points: x.points })))
function saveDrawings() { api.put(`/stock/${symbol.value}/drawings`, drawings.value, { quiet: true }) }
function onChartClick({ time, price: p }) {
  if (!draw.value || p == null) return
  if (draw.value === 'hline') { drawings.value.push({ type: 'hline', price: +p.toPrecision(8) }); saveDrawings() }
  else if (draw.value === 'trend' && time) {
    if (!pending.value) pending.value = [time, p]
    else { drawings.value.push({ type: 'trend', points: [pending.value, [time, p]] }); pending.value = null; saveDrawings() }
  }
}
function addAvgLine() { drawings.value.push({ type: 'hline', price: myPos.value.avg_price, title: '평단가', color: '#f59e0b' }); saveDrawings() }
function clearDrawings() { drawings.value = []; saveDrawings() }

// ── 기타 탭 ──
const finPeriod = ref('annual'); const fin = ref(null)
const revRow = computed(() => fin.value?.rows.find(r => r.title === '매출액'))
const newsTab = ref('news'); const news = ref(null)
const ana = ref(null)
const win = ref(60); const pred = ref(null); const predErr = ref(''); const sim = ref(null)
watch([tab, finPeriod], async () => {
  if (tab.value === 'finance') { fin.value = null; fin.value = await api.get(`/stock/${symbol.value}/finance`, { period: finPeriod.value }, { quiet: true }).catch(() => ({ columns: [], rows: [] })) }
  if (tab.value === 'news' && !news.value) news.value = await api.get(`/stock/${symbol.value}/news`, null, { quiet: true }).catch(() => ({ news: [], disclosures: [], research: [] }))
  if (tab.value === 'analysis' && !ana.value) ana.value = await api.get(`/stock/${symbol.value}/analysis`, null, { quiet: true }).catch(() => null)
}, { immediate: true })
watch([tab, win], async () => {
  if (tab.value === 'predict') { pred.value = null; predErr.value = ''; try { pred.value = await api.get(`/stock/${symbol.value}/predict`, { window: win.value }, { quiet: true }) } catch (e) { predErr.value = e.message } }
  if (tab.value === 'similar') { sim.value = null; sim.value = await api.get(`/stock/${symbol.value}/similar`, { window: win.value }, { quiet: true }).catch(() => []) }
}, { immediate: true })
const predSeries = computed(() => pred.value ? [
  { values: pred.value.query, color: 'var(--text)', width: 2 },
  { values: [...Array(pred.value.window - 1).fill(null), 0, ...pred.value.path.median], color: 'var(--accent)', width: 2.2, dashed: true }] : [])
const bandLow = computed(() => pred.value ? [0, ...pred.value.path.p25] : null)
const bandHigh = computed(() => pred.value ? [0, ...pred.value.path.p75] : null)
const mySeries = computed(() => { const c = candles.value.slice(-win.value).map(r => r[4]); const last = c[c.length - 1]; return c.map(x => (x / last - 1) * 100) })

// ── 호가·수급 ──
const ob = ref(null); const trend = ref([])
async function loadOb() { if (d.value?.has_orderbook) ob.value = await api.get(`/stock/${symbol.value}/orderbook`, null, { quiet: true }).catch(() => ob.value) }
watch(d, () => { loadOb(); if (symbol.value.startsWith('KR:')) api.get(`/stock/${symbol.value}/trend`, null, { quiet: true }).then(r => (trend.value = r)).catch(() => {}) })
useInterval(loadOb, 3000)
const obMax = computed(() => Math.max(1, ...(ob.value ? [...ob.value.asks, ...ob.value.bids].map(x => x.qty || 0) : [1])))
function barW(qty) { return (qty / obMax.value * 100) + '%' }

// ── 메모·관심·알림 ──
const memo = ref('')
async function saveMemo() { await api.put(`/stock/${symbol.value}/memo`, { body: memo.value }); toast('메모를 저장했습니다', 'ok') }
async function toggleWatch() { const r = await api.post('/user/watchlist/toggle', { symbol: symbol.value }); d.value.watched = r.watched; toast(r.watched ? '관심종목에 추가했습니다' : '관심종목에서 뺐습니다', 'ok') }
const alertOpen = ref(false)
function opCls(o) { return o?.includes('매수') ? 'up' : o?.includes('매도') ? 'down' : 'muted' }
</script>

<style scoped>
.bigp { font-size: 26px; font-weight: 800; font-variant-numeric: tabular-nums; }
.op-big { font-size: 22px; font-weight: 800; margin: 2px 0; }
.bar-axis { display: grid; padding: 0 6px; }
.num-c { text-align: center; font-variant-numeric: tabular-nums; }
.ob { position: relative; display: flex; align-items: center; gap: 6px; font-size: 12px; padding: 2px 0; }
.ob .bar { position: absolute; top: 1px; bottom: 1px; left: 0; opacity: .9; z-index: 0; border-radius: 2px; }
.ob .bar.r { left: auto; right: 0; }
.ob span:not(.bar) { position: relative; z-index: 1; }
</style>
