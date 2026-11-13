import { createRouter, createWebHistory } from 'vue-router'
import { api, session, setUnauthorizedHandler } from './lib/api'

const v = (name) => () => import(`./views/${name}.vue`)
const routes = [
  { path: '/login', component: v('Login'), meta: { public: true, bare: true } },
  { path: '/', component: v('MarketSummary') },
  { path: '/market/movers', component: v('MarketMovers') },
  { path: '/market/indicators', component: v('MarketIndicators') },
  { path: '/market/news', component: v('MarketNews') },
  { path: '/market/briefing', component: v('Briefing') },
  { path: '/market/flow', component: v('Flow') },
  { path: '/market/program', component: v('FlowDetail'), props: { part: 'program' } },
  { path: '/market/short', component: v('FlowDetail'), props: { part: 'short' } },
  { path: '/market/flow-detail', redirect: '/market/program' },
  { path: '/market/risk', component: v('Risk') },
  { path: '/market/disclosures', component: v('Disclosures') },
  { path: '/market/earnings', component: v('Earnings') },
  { path: '/market/rs', component: v('RsRank') },
  { path: '/market/list', component: v('MarketList') },
  { path: '/market/groups/:kind', component: v('Groups') },
  { path: '/market/groups/:kind/:no', component: v('GroupDetail') },
  { path: '/stock/:symbol', component: v('Stock') },
  { path: '/discover/screener', component: v('Screener') },
  { path: '/discover/signals', component: v('Signals') },
  { path: '/discover/ai', component: v('AiPredict') },
  { path: '/discover/similar', component: v('SimilarSearch') },
  { path: '/discover/backtest', component: v('Backtest') },
  { path: '/trade/order', component: v('Order') },
  { path: '/trade/status', component: v('TradeStatus') },
  { path: '/trade/league', component: v('League') },
  { path: '/trade/journal', component: v('Journal') },
  { path: '/trade/mind', component: v('Simbeop'), props: { part: 'sayings' } },
  { path: '/trade/mind/moktak', component: v('Simbeop'), props: { part: 'moktak' } },
  { path: '/trade/mind/bell', component: v('Simbeop'), props: { part: 'bell' } },
  { path: '/trade/game', component: v('ChartGame') },
  { path: '/trade/live', component: v('LiveTrade') },
  { path: '/community/timeline', component: v('Posts'), props: { kind: 'timeline' } },
  { path: '/community/insight', component: v('Posts'), props: { kind: 'insight' } },
  { path: '/community/post/:id', component: v('PostDetail') },
  { path: '/community/predict', component: v('Predictions') },
  { path: '/watchlist', component: v('Watchlist') },
  { path: '/alerts', component: v('Alerts') },
  { path: '/vc', component: v('VcStats') },
  { path: '/vc/deals', component: v('VcDeals') },
  { path: '/vc/companies', component: v('VcCompanies') },
  { path: '/vc/companies/:id', component: v('VcCompany') },
  { path: '/vc/investors', component: v('VcInvestors') },
  { path: '/vc/investors/:id', component: v('VcInvestor') },
  { path: '/vc/funds', component: v('VcFunds') },
  { path: '/vc/news', component: v('VcNews') },
  { path: '/vc/grants', component: v('VcGrants') },
  { path: '/vc/ir', component: v('VcIr') },
  { path: '/vc/collections', component: v('VcCollections') },
  { path: '/vc/collections/:id', component: v('VcCollection') },
  { path: '/vc/compare', component: v('VcCompare') },
  { path: '/vc/discussions', component: v('Posts'), props: { kind: 'discussion' } },
  { path: '/settings', component: v('Settings') },
  { path: '/:rest(.*)', redirect: '/' },
]

export const router = createRouter({ history: createWebHistory(), routes, scrollBehavior: () => ({ top: 0 }) })

setUnauthorizedHandler(() => {
  session.user = null
  if (router.currentRoute.value.path !== '/login') router.push({ path: '/login', query: { next: router.currentRoute.value.fullPath } })
})

router.beforeEach(async (to) => {
  if (!session.ready) {
    try { const r = await api.get('/auth/me', null, { quiet: true }); session.user = r.user; session.firstRun = r.first_run } catch { /* 서버 미기동 */ }
    session.ready = true
  }
  if (!to.meta.public && !session.user) return { path: '/login', query: { next: to.fullPath } }
})
