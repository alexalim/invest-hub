<template>
  <div>
    <div class="page-h"><div><h1>설정·데이터 수집</h1><div class="muted small">내 계정, 다른 사용자 초대, 외부 데이터 키, 수집 작업 상태</div></div></div>
    <div class="grid g2">
      <div class="card"><h3>내 계정</h3>
        <div class="col">
          <div class="row"><label class="field grow">닉네임<input v-model="nick" /></label><button style="align-self:flex-end" @click="saveNick">저장</button></div>
          <div class="row wrap"><input v-model="pw.old" type="password" placeholder="현재 비밀번호" autocomplete="current-password" /><input v-model="pw.new" type="password" placeholder="새 비밀번호 (6자 이상)" autocomplete="new-password" /><button @click="savePw">비밀번호 변경</button></div>
          <div><button class="danger" @click="logout">로그아웃</button></div>
        </div></div>
      <div class="card" v-if="st?.is_admin"><h3>사용자 초대</h3>
        <p class="small muted">같은 네트워크의 사람이 이 PC 주소로 접속해 아래 초대 코드로 가입할 수 있습니다.</p>
        <div class="row"><input aria-label="초대 코드" v-model="invite" class="grow" /><button @click="saveSettings({ invite_code: invite })">초대 코드 저장</button></div>
        <div class="small" style="margin-top:8px">접속 주소: <code>{{ origin }}</code></div>
        <table class="t" style="margin-top:10px"><tbody><tr v-for="u in users" :key="u.id"><td>{{ u.nickname }} <span class="faint small">{{ u.username }}</span></td><td>{{ u.is_admin ? '관리자' : '' }}</td>
          <td class="num"><button v-if="u.id !== session.user.id" class="sm ghost danger" @click="delUser(u)">삭제</button></td></tr></tbody></table>
      </div>
    </div>
    <div class="card" style="margin-top:12px" v-if="st?.is_admin">
      <h3>외부 데이터 키 <span class="small muted">(선택 — 스타트업 기업 프로필의 공시·재무·고용 정보에 씁니다)</span></h3>
      <div class="grid g2">
        <div class="col">
          <div class="row"><b class="small">DART 전자공시</b><span class="chip" :class="st.keys.dart_key ? 'green' : ''">{{ st.keys.dart_key ? '설정됨' : '없음' }}</span></div>
          <div class="small muted">opendart.fss.or.kr → 인증키 신청 (무료, 즉시 발급). 기업 개황·사업보고서 재무·공시 목록.</div>
          <div class="row"><input v-model="keys.dart_key" type="password" placeholder="40자리 인증키" class="grow" autocomplete="off" /><button @click="saveSettings({ dart_key: keys.dart_key })">저장</button></div>
        </div>
        <div class="col">
          <div class="row"><b class="small">공공데이터포털</b><span class="chip" :class="st.keys.data_go_kr_key ? 'green' : ''">{{ st.keys.data_go_kr_key ? '설정됨' : '없음' }}</span></div>
          <div class="small muted">data.go.kr에서 '금융위원회_기업기본정보', '금융위원회_기업재무정보', '국민연금공단_가입 사업장 내역' 활용 신청 후 일반 인증키(Decoding). 비상장 기업 재무·고용 인원.</div>
          <div class="row"><input v-model="keys.data_go_kr_key" type="password" placeholder="인증키" class="grow" autocomplete="off" /><button @click="saveSettings({ data_go_kr_key: keys.data_go_kr_key })">저장</button></div>
        </div>
      </div>
      <div class="notice warn small" style="margin-top:10px">공공데이터포털 연동은 키 없이 만들어 실제 응답으로는 아직 확인하지 못했습니다. 키를 넣고 기업 화면에서 '불러오기'를 눌렀을 때 오류가 나면 메시지가 화면에 표시됩니다.</div>
    </div>
    <div class="card" style="margin-top:12px" v-if="st">
      <div class="card-h"><h3>데이터 현황</h3><button class="sm" @click="load">새로고침</button></div>
      <div class="row wrap">
        <div v-for="(v, k) in st.counts" :key="k" class="stat card" style="padding:8px 12px"><span class="k">{{ COUNT_LABEL[k] || k }}</span><span class="v" style="font-size:16px">{{ num(v) }}</span></div>
      </div>
      <div v-if="st.is_admin" class="scroll-x" style="margin-top:12px"><table class="t">
        <thead><tr><th>작업</th><th>상태</th><th>마지막 시작</th><th>마지막 완료</th><th>결과</th><th v-if="st.is_admin"></th></tr></thead>
        <tbody><tr v-for="j in st.jobs" :key="j.name"><td>{{ j.label }}<div class="tiny faint">{{ j.name }}</div></td>
          <td><span class="chip" :class="{ green: j.status === 'ok', orange: j.status === 'running', red: j.status === 'error' || j.status === 'interrupted' }">{{ STATUS[j.status] || '대기' }}</span></td>
          <td class="small">{{ j.started_at ? datetime(j.started_at) : '-' }}</td><td class="small">{{ j.finished_at ? datetime(j.finished_at) : '-' }}</td>
          <td class="small muted ellipsis" style="max-width:360px" :title="j.detail">{{ j.detail }}</td>
          <td v-if="st.is_admin"><button class="sm" :disabled="j.status === 'running'" @click="runJob(j)">지금 실행</button></td></tr></tbody></table></div>
      <div v-if="st.intraday" class="notice small" style="margin-top:10px">
        <b>5분봉 자료</b> {{ st.intraday.symbols }}종목 · {{ st.intraday.first }} ~ {{ st.intraday.last }} ({{ st.intraday.days }}거래일) · {{ st.intraday.mb }}MB
        <template v-if="st.intraday.kis"> · 한투 1년치 받기: {{ st.intraday.kis.done_symbols }}/{{ st.intraday.kis.symbols }}종목 완료{{ st.intraday.kis.finished ? ' (끝)' : '' }}, 마지막 갱신 {{ datetime(st.intraday.kis.at) }}</template>
      </div>
      <div class="tiny faint" style="margin-top:8px">시세 목록은 장중 45초, 코인 20초마다 갱신합니다. 일봉은 국내 15:50·20:10, 미국 06:40, 코인 09:10(한국 시각)에 다시 받습니다.</div>
    </div>
  </div>
</template>
<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, session, toast } from '../lib/api'
import { datetime, num } from '../lib/fmt'
import { useInterval } from '../lib/poll'
const router = useRouter()
const st = ref(null); const users = ref([]); const invite = ref(''); const nick = ref(session.user?.nickname || '')
const pw = reactive({ old: '', new: '' }); const keys = reactive({ dart_key: '', data_go_kr_key: '' })
const origin = location.origin
const STATUS = { ok: '완료', running: '실행 중', error: '오류', interrupted: '중단됨' }
const COUNT_LABEL = { instruments: '종목', candles: '일봉 행', candle_symbols: '일봉 종목', signals: '매매신호', articles: '기사', deals: '투자 건', companies: '기업', investors: '투자자', funds: '펀드', grants: '지원사업', users: '사용자' }
async function load() {
  st.value = await api.get('/admin/status')
  if (st.value.is_admin) { invite.value = st.value.invite_code || ''; users.value = await api.get('/admin/users') }
}
async function saveSettings(p) { await api.post('/admin/settings', p); toast('저장했습니다', 'ok'); keys.dart_key = ''; keys.data_go_kr_key = ''; load() }
async function runJob(j) { await api.post(`/admin/jobs/${j.name}`); toast(`${j.label} 작업을 시작했습니다`, 'ok'); setTimeout(load, 1500) }
async function saveNick() { await api.post('/auth/profile', { nickname: nick.value }); session.user.nickname = nick.value; toast('저장했습니다', 'ok') }
async function savePw() { await api.post('/auth/password', pw); pw.old = pw.new = ''; toast('비밀번호를 바꿨습니다', 'ok') }
async function logout() { await api.post('/auth/logout'); session.user = null; router.push('/login') }
async function delUser(u) { if (window.confirm(`${u.nickname} 계정을 삭제할까요?`)) { await api.del(`/admin/users/${u.id}`); load() } }
load(); useInterval(load, 15000)
</script>
