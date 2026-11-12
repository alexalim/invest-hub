<template>
  <div class="wrap">
    <div class="card box">
      <h1>Invest Hub</h1>
      <p class="muted small">트레이딩 도구와 스타트업 투자 DB를 한곳에서</p>
      <div v-if="session.firstRun" class="notice small">처음 실행입니다. 지금 만드는 계정이 관리자가 됩니다. 서버 콘솔이나 <code>data/setup_code.txt</code>에 있는 설치 코드를 입력하세요.</div>
      <div class="seg" style="margin:12px 0" v-if="!session.firstRun">
        <button :class="{ on: mode === 'login' }" @click="mode = 'login'">로그인</button>
        <button :class="{ on: mode === 'register' }" @click="mode = 'register'">가입</button>
      </div>
      <form class="col" @submit.prevent="submit">
        <label class="field">아이디<input v-model="f.username" autocomplete="username" required /></label>
        <label class="field">비밀번호<input v-model="f.password" type="password" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" required /></label>
        <template v-if="mode === 'register'">
          <label class="field">닉네임<input v-model="f.nickname" /></label>
          <label class="field">{{ session.firstRun ? '설치 코드' : '초대 코드 (관리자에게 받으세요)' }}<input v-model="f.invite" required /></label>
        </template>
        <button class="primary" :disabled="busy">{{ mode === 'login' ? '로그인' : '가입하고 시작' }}</button>
      </form>
    </div>
  </div>
</template>
<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, session } from '../lib/api'

const router = useRouter(); const route = useRoute()
const mode = ref(session.firstRun ? 'register' : 'login')
const f = reactive({ username: '', password: '', nickname: '', invite: '' })
const busy = ref(false)
async function submit() {
  busy.value = true
  try {
    await api.post(mode.value === 'login' ? '/auth/login' : '/auth/register', f)
    const r = await api.get('/auth/me'); session.user = r.user; session.firstRun = false
    router.replace(route.query.next || '/')
  } catch { /* 토스트로 안내됨 */ } finally { busy.value = false }
}
</script>
<style scoped>
.wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 16px; }
.box { width: min(380px, 100%); padding: 24px; }
</style>
