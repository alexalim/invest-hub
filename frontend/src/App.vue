<template>
  <div v-if="route.meta.bare"><router-view /></div>
  <div v-else class="shell">
    <aside class="nav" :class="{ open: navOpen }">
      <router-link to="/" class="brand" @click="navOpen = false">
        <svg width="22" height="22" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="var(--accent)"/><path d="M7 21l6-7 4 4 8-9" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
        Invest Hub
      </router-link>
      <div class="seg areas"><button v-for="a in AREAS" :key="a.key" :class="{ on: area === a.key }" @click="switchArea(a.key)">{{ a.label }}</button></div>
      <nav @click="navOpen = false">
        <div class="group mine">
          <div class="gt">내 메뉴</div>
          <template v-if="!favItems.length">
            <div v-for="m in frequent" :key="'q' + m.to" class="item"><router-link :to="m.to" :class="{ active: isActive(m) }">{{ m.label }}</router-link></div>
            <div class="tiny faint" style="padding:2px 10px 6px">{{ frequent.length ? '자주 여는 화면입니다. ' : '' }}메뉴 오른쪽 ☆를 누르면 여기 고정됩니다</div>
          </template>
          <div v-for="(m, i) in favItems" :key="'f' + m.to" class="item">
            <router-link :to="m.to" :class="{ active: isActive(m), live: m.admin }">{{ m.label }}</router-link>
            <span class="tools" @click.stop.prevent>
              <button class="ghost tiny" :disabled="i === 0" title="위로" @click="moveFav(i, -1)">▲</button>
              <button class="ghost tiny" :disabled="i === favItems.length - 1" title="아래로" @click="moveFav(i, 1)">▼</button>
              <button class="ghost tiny star on" title="내 메뉴에서 빼기" @click="toggleFav(m.to)">★</button>
            </span>
          </div>
        </div>
        <div v-for="g in menu" :key="g.title" class="group">
          <button class="gt fold" :aria-expanded="isOpen(g)" @click.stop="toggleGroup(g)"><span>{{ g.title }}</span><span class="arrow">{{ isOpen(g) ? '▾' : '▸' }}</span></button>
          <div v-for="m in isOpen(g) ? g.items.filter(x => !x.admin || session.user?.is_admin) : []" :key="m.to" class="item">
            <router-link :to="m.to" :class="{ active: isActive(m), live: m.admin }">{{ m.label }}</router-link>
            <button class="ghost tiny star" :class="{ on: favs.includes(m.to) }" :title="favs.includes(m.to) ? '내 메뉴에서 빼기' : '내 메뉴에 담기'" @click.stop.prevent="toggleFav(m.to)">{{ favs.includes(m.to) ? '★' : '☆' }}</button>
          </div>
        </div>
        <div class="group foot"><div class="item"><router-link to="/settings" :class="{ active: route.path === '/settings' }">⚙ 설정·데이터 수집</router-link></div></div>
      </nav>
    </aside>
    <div class="main">
      <header class="top">
        <button class="ghost burger" @click="navOpen = !navOpen" aria-label="메뉴">☰</button>
        <SymbolSearch class="search" placeholder="종목 검색 (이름·코드) — 국내·미국·코인·지수" @select="s => router.push('/stock/' + s.symbol)" />
        <div class="row">
          <div class="bell-wrap">
            <button class="ghost" @click="toggleBell" aria-label="알림">🔔<span v-if="notif.unread" class="badge">{{ notif.unread }}</span></button>
            <div v-if="bellOpen" class="bell card">
              <div class="card-h"><h3>알림</h3><router-link to="/alerts" class="link small" @click="bellOpen = false">알림 설정</router-link></div>
              <div v-if="!notif.items.length" class="empty small">새 알림이 없습니다</div>
              <div v-for="n in notif.items" :key="n.id" class="list-item" @click="openNotif(n)" style="cursor:pointer">
                <div class="row between"><b class="small">{{ n.title }}</b><span class="tiny faint">{{ ago(n.created_at) }}</span></div>
                <div class="small muted">{{ n.body }}</div>
              </div>
            </div>
          </div>
          <button class="ghost" @click="toggleTheme" :aria-label="'테마 전환'">{{ dark ? '☀️' : '🌙' }}</button>
          <router-link to="/settings" class="btn ghost small ellipsis" style="max-width:110px;display:inline-block" :title="session.user?.nickname + ' 설정'">{{ session.user?.nickname }}</router-link>
        </div>
      </header>
      <main class="content">
        <div v-if="tabs" class="tabs page-tabs"><router-link v-for="t in tabs" :key="t.to" :to="t.to" :class="{ on: isActive(t) }">{{ t.label }}</router-link></div>
        <router-view :key="route.path" />
      </main>
    </div>
    <div v-if="navOpen" class="nav-back" @click="navOpen = false" />
  </div>
  <div class="toasts"><div v-for="t in toasts" :key="t.id" class="toast" :class="t.kind">{{ t.msg }}</div></div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SymbolSearch from './components/SymbolSearch.vue'
import { api, session, toasts } from './lib/api'
import { ago } from './lib/fmt'
import { useInterval } from './lib/poll'
import { stored } from './lib/prefs'

const route = useRoute()
const router = useRouter()
const navOpen = ref(false)
const bellOpen = ref(false)
const dark = ref(document.documentElement.dataset.theme === 'dark')
const notif = reactive({ unread: 0, items: [] })

// 메뉴는 두 영역으로 나눈다. 영역마다 '보기 → 찾기 → 거래 → 함께' 순서로 묶는다.
const AREAS = [
  { key: 'stock', label: '주식·코인', groups: [
    { title: '내 종목', items: [{ to: '/watchlist', label: '관심종목' }, { to: '/alerts', label: '알림' }] },
    { title: '시장 보기', items: [
      { to: '/', label: '시장요약', tabs: [{ to: '/', label: '요약' }, { to: '/market/briefing', label: '아침 브리핑' }] },
      { to: '/market/flow', label: '수급', tabs: [{ to: '/market/flow', label: '투자자 수급' }, { to: '/market/program', label: '프로그램·업종' }, { to: '/market/short', label: '공매도·장중 가집계' }] },
      { to: '/market/risk', label: '위험·심리 지표' },
      { to: '/market/movers', label: '종목 순위', tabs: [{ to: '/market/movers', label: '특징종목' }, { to: '/market/rs', label: '상대강도' },
        { to: '/market/groups/theme', label: '테마·업종', prefix: '/market/groups' }, { to: '/market/list', label: '전체 종목' }] },
      { to: '/market/indicators', label: '지수·환율·원자재' },
      { to: '/market/news', label: '뉴스·일정', tabs: [{ to: '/market/news', label: '시장 뉴스' }, { to: '/market/disclosures', label: '공시 속보' }, { to: '/market/earnings', label: '미국 실적 일정' }] }] },
    { title: '종목 찾기·검증', items: [{ to: '/discover/screener', label: '종목필터' }, { to: '/discover/signals', label: '매매신호' }, { to: '/discover/backtest', label: '백테스팅' },
      { to: '/discover/similar', label: '유사차트' }, { to: '/discover/ai', label: 'AI예측 (참고)' }] },
    { title: '모의투자', items: [{ to: '/trade/order', label: '모의 주문' }, { to: '/trade/status', label: '투자현황' }, { to: '/trade/journal', label: '매매일지' },
      { to: '/trade/live', label: '실계좌 (관리자)', admin: true }] },
    { title: '연습·커뮤니티', items: [{ to: '/trade/game', label: '차트게임' }, { to: '/trade/league', label: '투자리그' }, { to: '/community/timeline', label: '타임라인' },
      { to: '/community/insight', label: '인사이트' }, { to: '/community/predict', label: '종목예측' }] },
  ] },
  { key: 'vc', label: '스타트업 투자', groups: [
    { title: '투자 데이터', items: [{ to: '/vc', label: '투자 통계' }, { to: '/vc/deals', label: '투자/M&A' }, { to: '/vc/companies', label: '스타트업', prefix: '/vc/companies' },
      { to: '/vc/investors', label: '투자자', prefix: '/vc/investors' }, { to: '/vc/funds', label: '펀드' }] },
    { title: '소식·지원', items: [{ to: '/vc/news', label: '뉴스' }, { to: '/vc/grants', label: '지원사업' }] },
    { title: '내 작업', items: [{ to: '/vc/collections', label: '컬렉션', prefix: '/vc/collections' }, { to: '/vc/compare', label: '기업 비교' }, { to: '/vc/ir', label: 'IR' },
      { to: '/vc/discussions', label: '토론' }] },
  ] },
]
const area = ref(route.path.startsWith('/vc') ? 'vc' : 'stock')
watch(() => route.path, p => { if (p.startsWith('/vc')) area.value = 'vc'; else if (p !== '/settings' && !p.startsWith('/community/post')) area.value = 'stock' })
const menu = computed(() => AREAS.find(a => a.key === area.value).groups)
function switchArea(k) { area.value = k; router.push(k === 'vc' ? '/vc' : '/'); navOpen.value = false }
const favs = ref([])
const allItems = computed(() => AREAS.flatMap(a => a.groups).flatMap(g => g.items).filter(x => !x.admin || session.user?.is_admin))
const favItems = computed(() => favs.value.map(to => allItems.value.find(m => m.to === to) || allItems.value.flatMap(m => m.tabs || []).find(t => t.to === to)).filter(Boolean))
watch(() => session.user?.id, id => { favs.value = []; if (id) api.get('/user/menu', null, { quiet: true }).then(r => (favs.value = r)).catch(() => {}) }, { immediate: true })
function saveFavs() { api.put('/user/menu', favs.value, { quiet: true }).catch(() => {}) }
function toggleFav(to) { favs.value = favs.value.includes(to) ? favs.value.filter(x => x !== to) : [...favs.value, to]; saveFavs() }
function moveFav(i, d) { const a = favItems.value.map(m => m.to); [a[i], a[i + d]] = [a[i + d], a[i]]; favs.value = a; saveFavs() }
// 탭으로 묶인 메뉴는 안에 든 화면 어느 것이 열려 있어도 켜진 것으로 본다
function isActive(m) { return m.tabs ? m.tabs.some(isActive) : m.prefix ? route.path.startsWith(m.prefix) : route.path === m.to }
const current = computed(() => allItems.value.find(isActive))
const tabs = computed(() => current.value?.tabs)

// 덜 쓰는 묶음은 접어 둔다. 지금 보고 있는 화면이 든 묶음은 늘 펼친다.
const folded = stored('pref.menuFolded', { '연습·커뮤니티': true })
function isOpen(g) { return !folded.value[g.title] || g.items.some(isActive) }
function toggleGroup(g) { folded.value = { ...folded.value, [g.title]: isOpen(g) } }

// ☆로 고른 메뉴가 없으면 자주 연 화면 네 개를 대신 보여 준다
const visits = stored('pref.menuVisits', {})
watch(() => current.value?.to, to => { if (to) visits.value = { ...visits.value, [to]: (visits.value[to] || 0) + 1 } }, { immediate: true })
const frequent = computed(() => allItems.value.filter(m => (visits.value[m.to] || 0) >= 3).sort((a, b) => visits.value[b.to] - visits.value[a.to]).slice(0, 4))

async function loadNotif() { try { Object.assign(notif, await api.get('/notifications', null, { quiet: true })) } catch { /* 무시 */ } }
watch(() => session.user?.id, id => { if (id) loadNotif() }, { immediate: true })
useInterval(() => { if (session.user) loadNotif() }, 20000)
async function toggleBell() {
  bellOpen.value = !bellOpen.value
  if (bellOpen.value && notif.unread) { await api.post('/notifications/read'); notif.unread = 0 }
}
function openNotif(n) { bellOpen.value = false; if (n.link) router.push(n.link) }
function toggleTheme() {
  dark.value = !dark.value
  const t = dark.value ? 'dark' : 'light'
  document.documentElement.dataset.theme = t
  try { localStorage.setItem('theme', t) } catch { /* 무시 */ }
  window.dispatchEvent(new Event('themechange'))
}
</script>

<style scoped>
.shell { display: flex; min-height: 100vh; }
.nav { width: var(--nav-w); flex: none; background: var(--panel); border-right: 1px solid var(--line); position: sticky; top: 0; height: 100vh; overflow-y: auto; padding: 12px 10px 24px; }
.brand { display: flex; align-items: center; gap: 8px; font-weight: 800; font-size: 16px; padding: 4px 8px 12px; }
.group { margin-bottom: 8px; }
.gt { font-size: 11px; color: var(--faint); font-weight: 700; padding: 6px 8px 2px; }
button.gt.fold { display: flex; justify-content: space-between; align-items: center; width: 100%; border: 0; background: none; border-radius: 6px; cursor: pointer; }
button.gt.fold:hover { color: var(--text); background: none; }
.page-tabs { margin-bottom: 14px; } .page-tabs a { white-space: nowrap; }
.nav a:not(.brand) { display: block; flex: 1; min-width: 0; padding: 6px 10px; border-radius: 7px; color: var(--muted); font-weight: 500; }
.item { display: flex; align-items: center; gap: 2px; }
.item .star, .item .tools button { padding: 2px 5px; font-size: 12px; color: var(--faint); visibility: hidden; border: 0; }
.item:hover .star, .item:hover .tools button, .item .star.on { visibility: visible; }
.item .star.on { color: #f59e0b; }
.item .tools { display: none; }
.item:hover .tools { display: flex; }
.item a { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.group.mine { border-bottom: 1px solid var(--line); padding-bottom: 6px; }
.areas { display: flex; margin: 0 2px 10px; }
.areas button { flex: 1; padding: 6px 4px; font-size: 12.5px; font-weight: 700; }
.group.foot { border-top: 1px solid var(--line); margin-top: 8px; padding-top: 6px; }
@media (hover: none) { .item .star, .item .tools button { visibility: visible; padding: 7px 10px; font-size: 14px; } .item .tools { display: flex; } }
.nav a:not(.brand):hover { background: var(--panel-2); color: var(--text); }
.nav a.active { background: var(--accent-soft); color: var(--accent); font-weight: 700; }
.nav a.live { color: var(--up); }
.main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.top { position: sticky; top: 0; z-index: 20; display: flex; gap: 10px; align-items: center; justify-content: space-between; padding: 10px 20px; background: var(--bg); border-bottom: 1px solid var(--line); }
.search { flex: 1; max-width: 520px; }
.content { padding: 18px 20px 40px; max-width: 1480px; width: 100%; }
.burger { display: none; }
.bell-wrap { position: relative; }
.badge { background: var(--up); color: #fff; font-size: 10px; border-radius: 9px; padding: 0 5px; margin-left: 2px; }
.bell { position: absolute; right: 0; top: 40px; width: 340px; max-height: 420px; overflow-y: auto; z-index: 40; }
.nav-back { display: none; }
@media (max-width: 900px) {
  .nav { position: fixed; left: 0; z-index: 60; transform: translateX(-100%); transition: transform .2s; }
  .nav.open { transform: none; }
  .nav-back { display: block; position: fixed; inset: 0; background: rgba(0,0,0,.35); z-index: 55; }
  .burger { display: inline-block; }
  .content { padding: 14px 16px 40px; }
  .top { padding: 8px 16px; }
}
</style>
