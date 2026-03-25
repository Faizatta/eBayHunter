<template>
  <div class="p-6 max-w-7xl mx-auto">
    <div class="mb-7">
      <h1 class="text-2xl font-display font-bold text-zinc-100">Admin Panel</h1>
      <p class="text-zinc-500 text-sm mt-1">Manage users, roles, and monitor bot usage</p>
    </div>

    <!-- Stats row -->
    <div v-if="stats" class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-7 animate-fadein">
      <div class="stat-card">
        <span class="stat-label">Total Users</span>
        <span class="stat-value">{{ stats.totalUsers }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">Total Searches</span>
        <span class="stat-value">{{ stats.totalSearches }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">Today's Searches</span>
        <span class="stat-value text-brand-400">{{ stats.todaySearches }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">Role Breakdown</span>
        <div class="flex flex-wrap gap-1 mt-1">
          <span v-for="rb in stats.roleBreakdown" :key="rb.role"
            :class="['badge', 'badge-' + rb.role.toLowerCase()]">
            {{ rb.role }}: {{ rb.count }}
          </span>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 mb-5 bg-zinc-900 border border-zinc-800 rounded-xl p-1 w-fit">
      <button v-for="tab in tabs" :key="tab"
        :class="['px-4 py-2 text-sm font-display font-medium rounded-lg transition-all', activeTab === tab
          ? 'bg-brand-500 text-white'
          : 'text-zinc-400 hover:text-zinc-200']"
        @click="activeTab = tab">
        {{ tab }}
      </button>
    </div>

    <!-- Users tab -->
    <div v-if="activeTab === 'Users'" class="animate-fadein">
      <div class="flex items-center justify-between mb-4">
        <input v-model="userSearch" type="text" placeholder="Filter by email…" class="input max-w-xs" />
        <button @click="loadUsers" class="btn-secondary">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
          </svg>
          Refresh
        </button>
      </div>

      <div v-if="loadingUsers" class="flex items-center justify-center py-16">
        <div class="spinner w-8 h-8" />
      </div>

      <div v-else class="table-container">
        <table class="table-base">
          <thead>
            <tr>
              <th>Email</th>
              <th>Role</th>
              <th>Used / Limit</th>
              <th>Remaining</th>
              <th>Joined</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in filteredUsers" :key="u.id">
              <td class="font-mono text-sm text-zinc-300">{{ u.email }}</td>
              <td>
                <span :class="['badge', 'badge-' + u.role.toLowerCase()]">{{ u.role }}</span>
              </td>
              <td>
                <div class="flex items-center gap-2">
                  <div class="w-24 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                    <div class="h-full bg-brand-500 rounded-full"
                      :style="{ width: Math.min(100, (u.searchUsed / u.searchLimit) * 100) + '%' }" />
                  </div>
                  <span class="font-mono text-xs text-zinc-400">{{ u.searchUsed }}/{{ u.searchLimit }}</span>
                </div>
              </td>
              <td>
                <span class="font-mono text-sm" :class="u.remaining > 0 ? 'text-emerald-400' : 'text-red-400'">
                  {{ u.remaining }}
                </span>
              </td>
              <td class="text-zinc-500 text-sm">{{ formatDate(u.createdAt) }}</td>
              <td>
                <div class="flex gap-2 items-center flex-wrap">
                  <!-- Role selector -->
                  <select
                    :value="u.role"
                    class="bg-zinc-800 border border-zinc-700 text-zinc-300 text-xs rounded-lg px-2 py-1.5 focus:outline-none focus:border-brand-500"
                    @change="e => updateRole(u.id, e.target.value)">
                    <option v-for="r in roles" :key="r" :value="r">{{ r }}</option>
                  </select>

                  <!-- Reset button -->
                  <button
                    @click="resetLimit(u.id)"
                    :disabled="resetting === u.id"
                    class="text-xs bg-zinc-800 hover:bg-emerald-500/20 hover:text-emerald-400 border border-zinc-700 hover:border-emerald-500/30 text-zinc-400 px-2.5 py-1.5 rounded-lg transition-all font-display disabled:opacity-50">
                    <span v-if="resetting === u.id">…</span>
                    <span v-else>Reset</span>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Recent Searches tab -->
    <div v-if="activeTab === 'Recent Searches'" class="animate-fadein">
      <div class="table-container">
        <table class="table-base">
          <thead>
            <tr>
              <th>User</th>
              <th>Keyword</th>
              <th>Results</th>
              <th>Date</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in stats?.recentSearches ?? []" :key="s.id">
              <td class="font-mono text-sm text-zinc-400">{{ s.userEmail }}</td>
              <td class="font-medium text-zinc-200">"{{ s.keyword }}"</td>
              <td>
                <span class="badge bg-zinc-800 text-zinc-400 border border-zinc-700">{{ s.resultCount }}</span>
              </td>
              <td class="text-zinc-500 text-sm">{{ formatDate(s.createdAt) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Toast -->
    <transition name="toast">
      <div v-if="toast" class="fixed bottom-6 right-6 bg-zinc-800 border border-zinc-700 text-zinc-100 text-sm font-display px-4 py-3 rounded-xl shadow-xl flex items-center gap-2">
        <svg class="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
        </svg>
        {{ toast }}
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'

const tabs      = ['Users', 'Recent Searches']
const activeTab = ref('Users')
const roles     = ['Free', 'Basic', 'Pro', 'Admin']

const users       = ref([])
const stats       = ref(null)
const loadingUsers = ref(true)
const userSearch  = ref('')
const resetting   = ref(null)
const toast       = ref('')

const filteredUsers = computed(() => {
  if (!userSearch.value) return users.value
  const q = userSearch.value.toLowerCase()
  return users.value.filter(u => u.email.toLowerCase().includes(q))
})

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function showToast(msg) {
  toast.value = msg
  setTimeout(() => toast.value = '', 3000)
}

async function loadUsers() {
  loadingUsers.value = true
  try {
    const res = await api.get('/admin/users')
    users.value = res.data
  } catch { users.value = [] }
  finally { loadingUsers.value = false }
}

async function loadStats() {
  try {
    const res = await api.get('/admin/stats')
    stats.value = res.data
  } catch { stats.value = null }
}

async function updateRole(userId, newRole) {
  try {
    await api.put(`/admin/users/${userId}/role`, { role: newRole })
    const user = users.value.find(u => u.id === userId)
    if (user) {
      user.role = newRole
      const limits = { Free: 5, Basic: 20, Pro: 100, Admin: 999999 }
      user.searchLimit = limits[newRole] ?? 5
      user.remaining = Math.max(0, user.searchLimit - user.searchUsed)
    }
    showToast(`Role updated to ${newRole}`)
    loadStats()
  } catch (e) {
    showToast('Failed to update role')
  }
}

async function resetLimit(userId) {
  resetting.value = userId
  try {
    await api.post(`/admin/users/${userId}/reset`)
    const user = users.value.find(u => u.id === userId)
    if (user) {
      user.searchUsed = 0
      user.remaining  = user.searchLimit
    }
    showToast('Search limit reset')
    loadStats()
  } catch {
    showToast('Failed to reset limit')
  } finally {
    resetting.value = null
  }
}

onMounted(() => {
  loadUsers()
  loadStats()
})
</script>

<style scoped>
.toast-enter-active, .toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(8px); }
</style>
