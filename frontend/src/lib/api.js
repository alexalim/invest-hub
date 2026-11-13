// API 클라이언트. 쿠키 세션을 쓰고, 401이면 로그인 화면으로 보낸다. 오류 문구는 토스트로 띄운다.
import { reactive } from 'vue'

export const toasts = reactive([])
let seq = 0
export function toast(msg, kind = 'error') {
  const id = ++seq
  toasts.push({ id, msg, kind })
  setTimeout(() => { const i = toasts.findIndex(t => t.id === id); if (i >= 0) toasts.splice(i, 1) }, 4500)
}

let onUnauthorized = () => {}
export function setUnauthorizedHandler(fn) { onUnauthorized = fn }

async function request(method, path, body, { quiet = false } = {}) {
  const opt = { method, credentials: 'same-origin', headers: {} }
  if (body !== undefined) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body) }
  let r
  try { r = await fetch('/api' + path, opt) } catch (e) {
    if (!quiet) toast('서버에 연결할 수 없습니다')
    const err = new Error('서버에 연결할 수 없습니다. 인터넷 연결을 확인하고 잠시 뒤 다시 시도해 주세요'); err.status = 0; throw err
  }
  // 로그인·가입의 401 은 "아이디·비밀번호가 틀림"이므로 세션 만료로 다루지 않고 문구를 그대로 넘긴다
  if (r.status === 401 && !/^\/auth\/(login|register)$/.test(path)) { onUnauthorized(); throw new Error('unauthorized') }
  const ct = r.headers.get('content-type') || ''
  const data = ct.includes('json') ? await r.json().catch(() => null) : await r.text()
  if (!r.ok) {
    const msg = (data && data.detail) ? (typeof data.detail === 'string' ? data.detail : '입력값을 확인해 주세요')
      : r.status >= 500 ? '서버가 응답하지 않습니다. 잠시 뒤 다시 시도해 주세요' : `오류 ${r.status}`
    if (!quiet) toast(msg)
    const err = new Error(msg); err.status = r.status; throw err
  }
  return data
}

export function qs(params) {
  const p = Object.entries(params || {}).filter(([, v]) => v !== undefined && v !== null && v !== '')
  return p.length ? '?' + p.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&') : ''
}

export const api = {
  get: (p, params, o) => request('GET', p + qs(params), undefined, o),
  post: (p, b, o) => request('POST', p, b ?? {}, o),
  put: (p, b, o) => request('PUT', p, b ?? {}, o),
  patch: (p, b, o) => request('PATCH', p, b ?? {}, o),
  del: (p, o) => request('DELETE', p, undefined, o),
}

export const session = reactive({ user: null, firstRun: false, ready: false })
