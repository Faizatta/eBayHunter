<template>
  <div class="min-h-screen">
    <!-- Authenticated layout with sidebar -->
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

          <!-- Nav -->
          <nav class="flex-1 px-3 py-4 flex flex-col gap-1 overflow-y-auto">
            <router-link to="/dashboard" custom v-slot="{ navigate, isActive }">
              <div :class="['nav-item', isActive && 'active']" @click="navigate">
                <IconSearch class="w-4 h-4" />
                Product Search
              </div>
            </router-link>

            <router-link to="/history" custom v-slot="{ navigate, isActive }">
              <div :class="['nav-item', isActive && 'active']" @click="navigate">
                <IconHistory class="w-4 h-4" />
                Search History
              </div>
            </router-link>

            <template v-if="auth.isAdmin">
              <div class="px-4 pt-4 pb-1">
                <span class="text-xs font-display uppercase tracking-widest text-zinc-600">Admin</span>
              </div>
              <router-link to="/admin" custom v-slot="{ navigate, isActive }">
                <div :class="['nav-item', isActive && 'active']" @click="navigate">
                  <IconAdmin class="w-4 h-4" />
                  Admin Panel
                </div>
              </router-link>
            </template>
          </nav>

          <!-- User info + logout -->
          <div class="px-3 py-4 border-t border-zinc-800">
            <!-- Usage bar -->
            <div class="mb-3 px-2">
              <div class="flex justify-between text-xs font-display text-zinc-500 mb-1.5">
                <span>Daily searches</span>
                <span class="text-zinc-300">{{ auth.user?.searchUsed ?? 0 }} / {{ auth.user?.searchLimit ?? 0 }}</span>
              </div>
              <div class="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  class="h-full bg-brand-500 rounded-full transition-all duration-500"
                  :style="{ width: usagePercent + '%' }"
                />
              </div>
            </div>

            <div class="flex items-center gap-3 px-2 py-2 rounded-xl bg-zinc-800/50">
              <div class="w-7 h-7 rounded-full bg-brand-500/20 border border-brand-500/30 flex items-center justify-center">
                <span class="text-brand-400 text-xs font-display font-bold uppercase">
                  {{ auth.user?.email?.[0] ?? '?' }}
                </span>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-xs font-display text-zinc-200 truncate">{{ auth.user?.email }}</p>
                <span :class="['badge', 'badge-' + auth.roleBadge]">{{ auth.user?.role }}</span>
              </div>
              <button @click="auth.logout(); $router.push('/login')" class="text-zinc-500 hover:text-zinc-300 transition-colors p-1">
                <IconLogout class="w-4 h-4" />
              </button>
            </div>
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

    <!-- Guest pages -->
    <template v-else>
      <router-view />
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAuthStore } from './stores/auth'

const auth = useAuthStore()

const usagePercent = computed(() => {
  const limit = auth.user?.searchLimit ?? 1
  const used  = auth.user?.searchUsed  ?? 0
  return Math.min(100, Math.round((used / limit) * 100))
})

// Inline icon components
const IconSearch = { template: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>` }
const IconHistory = { template: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/></svg>` }
const IconAdmin = { template: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>` }
const IconLogout = { template: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>` }
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
