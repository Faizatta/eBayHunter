<template>
  <div class="min-h-screen">
    <template v-if="auth.isLoggedIn">
      <div class="flex h-screen overflow-hidden">

        <!-- Sidebar -->
        <aside class="w-60 flex-shrink-0 bg-zinc-900 border-r border-zinc-800 flex flex-col">

          <!-- Logo -->
          <div class="px-5 py-5 border-b border-zinc-800">
            <div class="flex items-center gap-2.5">
              <div class="w-8 h-8 bg-brand-500 rounded-lg flex items-center justify-center">
                <svg class="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                </svg>
              </div>
              <span class="font-display font-bold text-zinc-100 text-lg tracking-tight">eBayHunter</span>
            </div>
          </div>

          <!-- Nav links -->
          <nav class="flex-1 px-3 py-4 flex flex-col gap-1 overflow-y-auto">
            <router-link to="/dashboard" custom v-slot="{ navigate, isActive }">
              <div :class="['nav-item', isActive && 'active']" @click="navigate">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                </svg>
                Product Search
              </div>
            </router-link>

            <router-link to="/history" custom v-slot="{ navigate, isActive }">
              <div :class="['nav-item', isActive && 'active']" @click="navigate">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
                  <path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>
                </svg>
                Search History
              </div>
            </router-link>

            <template v-if="auth.isAdmin">
              <div class="px-4 pt-4 pb-1">
                <span class="text-xs font-display uppercase tracking-widest text-zinc-600">Admin</span>
              </div>
              <router-link to="/admin" custom v-slot="{ navigate, isActive }">
                <div :class="['nav-item', isActive && 'active']" @click="navigate">
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                  </svg>
                  Admin Panel
                </div>
              </router-link>
            </template>
          </nav>

          <!-- Bottom: usage + user card + logout -->
          <div class="px-3 py-4 border-t border-zinc-800 space-y-3">

            <!-- Search usage bar (hidden for Admin — unlimited) -->
            <div v-if="!auth.isAdmin" class="px-2">
              <div class="flex justify-between text-xs font-display text-zinc-500 mb-1.5">
                <span>Searches</span>
                <span class="text-zinc-300">{{ auth.user?.searchUsed ?? 0 }} / {{ auth.user?.searchLimit ?? 0 }}</span>
              </div>
              <div class="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                <div class="h-full rounded-full transition-all duration-500"
                  :class="usagePercent >= 90 ? 'bg-red-500' : usagePercent >= 70 ? 'bg-amber-500' : 'bg-brand-500'"
                  :style="{ width: usagePercent + '%' }" />
              </div>
              <p v-if="auth.remaining === 0" class="text-xs text-red-400 mt-1.5 font-display">
                No searches left — contact admin
              </p>
            </div>

            <!-- Admin unlimited badge -->
            <div v-else class="px-2">
              <div class="flex items-center gap-2 text-xs text-purple-400 font-display">
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                </svg>
                Unlimited searches
              </div>
            </div>

            <!-- User card -->
            <div class="flex items-center gap-3 px-2 py-2 rounded-xl bg-zinc-800/50">
              <div class="w-7 h-7 rounded-full bg-brand-500/20 border border-brand-500/30 flex items-center justify-center flex-shrink-0">
                <span class="text-brand-400 text-xs font-display font-bold uppercase">
                  {{ auth.user?.email?.[0] ?? '?' }}
                </span>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-xs font-display text-zinc-200 truncate">{{ auth.user?.email }}</p>
                <span :class="['badge', 'badge-' + auth.roleBadge]">{{ auth.user?.role }}</span>
              </div>
            </div>

            <!-- Logout button — full width, clearly visible -->
            <button
              @click="doLogout"
              class="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl
                     bg-zinc-800 hover:bg-red-500/15 border border-zinc-700 hover:border-red-500/40
                     text-zinc-400 hover:text-red-400 font-display font-medium text-sm
                     transition-all duration-200 group">
              <svg class="w-4 h-4 transition-transform group-hover:translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
              </svg>
              Sign Out
            </button>

          </div>
        </aside>

        <!-- Main content -->
        <main class="flex-1 overflow-y-auto">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </main>
      </div>
    </template>

    <!-- Guest pages (login / register) -->
    <template v-else>
      <router-view />
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'

const auth   = useAuthStore()
const router = useRouter()

const usagePercent = computed(() => {
  const limit = auth.user?.searchLimit ?? 1
  const used  = auth.user?.searchUsed  ?? 0
  if (limit <= 0) return 0
  return Math.min(100, Math.round((used / limit) * 100))
})

function doLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from,  .fade-leave-to      { opacity: 0; }
</style>
