<template>
  <div class="p-6 max-w-7xl mx-auto">
    <div class="mb-8">
      <div class="flex items-center gap-3 mb-1">
        <div class="w-8 h-8 rounded-lg bg-brand-500/15 border border-brand-500/30 flex items-center justify-center">
          <svg class="w-4 h-4 text-brand-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"/>
          </svg>
        </div>
        <h1 class="text-xl font-display font-bold text-zinc-100 tracking-tight">Admin Panel</h1>
      </div>
      <p class="text-zinc-500 text-sm ml-11">Manage users, assign search credits, monitor usage</p>
    </div>

    <!-- Stats row -->
    <div v-if="stats" class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8 animate-fadein">
      <div class="stat-card group">
        <span class="stat-label">Total Users</span>
        <span class="stat-value">{{ stats.totalUsers }}</span>
        <div class="stat-decoration" />
      </div>
      <div class="stat-card group">
        <span class="stat-label">Total Searches</span>
        <span class="stat-value">{{ stats.totalSearches }}</span>
        <div class="stat-decoration" />
      </div>
      <div class="stat-card group">
        <span class="stat-label">Today's Searches</span>
        <span class="stat-value text-brand-400">{{ stats.todaySearches }}</span>
        <div class="stat-decoration bg-brand-500/10" />
      </div>
      <div class="stat-card group">
        <span class="stat-label">By Role</span>
        <div class="flex flex-wrap gap-1 mt-1.5">
          <span v-for="rb in stats.roleBreakdown" :key="rb.role"
            :class="['badge', 'badge-' + rb.role.toLowerCase()]">
            {{ rb.role }}: {{ rb.count }}
          </span>
        </div>
        <div class="stat-decoration" />
      </div>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 mb-6 bg-zinc-900 border border-zinc-800 rounded-xl p-1 w-fit">
      <button v-for="tab in tabs" :key="tab"
        :class="['px-4 py-2 text-sm font-display font-medium rounded-lg transition-all',
          activeTab === tab
            ? 'bg-brand-500 text-white shadow-md shadow-brand-500/20'
            : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60']"
        @click="activeTab = tab">
        {{ tab }}
      </button>
    </div>

    <!-- ── Users tab ── -->
    <div v-if="activeTab === 'Users'" class="animate-fadein">

      <div class="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div class="relative">
          <svg class="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
            fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M21 21l-4.35-4.35M17 11A6 6 0 115 11a6 6 0 0112 0z"/>
          </svg>
          <input v-model="userSearch" type="text" placeholder="Search users…" class="input pl-9 max-w-xs" />
        </div>
        <div class="flex gap-2">
          <button @click="showCreateModal = true" class="btn-primary">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
            </svg>
            Add User
          </button>
          <button @click="loadAll" class="btn-secondary">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
            </svg>
            Refresh
          </button>
        </div>
      </div>

      <div v-if="loadingUsers" class="flex items-center justify-center py-20">
        <div class="spinner w-8 h-8" />
      </div>

      <div v-else-if="!filteredUsers.length"
        class="flex flex-col items-center justify-center py-20 text-zinc-500 gap-3 bg-zinc-900/40 border border-zinc-800 rounded-2xl">
        <div class="w-12 h-12 rounded-2xl bg-zinc-800 flex items-center justify-center">
          <svg class="w-6 h-6 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
              d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/>
          </svg>
        </div>
        <p class="font-display text-sm font-medium text-zinc-400">No users found</p>
        <p class="text-xs text-zinc-600">Try adjusting your search filter</p>
      </div>

      <div v-else class="rounded-2xl border border-zinc-800 overflow-hidden bg-zinc-900/50">
        <table class="w-full border-collapse">
          <thead>
            <tr class="border-b border-zinc-800 bg-zinc-900">
              <th class="text-left px-5 py-3.5 text-xs font-display font-semibold text-zinc-400 tracking-wide uppercase">User</th>
              <th class="text-left px-4 py-3.5 text-xs font-display font-semibold text-zinc-400 tracking-wide uppercase">Role</th>
              <th class="text-left px-4 py-3.5 text-xs font-display font-semibold text-zinc-400 tracking-wide uppercase">Usage</th>
              <th class="text-left px-4 py-3.5 text-xs font-display font-semibold text-zinc-400 tracking-wide uppercase">Remaining</th>
              <th class="text-left px-4 py-3.5 text-xs font-display font-semibold text-zinc-400 tracking-wide uppercase">Joined</th>
              <th class="text-right px-5 py-3.5 text-xs font-display font-semibold text-zinc-400 tracking-wide uppercase">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-zinc-800/70">
            <tr v-for="u in filteredUsers" :key="u.id"
              class="group hover:bg-zinc-800/30 transition-colors duration-150">

              <td class="px-5 py-4">
                <div class="flex items-center gap-3">
                  <div class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold font-display flex-shrink-0"
                    :class="avatarColor(u.role)">
                    {{ u.email[0].toUpperCase() }}
                  </div>
                  <span class="font-mono text-sm text-zinc-200 leading-none">{{ u.email }}</span>
                </div>
              </td>

              <td class="px-4 py-4">
                <span :class="['badge', 'badge-' + u.role.toLowerCase()]">{{ u.role }}</span>
              </td>

              <td class="px-4 py-4">
                <div v-if="u.role === 'Admin'"
                  class="flex items-center gap-1.5 text-xs text-purple-400 font-display font-medium">
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                  </svg>
                  Unlimited
                </div>
                <div v-else class="flex flex-col gap-1.5">
                  <div class="flex items-center justify-between">
                    <span class="font-mono text-xs text-zinc-500">{{ u.searchUsed }} / {{ u.searchLimit }}</span>
                    <span class="text-xs font-display font-medium" :class="pctTextColor(u)">{{ pct(u) }}%</span>
                  </div>
                  <div class="w-28 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                    <div class="h-full rounded-full transition-all duration-500"
                      :class="pctColor(u)"
                      :style="{ width: pct(u) + '%' }" />
                  </div>
                </div>
              </td>

              <td class="px-4 py-4">
                <span v-if="u.role === 'Admin'" class="text-purple-400 font-mono text-sm font-bold">∞</span>
                <div v-else class="flex items-center gap-1.5">
                  <div class="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    :class="u.remaining > 0 ? 'bg-emerald-400' : 'bg-red-400'" />
                  <span class="font-mono text-sm font-semibold"
                    :class="u.remaining > 0 ? 'text-emerald-400' : 'text-red-400'">
                    {{ u.remaining }}
                  </span>
                </div>
              </td>

              <td class="px-4 py-4">
                <span class="text-zinc-500 text-sm font-display">{{ fmtDate(u.createdAt) }}</span>
              </td>

              <td class="px-5 py-4">
                <div class="flex gap-2 items-center justify-end flex-nowrap">
                  <select
                    :value="u.role"
                    class="bg-zinc-800 border border-zinc-700 text-zinc-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500/30 transition-all cursor-pointer"
                    @change="e => updateRole(u, e.target.value)">
                    <option v-for="r in roles" :key="r" :value="r">{{ r }}</option>
                  </select>
                  <template v-if="u.role !== 'Admin'">
                    <input
                      v-model.number="u._topup"
                      type="number" min="1" max="100000"
                      placeholder="Credits"
                      class="w-20 bg-zinc-800 border border-zinc-700 text-zinc-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/20 transition-all placeholder-zinc-600"
                      @keydown.enter="topUp(u)" />
                    <button
                      @click="topUp(u)"
                      class="text-xs bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 hover:border-emerald-500/40 px-2.5 py-1.5 rounded-lg transition-all font-display font-medium whitespace-nowrap"
                      title="Add search credits">
                      + Add
                    </button>
                    <button
                      @click="confirmDeleteUser = u"
                      class="p-1.5 rounded-lg text-zinc-600 hover:text-red-400 hover:bg-red-500/10 border border-transparent hover:border-red-500/20 transition-all flex-shrink-0"
                      title="Delete user">
                      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                      </svg>
                    </button>
                  </template>
                  <span v-else class="text-xs text-zinc-700 italic font-display px-1">protected</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <div class="px-5 py-3 border-t border-zinc-800 bg-zinc-900/60 flex items-center justify-between">
          <span class="text-xs text-zinc-500 font-display">
            Showing <span class="text-zinc-300 font-medium">{{ filteredUsers.length }}</span>
            user{{ filteredUsers.length !== 1 ? 's' : '' }}
          </span>
          <span v-if="userSearch" class="text-xs text-zinc-600 font-display">
            Filtered by "{{ userSearch }}"
          </span>
        </div>
      </div>
    </div>

    <!-- ── Recent Searches tab ── -->
    <div v-if="activeTab === 'Recent Searches'" class="animate-fadein">

      <div class="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div class="relative">
          <svg class="w-4 h-4 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
            fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M21 21l-4.35-4.35M17 11A6 6 0 115 11a6 6 0 0112 0z"/>
          </svg>
          <input v-model="searchFilter" type="text" placeholder="Filter by user or keyword…"
            class="input pl-9 max-w-xs" />
        </div>
        <button @click="loadAll" class="btn-secondary">
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
          </svg>
          Refresh
        </button>
      </div>

      <div v-if="loadingUsers" class="flex items-center justify-center py-20">
        <div class="spinner w-8 h-8" />
      </div>

      <div v-else-if="!filteredSearches.length"
        class="flex flex-col items-center justify-center py-20 text-zinc-500 gap-3 bg-zinc-900/40 border border-zinc-800 rounded-2xl">
        <div class="w-12 h-12 rounded-2xl bg-zinc-800 flex items-center justify-center">
          <svg class="w-6 h-6 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
              d="M21 21l-4.35-4.35M17 11A6 6 0 115 11a6 6 0 0112 0z"/>
          </svg>
        </div>
        <p class="font-display text-sm font-medium text-zinc-400">No recent searches found</p>
      </div>

      <!-- Grouped by user -->
      <div v-else class="space-y-4">
        <div v-for="group in groupedSearches" :key="group.email"
          class="rounded-2xl border border-zinc-800 overflow-hidden bg-zinc-900/50">

          <div class="flex items-center gap-3 px-5 py-3.5 bg-zinc-900 border-b border-zinc-800">
            <div class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold font-display flex-shrink-0"
              :class="avatarColor(group.role)">
              {{ group.email[0].toUpperCase() }}
            </div>
            <span class="font-mono text-sm text-zinc-200 font-medium">{{ group.email }}</span>
            <span :class="['badge', 'badge-' + group.role.toLowerCase()]">{{ group.role }}</span>
            <span class="ml-auto text-xs text-zinc-500 font-display">
              {{ group.searches.length }} search{{ group.searches.length !== 1 ? 'es' : '' }}
            </span>
          </div>

          <table class="w-full border-collapse">
            <thead>
              <tr class="border-b border-zinc-800/60 bg-zinc-900/40">
                <th class="text-left px-5 py-2.5 text-xs font-display font-semibold text-zinc-500 tracking-wide uppercase w-10">#</th>
                <th class="text-left px-4 py-2.5 text-xs font-display font-semibold text-zinc-500 tracking-wide uppercase">Keyword</th>
                <th class="text-left px-4 py-2.5 text-xs font-display font-semibold text-zinc-500 tracking-wide uppercase">Results</th>
                <th class="text-left px-4 py-2.5 text-xs font-display font-semibold text-zinc-500 tracking-wide uppercase">Top Profit</th>
                <th class="text-left px-4 py-2.5 text-xs font-display font-semibold text-zinc-500 tracking-wide uppercase">Date</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-zinc-800/50">
              <tr v-for="(s, i) in group.searches" :key="s.id"
                class="hover:bg-zinc-800/20 transition-colors duration-100">
                <td class="px-5 py-3 text-xs text-zinc-600 font-mono">{{ i + 1 }}</td>
                <td class="px-4 py-3">
                  <div class="flex items-center gap-2">
                    <svg class="w-3.5 h-3.5 text-zinc-600 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                        d="M21 21l-4.35-4.35M17 11A6 6 0 115 11a6 6 0 0112 0z"/>
                    </svg>
                    <span class="text-sm text-zinc-200 font-medium">{{ s.keyword }}</span>
                  </div>
                </td>
                <td class="px-4 py-3">
                  <span class="inline-flex items-center gap-1 bg-zinc-800/80 border border-zinc-700/60 text-zinc-400 text-xs font-mono font-medium rounded-lg px-2.5 py-1">
                    {{ s.resultCount ?? '—' }}
                    <span class="text-zinc-600 font-display">results</span>
                  </span>
                </td>
                <!-- ✅ New: top profit column in admin view -->
                <td class="px-4 py-3">
                  <span v-if="s.parsedResults?.length"
                    class="text-emerald-400 text-xs font-mono font-medium">
                    {{ adminBestProfit(s.parsedResults) }}
                  </span>
                  <span v-else class="text-zinc-700 text-xs">—</span>
                </td>
                <td class="px-4 py-3 text-zinc-500 text-xs font-display">{{ fmtDate(s.createdAt) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="text-xs text-zinc-600 font-display px-1">
          {{ filteredSearches.length }} search{{ filteredSearches.length !== 1 ? 'es' : '' }}
          across {{ groupedSearches.length }} user{{ groupedSearches.length !== 1 ? 's' : '' }}
        </div>
      </div>
    </div>

    <!-- ── Create User Modal ── -->
    <transition name="modal">
      <div v-if="showCreateModal"
        class="fixed inset-0 z-50 flex items-center justify-center px-4"
        style="background:rgba(0,0,0,0.8);backdrop-filter:blur(4px)"
        @click.self="closeCreate">
        <div class="card p-6 w-full max-w-md animate-fadein border border-zinc-700/80">
          <div class="flex items-center justify-between mb-6">
            <div>
              <h2 class="font-display font-bold text-zinc-100 text-lg">Create User</h2>
              <p class="text-zinc-500 text-xs mt-0.5">Add a new user to the platform</p>
            </div>
            <button @click="closeCreate"
              class="w-8 h-8 flex items-center justify-center rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition-all">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>

          <div class="space-y-4">
            <div>
              <label class="block text-xs font-display font-semibold text-zinc-400 mb-1.5 tracking-wide uppercase">Email</label>
              <input v-model="cf.email" type="email" class="input" placeholder="user@example.com" />
            </div>
            <div>
              <label class="block text-xs font-display font-semibold text-zinc-400 mb-1.5 tracking-wide uppercase">Password</label>
              <input v-model="cf.password" type="password" class="input" placeholder="Min. 6 characters" />
            </div>
            <div>
              <label class="block text-xs font-display font-semibold text-zinc-400 mb-1.5 tracking-wide uppercase">Role</label>
              <select v-model="cf.role" class="input">
                <option v-for="r in roles" :key="r" :value="r">
                  {{ r }} — {{ r === 'Admin' ? 'Unlimited' : planLabels[r] + ' searches' }}
                </option>
              </select>
            </div>
            <div class="bg-zinc-800/60 border border-zinc-700/80 rounded-xl px-4 py-3 flex justify-between items-center">
              <div>
                <p class="text-xs font-display text-zinc-400">Starting credits</p>
                <p class="text-xs text-zinc-600 mt-0.5">Based on selected role</p>
              </div>
              <span class="text-zinc-100 font-mono font-bold text-lg">
                {{ cf.role === 'Admin' ? '∞' : planLimits[cf.role] }}
              </span>
            </div>
            <div v-if="createError"
              class="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-xl px-4 py-3">
              <svg class="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
              {{ createError }}
            </div>
          </div>

          <div class="flex gap-3 mt-6">
            <button @click="closeCreate" class="btn-secondary flex-1 justify-center">Cancel</button>
            <button @click="createUser" :disabled="creating" class="btn-primary flex-1 justify-center">
              <div v-if="creating" class="spinner w-4 h-4" />
              {{ creating ? 'Creating…' : 'Create User' }}
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- ── Delete Confirm Modal ── -->
    <transition name="modal">
      <div v-if="confirmDeleteUser"
        class="fixed inset-0 z-50 flex items-center justify-center px-4"
        style="background:rgba(0,0,0,0.8);backdrop-filter:blur(4px)"
        @click.self="confirmDeleteUser = null">
        <div class="card p-6 max-w-sm w-full border border-zinc-700/80">
          <div class="w-10 h-10 rounded-xl bg-red-500/15 border border-red-500/20 flex items-center justify-center mb-4">
            <svg class="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
            </svg>
          </div>
          <h3 class="font-display font-bold text-zinc-100 mb-1">Delete user?</h3>
          <p class="text-sm text-zinc-400 mb-6 leading-relaxed">
            This will permanently delete
            <span class="text-zinc-200 font-medium font-mono bg-zinc-800 px-1.5 py-0.5 rounded text-xs">
              {{ confirmDeleteUser.email }}
            </span>
            and all their search history. This action cannot be undone.
          </p>
          <div class="flex gap-3">
            <button @click="confirmDeleteUser = null" class="btn-secondary flex-1 justify-center">Cancel</button>
            <button @click="doDelete"
              class="flex-1 justify-center inline-flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-display font-semibold bg-red-500 hover:bg-red-600 text-white transition-all">
              Delete User
            </button>
          </div>
        </div>
      </div>
    </transition>

    <!-- Toast -->
    <transition name="toast">
      <div v-if="toast"
        class="fixed bottom-6 right-6 text-sm font-display px-4 py-3 rounded-xl shadow-2xl flex items-center gap-2.5 z-40 border"
        :class="toastErr
          ? 'bg-zinc-900 border-red-500/30 text-red-300 shadow-red-500/10'
          : 'bg-zinc-900 border-emerald-500/30 text-zinc-100 shadow-emerald-500/10'">
        <div class="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0"
          :class="toastErr ? 'bg-red-500/20' : 'bg-emerald-500/20'">
          <svg class="w-3 h-3" :class="toastErr ? 'text-red-400' : 'text-emerald-400'"
            fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path v-if="!toastErr" stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
            <path v-else stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </div>
        {{ toast }}
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'

const tabs       = ['Users', 'Recent Searches']
const activeTab  = ref('Users')
const roles      = ['Admin', 'Pro', 'Basic', 'Free']
const planLimits = { Admin: '∞', Pro: 200, Basic: 50, Free: 5 }
const planLabels = { Admin: '∞', Pro: '200', Basic: '50', Free: '5' }

const users        = ref([])
const stats        = ref(null)
const loadingUsers = ref(true)
const userSearch   = ref('')
const searchFilter = ref('')
const toast        = ref('')
const toastErr     = ref(false)
const confirmDeleteUser = ref(null)

const showCreateModal = ref(false)
const creating        = ref(false)
const createError     = ref('')
const cf              = ref({ email: '', password: '', role: 'Free' })

// ── Currency helper ────────────────────────────────────────────────────────
function currencySymbol(currency) {
  const map = { GBP: '£', EUR: '€', AUD: 'A$', USD: '$' }
  return map[currency] ?? (currency ? currency + ' ' : '$')
}

// ── Best profit across a result set (for admin summary column) ─────────────
function adminBestProfit(products) {
  if (!products?.length) return '—'
  const best = products.reduce((a, b) => (b.profit ?? 0) > (a.profit ?? 0) ? b : a)
  const sym  = currencySymbol(best.currency)
  return (best.profit >= 0 ? '+' : '') + sym + (best.profit ?? 0).toFixed(2)
}

const filteredUsers = computed(() => {
  const list = userSearch.value
    ? users.value.filter(u => u.email.toLowerCase().includes(userSearch.value.toLowerCase()))
    : users.value
  return [...list].sort((a, b) => (a.role === 'Admin' ? -1 : b.role === 'Admin' ? 1 : 0))
})

const filteredSearches = computed(() => {
  const list = stats.value?.recentSearches ?? []
  if (!searchFilter.value) return list
  const q = searchFilter.value.toLowerCase()
  return list.filter(s => {
    const email = (s.userEmail ?? s.user?.email ?? '').toLowerCase()
    const kw    = (s.keyword ?? '').toLowerCase()
    return email.includes(q) || kw.includes(q)
  })
})

const groupedSearches = computed(() => {
  const map = new Map()
  for (const s of filteredSearches.value) {
    const email = s.userEmail ?? s.user?.email ?? '—'
    const role  = s.userRole  ?? s.user?.role  ?? 'Free'
    // Parse results JSON if present for the top-profit column
    const parsedResults = (() => {
      try { return JSON.parse(s.results ?? '[]') } catch { return [] }
    })()
    if (!map.has(email)) map.set(email, { email, role, searches: [] })
    map.get(email).searches.push({ ...s, parsedResults })
  }
  return [...map.values()]
})

function avatarColor(role) {
  const map = {
    Admin: 'bg-purple-500/20 text-purple-300',
    Pro:   'bg-brand-500/20 text-brand-300',
    Basic: 'bg-blue-500/20 text-blue-300',
    Free:  'bg-zinc-700 text-zinc-400',
  }
  return map[role] ?? 'bg-zinc-700 text-zinc-400'
}

function pct(u) {
  if (!u.searchLimit || u.searchLimit <= 0) return 0
  return Math.min(100, Math.round((u.searchUsed / u.searchLimit) * 100))
}
function pctColor(u) {
  const p = pct(u)
  if (p >= 90) return 'bg-red-500'
  if (p >= 70) return 'bg-amber-400'
  return 'bg-brand-500'
}
function pctTextColor(u) {
  const p = pct(u)
  if (p >= 90) return 'text-red-400'
  if (p >= 70) return 'text-amber-400'
  return 'text-zinc-500'
}
function fmtDate(d) {
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function showToast(msg, isErr = false) {
  toast.value    = msg
  toastErr.value = isErr
  setTimeout(() => toast.value = '', 3500)
}

async function loadAll() {
  loadingUsers.value = true
  try {
    const [uRes, sRes] = await Promise.all([
      api.get('/admin/users'),
      api.get('/admin/stats'),
    ])
    const rawUsers = Array.isArray(uRes.data) ? uRes.data : (uRes.data.users ?? [])
    users.value = rawUsers.map(u => ({ ...u, _topup: '' }))
    stats.value = sRes.data
  } catch (e) {
    console.error('Admin loadAll error:', e)
    users.value = []
  } finally {
    loadingUsers.value = false
  }
}

function closeCreate() {
  showCreateModal.value = false
  createError.value     = ''
  cf.value              = { email: '', password: '', role: 'Free' }
}

async function createUser() {
  createError.value = ''
  if (!cf.value.email || !cf.value.password) {
    createError.value = 'Email and password are required.'
    return
  }
  creating.value = true
  try {
    const res = await api.post('/admin/users', cf.value)
    users.value.unshift({ ...res.data.user, _topup: '' })
    closeCreate()
    showToast(`${res.data.user.email} created`)
    loadAll()
  } catch (e) {
    createError.value = e.response?.data?.error ?? 'Failed to create user.'
  } finally {
    creating.value = false
  }
}

async function updateRole(u, newRole) {
  try {
    const res     = await api.put(`/admin/users/${u.id}/role`, { role: newRole })
    u.role        = newRole
    u.searchLimit = res.data.searchLimit ?? (newRole === 'Admin' ? -1 : 5)
    u.searchUsed  = 0
    u.remaining   = res.data.remaining  ?? (newRole === 'Admin' ? -1 : u.searchLimit)
    showToast(`Role updated → ${newRole}`)
    loadAll()
  } catch (e) {
    showToast(e.response?.data?.error ?? 'Failed to update role', true)
    loadAll()
  }
}

async function topUp(u) {
  const amount = Number(u._topup)
  if (!amount || amount < 1) return
  try {
    const res     = await api.post(`/admin/users/${u.id}/topup`, { amount })
    u.searchLimit = res.data.searchLimit
    u.remaining   = res.data.remaining
    u._topup      = ''
    showToast(`Added ${amount} credits to ${u.email}`)
  } catch (e) {
    showToast(e.response?.data?.error ?? 'Top-up failed', true)
  }
}

function doDelete() {
  const u = confirmDeleteUser.value
  confirmDeleteUser.value = null
  api.delete(`/admin/users/${u.id}`)
    .then(() => {
      users.value = users.value.filter(x => x.id !== u.id)
      showToast('User deleted')
      loadAll()
    })
    .catch(e => showToast(e.response?.data?.error ?? 'Delete failed', true))
}

onMounted(loadAll)
</script>

<style scoped>
.stat-decoration {
  @apply absolute bottom-0 right-0 w-16 h-16 rounded-tl-3xl bg-zinc-800/30 -z-0;
}
.stat-card { @apply relative overflow-hidden; }

.toast-enter-active, .toast-leave-active { transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1); }
.toast-enter-from,  .toast-leave-to      { opacity: 0; transform: translateY(10px) scale(0.97); }
.modal-enter-active, .modal-leave-active { transition: opacity 0.2s ease; }
.modal-enter-from,  .modal-leave-to      { opacity: 0; }
</style>