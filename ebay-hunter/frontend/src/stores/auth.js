import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

export const useAuthStore = defineStore('auth', () => {
  // ── State ──────────────────────────────────────────────────────────────────
  const token  = ref(localStorage.getItem('token') || null)
  const user   = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  // ── Getters ────────────────────────────────────────────────────────────────
  const isLoggedIn  = computed(() => !!token.value)
  const isAdmin     = computed(() => user.value?.role === 'Admin')
  const remaining   = computed(() => Math.max(0, (user.value?.searchLimit ?? 0) - (user.value?.searchUsed ?? 0)))
  const roleBadge   = computed(() => (user.value?.role ?? 'Free').toLowerCase())

  // ── Actions ────────────────────────────────────────────────────────────────
  function persist(data) {
    token.value = data.token
    user.value  = {
      email:       data.email,
      role:        data.role,
      searchLimit: data.searchLimit,
      searchUsed:  data.searchUsed,
      remaining:   data.remaining,
    }
    localStorage.setItem('token', data.token)
    localStorage.setItem('user', JSON.stringify(user.value))
  }

  async function register(email, password) {
    const res = await api.post('/auth/register', { email, password })
    persist(res.data.data)
    return res.data
  }

  async function login(email, password) {
    const res = await api.post('/auth/login', { email, password })
    persist(res.data.data)
    return res.data
  }

  async function refreshLimits() {
    try {
      const res = await api.get('/user/limits')
      const d   = res.data
      if (user.value) {
        user.value.searchLimit = d.searchLimit
        user.value.searchUsed  = d.searchUsed
        user.value.remaining   = d.remaining
        user.value.role        = d.role
        localStorage.setItem('user', JSON.stringify(user.value))
      }
    } catch { /* ignore */ }
  }

  function decrementSearch() {
    if (user.value) {
      user.value.searchUsed = (user.value.searchUsed ?? 0) + 1
      localStorage.setItem('user', JSON.stringify(user.value))
    }
  }

  function logout() {
    token.value = null
    user.value  = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return {
    token, user,
    isLoggedIn, isAdmin, remaining, roleBadge,
    register, login, logout, refreshLimits, decrementSearch,
  }
})
