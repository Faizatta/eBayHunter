<template>
  <div class="min-h-screen bg-zinc-950">

    <template v-if="auth.isLoggedIn">

      <!-- ══════════════════════════════════════════════
           ROOT LAYOUT: full-height flex row
           Mobile  → just main (sidebar hidden)
           Tablet  → icon sidebar + main
           Desktop → full sidebar + main
      ══════════════════════════════════════════════ -->
      <div class="flex h-screen overflow-hidden">

        <!-- ─────────────── SIDEBAR (md+) ─────────────── -->
        <aside
          :class="[
            'hidden md:flex flex-col flex-shrink-0',
            'bg-zinc-900 border-r border-zinc-800',
            'transition-[width] duration-300 ease-in-out',
            sidebarCollapsed ? 'md:w-16' : 'md:w-60'
          ]"
        >
          <!-- Logo -->
          <div
            :class="[
              'py-5 border-b border-zinc-800 flex items-center flex-shrink-0',
              sidebarCollapsed ? 'justify-center px-3' : 'gap-2.5 px-5'
            ]"
          >
            <div class="w-8 h-8 flex-shrink-0 bg-brand-500 rounded-lg flex items-center justify-center">
              <svg class="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
              </svg>
            </div>
            <span
              v-show="!sidebarCollapsed"
              class="font-display font-bold text-zinc-100 text-lg tracking-tight whitespace-nowrap overflow-hidden"
            >
              eBayHunter
            </span>
          </div>

          <!-- Collapse toggle (tablet md only, hidden on lg+) -->
          <button
            @click="sidebarCollapsed = !sidebarCollapsed"
            class="hidden md:flex lg:hidden items-center justify-center w-full py-2 flex-shrink-0
                   text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/60 transition-colors"
            :title="sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
          >
            <svg
              class="w-4 h-4 transition-transform duration-300"
              :class="sidebarCollapsed ? '' : 'rotate-180'"
              fill="none" viewBox="0 0 24 24" stroke="currentColor"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
            </svg>
          </button>

          <!-- Nav links -->
          <nav class="flex-1 px-2 py-4 flex flex-col gap-1 overflow-y-auto overflow-x-hidden">

            <router-link to="/dashboard" custom v-slot="{ navigate, isActive }">
              <button
                @click="navigate"
                :title="sidebarCollapsed ? 'Product Search' : undefined"
                :class="['nav-item w-full', isActive && 'active', sidebarCollapsed ? 'justify-center px-2' : '']"
              >
                <svg class="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                </svg>
                <span v-show="!sidebarCollapsed">Product Search</span>
              </button>
            </router-link>

            <router-link to="/history" custom v-slot="{ navigate, isActive }">
              <button
                @click="navigate"
                :title="sidebarCollapsed ? 'Search History' : undefined"
                :class="['nav-item w-full', isActive && 'active', sidebarCollapsed ? 'justify-center px-2' : '']"
              >
                <svg class="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
                  <path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>
                </svg>
                <span v-show="!sidebarCollapsed">Search History</span>
              </button>
            </router-link>

            <template v-if="auth.isAdmin">
              <div v-show="!sidebarCollapsed" class="px-4 pt-4 pb-1">
                <span class="text-xs font-display uppercase tracking-widest text-zinc-600">Admin</span>
              </div>
              <div v-show="sidebarCollapsed" class="border-t border-zinc-800 my-2 mx-2" />
              <router-link to="/admin" custom v-slot="{ navigate, isActive }">
                <button
                  @click="navigate"
                  :title="sidebarCollapsed ? 'Admin Panel' : undefined"
                  :class="['nav-item w-full', isActive && 'active', sidebarCollapsed ? 'justify-center px-2' : '']"
                >
                  <svg class="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                  </svg>
                  <span v-show="!sidebarCollapsed">Admin Panel</span>
                </button>
              </router-link>
            </template>
          </nav>

          <!-- Bottom: usage + user + logout -->
          <div class="px-3 py-4 border-t border-zinc-800 space-y-3 flex-shrink-0">

            <!-- Usage bar (expanded) -->
            <div v-if="!auth.isAdmin" v-show="!sidebarCollapsed" class="px-2">
              <div class="flex justify-between text-xs font-display text-zinc-500 mb-1.5">
                <span>Searches</span>
                <span class="text-zinc-300">{{ auth.user?.searchUsed ?? 0 }} / {{ auth.user?.searchLimit ?? 0 }}</span>
              </div>
              <div class="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-500"
                  :class="usagePercent >= 90 ? 'bg-red-500' : usagePercent >= 70 ? 'bg-amber-500' : 'bg-brand-500'"
                  :style="{ width: usagePercent + '%' }"
                />
              </div>
              <p v-if="auth.remaining === 0" class="text-xs text-red-400 mt-1.5 font-display">
                No searches left — contact admin
              </p>
            </div>

            <!-- Usage dot (collapsed) -->
            <div v-if="!auth.isAdmin" v-show="sidebarCollapsed" class="flex justify-center">
              <div
                class="w-2 h-2 rounded-full"
                :class="usagePercent >= 90 ? 'bg-red-500' : usagePercent >= 70 ? 'bg-amber-500' : 'bg-brand-500'"
                :title="`${auth.user?.searchUsed ?? 0} / ${auth.user?.searchLimit ?? 0} searches used`"
              />
            </div>

            <!-- Admin badge (expanded) -->
            <div v-if="auth.isAdmin" v-show="!sidebarCollapsed" class="px-2">
              <div class="flex items-center gap-2 text-xs text-purple-400 font-display">
                <svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                </svg>
                Unlimited searches
              </div>
            </div>

            <!-- User card (expanded) -->
            <div v-show="!sidebarCollapsed" class="flex items-center gap-3 px-2 py-2 rounded-xl bg-zinc-800/50">
              <div class="w-7 h-7 rounded-full bg-brand-500/20 border border-brand-500/30
                          flex items-center justify-center flex-shrink-0">
                <span class="text-brand-400 text-xs font-display font-bold uppercase">
                  {{ auth.user?.email?.[0] ?? '?' }}
                </span>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-xs font-display text-zinc-200 truncate">{{ auth.user?.email }}</p>
                <span :class="['badge', 'badge-' + auth.roleBadge]">{{ auth.user?.role }}</span>
              </div>
            </div>

            <!-- Avatar only (collapsed) -->
            <div v-show="sidebarCollapsed" class="flex justify-center">
              <div
                class="w-7 h-7 rounded-full bg-brand-500/20 border border-brand-500/30
                       flex items-center justify-center cursor-default"
                :title="auth.user?.email"
              >
                <span class="text-brand-400 text-xs font-display font-bold uppercase">
                  {{ auth.user?.email?.[0] ?? '?' }}
                </span>
              </div>
            </div>

            <!-- Logout -->
            <button
              @click="doLogout"
              :class="[
                'w-full flex items-center gap-2 py-2.5 rounded-xl',
                'bg-zinc-800 hover:bg-red-500/15 border border-zinc-700 hover:border-red-500/40',
                'text-zinc-400 hover:text-red-400 font-display font-medium text-sm',
                'transition-all duration-200 group',
                sidebarCollapsed ? 'justify-center px-2' : 'justify-center px-4'
              ]"
              title="Sign Out"
            >
              <svg class="w-4 h-4 flex-shrink-0 transition-transform group-hover:translate-x-0.5"
                   fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
              </svg>
              <span v-show="!sidebarCollapsed">Sign Out</span>
            </button>
          </div>
        </aside>

        <!-- ─────────────── MAIN CONTENT COLUMN ─────────────── -->
        <!--
          KEY FIX: The bottom tab bar lives INSIDE this column as a flex child.
          This means it pushes the <main> content UP naturally — no absolute
          positioning, no pb-16 hacks, no clipping from h-screen overflow-hidden.
        -->
        <div class="flex-1 flex flex-col min-w-0 overflow-hidden">

          <!-- Mobile top bar -->
          <header class="md:hidden flex items-center justify-between px-4 py-3 flex-shrink-0
                         bg-zinc-900 border-b border-zinc-800 z-10">
            <div class="flex items-center gap-2.5">
              <div class="w-7 h-7 bg-brand-500 rounded-lg flex items-center justify-center">
                <svg class="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                </svg>
              </div>
              <span class="font-display font-bold text-zinc-100 text-base tracking-tight">eBayHunter</span>
            </div>
            <button
              @click="drawerOpen = true"
              class="p-2 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
              aria-label="Open account menu"
            >
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
              </svg>
            </button>
          </header>

          <!-- Scrollable page content — takes all remaining space -->
          <main class="flex-1 overflow-y-auto min-h-0">
            <router-view v-slot="{ Component }">
              <transition name="fade" mode="out-in">
                <component :is="Component" />
              </transition>
            </router-view>
          </main>

          <!-- Mobile bottom tab bar — flex child, pushes content up, never clips -->
          <nav
            class="md:hidden flex-shrink-0 flex items-stretch
                   bg-zinc-900 border-t border-zinc-800"
            style="padding-bottom: env(safe-area-inset-bottom, 0px)"
          >
            <router-link to="/dashboard" custom v-slot="{ navigate, isActive }">
              <button @click="navigate" :class="['bottom-tab', isActive && 'bottom-tab-active']">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                </svg>
                <span>Search</span>
              </button>
            </router-link>

            <router-link to="/history" custom v-slot="{ navigate, isActive }">
              <button @click="navigate" :class="['bottom-tab', isActive && 'bottom-tab-active']">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
                  <path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>
                </svg>
                <span>History</span>
              </button>
            </router-link>

            <router-link v-if="auth.isAdmin" to="/admin" custom v-slot="{ navigate, isActive }">
              <button @click="navigate" :class="['bottom-tab', isActive && 'bottom-tab-active']">
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                </svg>
                <span>Admin</span>
              </button>
            </router-link>

            <button @click="drawerOpen = true" class="bottom-tab">
              <div class="w-5 h-5 rounded-full bg-brand-500/20 border border-brand-500/30
                          flex items-center justify-center">
                <span class="text-brand-400 text-[10px] font-display font-bold uppercase leading-none">
                  {{ auth.user?.email?.[0] ?? '?' }}
                </span>
              </div>
              <span>Account</span>
            </button>
          </nav>

        </div><!-- /main column -->
      </div><!-- /flex h-screen -->

      <!-- ════════════════════════════════════
           MOBILE DRAWER  (fixed overlay)
      ════════════════════════════════════ -->
      <transition name="drawer-backdrop">
        <div
          v-if="drawerOpen"
          class="md:hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
          @click="drawerOpen = false"
        />
      </transition>

      <transition name="drawer-slide">
        <div
          v-if="drawerOpen"
          class="md:hidden fixed top-0 right-0 bottom-0 z-[60] w-72
                 bg-zinc-900 border-l border-zinc-800 flex flex-col shadow-2xl"
        >
          <div class="flex items-center justify-between px-5 py-4 border-b border-zinc-800 flex-shrink-0">
            <span class="font-display font-bold text-zinc-200 text-sm">Account</span>
            <button
              @click="drawerOpen = false"
              class="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
            >
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>

          <div class="flex-1 overflow-y-auto px-4 py-5 space-y-5">
            <div class="flex items-center gap-3 p-3 rounded-xl bg-zinc-800/60 border border-zinc-700/50">
              <div class="w-9 h-9 rounded-full bg-brand-500/20 border border-brand-500/30
                          flex items-center justify-center flex-shrink-0">
                <span class="text-brand-400 text-sm font-display font-bold uppercase">
                  {{ auth.user?.email?.[0] ?? '?' }}
                </span>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-display text-zinc-200 truncate">{{ auth.user?.email }}</p>
                <span :class="['badge', 'badge-' + auth.roleBadge]">{{ auth.user?.role }}</span>
              </div>
            </div>

            <div v-if="!auth.isAdmin" class="space-y-2">
              <div class="flex justify-between text-xs font-display text-zinc-500">
                <span>Search usage</span>
                <span class="text-zinc-300">{{ auth.user?.searchUsed ?? 0 }} / {{ auth.user?.searchLimit ?? 0 }}</span>
              </div>
              <div class="h-2 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-500"
                  :class="usagePercent >= 90 ? 'bg-red-500' : usagePercent >= 70 ? 'bg-amber-500' : 'bg-brand-500'"
                  :style="{ width: usagePercent + '%' }"
                />
              </div>
              <p v-if="auth.remaining === 0" class="text-xs text-red-400 font-display">
                No searches left — contact admin
              </p>
            </div>

            <div v-else class="flex items-center gap-2 text-xs text-purple-400 font-display">
              <svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
              Unlimited searches
            </div>
          </div>

          <div class="px-4 py-5 border-t border-zinc-800 flex-shrink-0"
               style="padding-bottom: max(1.25rem, env(safe-area-inset-bottom))">
            <button
              @click="doLogout"
              class="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl
                     bg-zinc-800 hover:bg-red-500/15 border border-zinc-700 hover:border-red-500/40
                     text-zinc-400 hover:text-red-400 font-display font-medium text-sm
                     transition-all duration-200 group"
            >
              <svg class="w-4 h-4 flex-shrink-0 transition-transform group-hover:translate-x-0.5"
                   fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
              </svg>
              Sign Out
            </button>
          </div>
        </div>
      </transition>

    </template>

    <template v-else>
      <router-view />
    </template>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'

const auth   = useAuthStore()
const router = useRouter()

const drawerOpen       = ref(false)
const sidebarCollapsed = ref(false)

const usagePercent = computed(() => {
  const limit = auth.user?.searchLimit ?? 1
  const used  = auth.user?.searchUsed  ?? 0
  if (limit <= 0) return 0
  return Math.min(100, Math.round((used / limit) * 100))
})

function doLogout() {
  auth.logout()
  drawerOpen.value = false
  router.push('/login')
}
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from,  .fade-leave-to      { opacity: 0; }

.drawer-backdrop-enter-active, .drawer-backdrop-leave-active { transition: opacity 0.25s; }
.drawer-backdrop-enter-from,   .drawer-backdrop-leave-to     { opacity: 0; }

.drawer-slide-enter-active, .drawer-slide-leave-active {
  transition: transform 0.28s cubic-bezier(0.4, 0, 0.2, 1);
}
.drawer-slide-enter-from, .drawer-slide-leave-to { transform: translateX(100%); }

.bottom-tab {
  @apply flex-1 flex flex-col items-center justify-center gap-1 py-2.5
         font-display font-medium text-[10px] text-zinc-500
         transition-colors duration-150 cursor-pointer;
}
.bottom-tab-active { @apply text-brand-400; }
</style>
