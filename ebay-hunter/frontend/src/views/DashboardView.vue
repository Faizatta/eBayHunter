<template>
  <div class="p-6 max-w-7xl mx-auto">
    <!-- Header -->
    <div class="mb-7">
      <h1 class="text-2xl font-display font-bold text-zinc-100">Product Search</h1>
      <p class="text-zinc-500 text-sm mt-1">Find profitable eBay products with AliExpress sourcing</p>
    </div>

    <!-- Stats row -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-7">
      <div class="stat-card">
        <span class="stat-label">Searches Used</span>
        <span class="stat-value">{{ auth.user?.searchUsed ?? 0 }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">Remaining</span>
        <span class="stat-value text-brand-400">{{ auth.remaining }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">Daily Limit</span>
        <span class="stat-value">{{ auth.user?.searchLimit ?? 0 }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">Your Plan</span>
        <div class="mt-1">
          <span :class="['badge', 'badge-' + auth.roleBadge, 'text-sm px-3 py-1']">{{ auth.user?.role }}</span>
        </div>
      </div>
    </div>

    <!-- Search box -->
    <div class="card p-5 mb-6">
      <form @submit.prevent="runSearch" class="flex gap-3 flex-wrap sm:flex-nowrap">
        <div class="flex-1 min-w-0">
          <input
            v-model="keyword"
            type="text"
            class="input"
            placeholder='e.g. "wireless earbuds", "phone case", "led strip lights"'
            :disabled="loading"
            required
          />
        </div>
        <button type="submit" class="btn-primary shrink-0 px-8" :disabled="loading || auth.remaining === 0">
          <div v-if="loading" class="spinner w-4 h-4" />
          <svg v-else class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
          {{ loading ? 'Searching…' : 'Hunt Products' }}
        </button>
      </form>

      <!-- Countries being searched -->
      <div v-if="loading" class="mt-4">
        <p class="text-xs text-zinc-500 mb-2 font-display">Searching across countries…</p>
        <div class="flex gap-2 flex-wrap">
          <span v-for="c in countries" :key="c.name"
            :class="['flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border transition-all duration-500',
              currentCountry === c.name
                ? 'bg-brand-500/20 border-brand-500/40 text-brand-300'
                : 'bg-zinc-800 border-zinc-700 text-zinc-500']">
            <span>{{ c.flag }}</span> {{ c.name }}
          </span>
        </div>
      </div>

      <!-- Limit warning -->
      <div v-if="auth.remaining === 0 && !loading" class="mt-4 flex items-center gap-2 text-amber-400 text-sm bg-amber-400/10 border border-amber-400/20 rounded-xl px-4 py-3">
        <svg class="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
        </svg>
        Daily limit reached. Resets tomorrow or upgrade your plan.
      </div>
    </div>

    <!-- Error -->
    <div v-if="searchError" class="mb-5 flex items-center gap-2 text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-xl px-4 py-3">
      <svg class="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
      </svg>
      {{ searchError }}
    </div>

    <!-- Results -->
    <div v-if="results.length > 0" class="animate-fadein">
      <!-- Result header -->
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="font-display font-semibold text-zinc-100">
            {{ results.length }} products found
            <span class="text-zinc-500 font-normal">for "{{ lastKeyword }}"</span>
          </h2>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-xs text-zinc-500 font-display">Sort by:</span>
          <select v-model="sortBy" class="bg-zinc-800 border border-zinc-700 text-zinc-300 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:border-brand-500">
            <option value="profit">Profit ↓</option>
            <option value="price">Price ↑</option>
            <option value="sold">Sold ↓</option>
            <option value="reviews">Reviews ↓</option>
          </select>
        </div>
      </div>

      <!-- Table -->
      <div class="table-container">
        <table class="table-base">
          <thead>
            <tr>
              <th>Product</th>
              <th>Country</th>
              <th>eBay Price</th>
              <th>AliExpress</th>
              <th>Profit</th>
              <th>Sold/wk</th>
              <th>Reviews</th>
              <th>Shipping</th>
              <th>Links</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(p, i) in sortedResults" :key="i">
              <!-- Title -->
              <td class="max-w-xs">
                <p class="text-zinc-200 font-medium text-sm line-clamp-2 leading-snug">{{ p.title }}</p>
                <p class="text-xs text-zinc-600 mt-0.5">{{ p.deliveryDays }}</p>
              </td>

              <!-- Country -->
              <td>
                <span class="flex items-center gap-1.5 text-sm text-zinc-400">
                  <span>{{ flagFor(p.country) }}</span>
                  {{ p.country }}
                </span>
              </td>

              <!-- eBay price -->
              <td>
                <span class="font-mono text-zinc-200 text-sm">${{ p.ebayPrice.toFixed(2) }}</span>
              </td>

              <!-- AliExpress price -->
              <td>
                <span class="font-mono text-zinc-400 text-sm">${{ p.aliexpressPrice.toFixed(2) }}</span>
              </td>

              <!-- Profit -->
              <td>
                <span :class="p.profit >= 0 ? 'profit-positive' : 'profit-negative'">
                  {{ p.profit >= 0 ? '+' : '' }}${{ p.profit.toFixed(2) }}
                </span>
              </td>

              <!-- Sold -->
              <td>
                <span class="text-emerald-400 font-mono text-sm font-medium">{{ p.soldLastWeek }}</span>
              </td>

              <!-- Reviews -->
              <td>
                <span class="text-zinc-400 text-sm font-mono">{{ p.reviews }}</span>
              </td>

              <!-- Shipping -->
              <td>
                <span v-if="p.freeShipping" class="flex items-center gap-1 text-emerald-400 text-xs font-display">
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                  </svg>
                  Free
                </span>
                <span v-else class="text-zinc-500 text-xs">Paid</span>
              </td>

              <!-- Links -->
              <td>
                <div class="flex gap-2">
                  <a :href="p.ebayUrl" target="_blank" rel="noopener noreferrer"
                    class="text-xs bg-zinc-800 hover:bg-brand-500/20 hover:text-brand-400 border border-zinc-700 hover:border-brand-500/30 text-zinc-300 px-2.5 py-1 rounded-lg transition-all font-display">
                    eBay
                  </a>
                  <a :href="p.aliexpressUrl" target="_blank" rel="noopener noreferrer"
                    class="text-xs bg-zinc-800 hover:bg-orange-500/20 hover:text-orange-400 border border-zinc-700 hover:border-orange-500/30 text-zinc-300 px-2.5 py-1 rounded-lg transition-all font-display">
                    Ali
                  </a>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="!loading && searched" class="card p-12 text-center">
      <div class="w-16 h-16 bg-zinc-800 rounded-2xl flex items-center justify-center mx-auto mb-4">
        <svg class="w-8 h-8 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
      </div>
      <p class="font-display font-semibold text-zinc-300">No products found</p>
      <p class="text-zinc-500 text-sm mt-1">Try a different keyword or broaden your search.</p>
    </div>

    <!-- Initial empty state -->
    <div v-else-if="!loading && !searched" class="card p-12 text-center border-dashed">
      <div class="w-16 h-16 bg-brand-500/10 border border-brand-500/20 rounded-2xl flex items-center justify-center mx-auto mb-4">
        <svg class="w-8 h-8 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
      </div>
      <p class="font-display font-semibold text-zinc-300">Enter a keyword to start hunting</p>
      <p class="text-zinc-500 text-sm mt-1">The bot will search eBay across 5 countries and find profitable opportunities.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const auth = useAuthStore()

const keyword      = ref('')
const lastKeyword  = ref('')
const results      = ref([])
const loading      = ref(false)
const searched     = ref(false)
const searchError  = ref('')
const sortBy       = ref('profit')
const currentCountry = ref('')

const countries = [
  { name: 'Germany',   flag: '🇩🇪' },
  { name: 'UK',        flag: '🇬🇧' },
  { name: 'Italy',     flag: '🇮🇹' },
  { name: 'USA',       flag: '🇺🇸' },
  { name: 'Australia', flag: '🇦🇺' },
]

const countryFlags = Object.fromEntries(countries.map(c => [c.name, c.flag]))
function flagFor(name) { return countryFlags[name] ?? '🌐' }

const sortedResults = computed(() => {
  const r = [...results.value]
  if (sortBy.value === 'profit')  return r.sort((a, b) => b.profit - a.profit)
  if (sortBy.value === 'price')   return r.sort((a, b) => a.ebayPrice - b.ebayPrice)
  if (sortBy.value === 'sold')    return r.sort((a, b) => b.soldLastWeek - a.soldLastWeek)
  if (sortBy.value === 'reviews') return r.sort((a, b) => b.reviews - a.reviews)
  return r
})

// Simulate country scanning visuals
let countryInterval = null
function startCountryAnimation() {
  let idx = 0
  currentCountry.value = countries[0].name
  countryInterval = setInterval(() => {
    idx = (idx + 1) % countries.length
    currentCountry.value = countries[idx].name
  }, 1800)
}
function stopCountryAnimation() {
  clearInterval(countryInterval)
  currentCountry.value = ''
}

async function runSearch() {
  if (!keyword.value.trim()) return
  loading.value    = true
  searchError.value = ''
  results.value    = []
  searched.value   = false

  startCountryAnimation()

  try {
    const res = await api.post('/search', { keyword: keyword.value.trim() })
    results.value   = res.data.products ?? []
    lastKeyword.value = keyword.value
    searched.value  = true
    auth.decrementSearch()
    await auth.refreshLimits()
  } catch (e) {
    if (e.response?.status === 429) {
      searchError.value = e.response.data?.error ?? 'Daily limit reached.'
    } else {
      searchError.value = e.response?.data?.error ?? 'Search failed. Please try again.'
    }
    searched.value = true
  } finally {
    loading.value = false
    stopCountryAnimation()
  }
}
</script>
