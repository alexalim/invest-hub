// 선택한 모의계좌를 화면 사이에서 공유한다.
import { ref } from 'vue'
import { api } from './api'
export const accounts = ref([])
export const accountId = ref(null)
try { const v = localStorage.getItem('accountId'); if (v) accountId.value = +v } catch { /* 무시 */ }
export async function loadAccounts() {
  accounts.value = await api.get('/trade/accounts')
  if (!accounts.value.find(a => a.id === accountId.value)) accountId.value = accounts.value[0]?.id ?? null
  return accounts.value
}
export function selectAccount(id) { accountId.value = id; try { localStorage.setItem('accountId', id) } catch { /* 무시 */ } }
