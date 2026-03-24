<template>
  <div class="p-6 max-w-7xl mx-auto">

    <div class="mb-7">
     <h1 class="text-2xl font-display font-bold text-zinc-100">Product Search</h1>

<div class="flex items-center gap-2 mt-1.5 mb-1">
  <img src="https://flagcdn.com/w40/de.png" alt="Germany" class="w-6 h-4 rounded-sm object-cover" />
  <img src="https://flagcdn.com/w40/gb.png" alt="UK" class="w-6 h-4 rounded-sm object-cover" />
  <img src="https://flagcdn.com/w40/it.png" alt="Italy" class="w-6 h-4 rounded-sm object-cover" />
  <img src="https://flagcdn.com/w40/us.png" alt="USA" class="w-6 h-4 rounded-sm object-cover" />
  <img src="https://flagcdn.com/w40/au.png" alt="Australia" class="w-6 h-4 rounded-sm object-cover" />
</div>
<p class="text-zinc-500 text-sm mt-1">Find profitable eBay products with AliExpress sourcing</p>
    </div>


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
        <span class="stat-label">Limit</span>
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
            v-model="keyword" type="text" class="input"
            placeholder='e.g. "wireless earbuds", "phone case", "led strip lights"'
            :disabled="loading" required />
        </div>
        <button type="submit" class="btn-primary shrink-0 px-8" :disabled="loading || (auth.remaining === 0 && !auth.isAdmin)">
          <div v-if="loading" class="spinner w-4 h-4" />
          <svg v-else class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
          {{ loading ? 'Searching…' : 'Hunt Products' }}
        </button>
      </form>

      <!-- Country scanning animation -->
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
      <div v-if="auth.remaining === 0 && !auth.isAdmin && !loading"
        class="mt-4 flex items-center gap-2 text-amber-400 text-sm bg-amber-400/10 border border-amber-400/20 rounded-xl px-4 py-3">
        <svg class="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
        </svg>
        Daily limit reached. Resets tomorrow or contact admin to upgrade your plan.
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
      <!-- Result header + controls -->
      <div class="flex items-center justify-between mb-4 flex-wrap gap-3">
        <h2 class="font-display font-semibold text-zinc-100">
          {{ sortedResults.length }} products
          <span class="text-zinc-500 font-normal">for "{{ lastKeyword }}"</span>
        </h2>

        <div class="flex items-center gap-2 flex-wrap">
          <!-- Country filter -->
          <select v-model="filterCountry"
            class="bg-zinc-800 border border-zinc-700 text-zinc-300 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:border-brand-500">
            <option value="">All countries</option>
            <option v-for="c in resultCountries" :key="c" :value="c">{{ flagFor(c) }} {{ c }}</option>
          </select>

          <!-- Sort -->
          <select v-model="sortBy"
            class="bg-zinc-800 border border-zinc-700 text-zinc-300 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:border-brand-500">
            <option value="profit">Profit ↓</option>
            <option value="price">Price ↑</option>
            <option value="sold">Sold ↓</option>
            <option value="reviews">Reviews ↓</option>
          </select>

          <!-- Excel export -->
          <button @click="exportExcel" class="btn-secondary">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
            </svg>
            Export Excel
          </button>
        </div>
      </div>

      <!-- Table -->
      <div class="table-container">
        <table class="table-base">
          <thead>
            <tr>
              <th>#</th>
              <th>Product</th>
              <th>Country</th>
              <th>eBay Price</th>
              <th>AliExpress</th>
              <th>Profit</th>
              <th>Margin</th>
              <th>Sold/wk</th>
              <th>Reviews</th>
              <th>Shipping</th>
              <th>Links</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(p, i) in sortedResults" :key="i">
              <!-- # -->
              <td class="text-zinc-600 text-xs font-mono">{{ i + 1 }}</td>

              <!-- Title -->
              <td class="max-w-xs">
                <p class="text-zinc-200 font-medium text-sm line-clamp-2 leading-snug">{{ p.title }}</p>
                <p class="text-xs text-zinc-600 mt-0.5">{{ p.deliveryDays }}</p>
              </td>

              <!-- Country -->
              <td>
                <span class="flex items-center gap-1.5 text-sm text-zinc-400">
                  <span>{{ flagFor(p.country) }}</span>{{ p.country }}
                </span>
              </td>

              <!-- eBay price -->
              <td><span class="font-mono text-zinc-200 text-sm">${{ p.ebayPrice.toFixed(2) }}</span></td>

              <!-- AliExpress price -->
              <td><span class="font-mono text-zinc-400 text-sm">${{ p.aliexpressPrice.toFixed(2) }}</span></td>

              <!-- Profit -->
              <td>
                <span :class="p.profit >= 0 ? 'profit-positive' : 'profit-negative'">
                  {{ p.profit >= 0 ? '+' : '' }}${{ p.profit.toFixed(2) }}
                </span>
              </td>

              <!-- Margin % -->
              <td>
                <span class="text-xs font-mono" :class="margin(p) >= 20 ? 'text-emerald-400' : 'text-zinc-500'">
                  {{ margin(p) }}%
                </span>
              </td>

              <!-- Sold -->
              <td><span class="text-emerald-400 font-mono text-sm font-medium">{{ p.soldLastWeek }}</span></td>

              <!-- Reviews -->
              <td><span class="text-zinc-400 text-sm font-mono">{{ p.reviews }}</span></td>

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
        <div class="px-6 py-3 border-t border-zinc-800 text-xs text-zinc-500 font-display">
          Showing {{ sortedResults.length }} of {{ results.length }} products
        </div>
      </div>
    </div>

    <!-- Empty after search -->
    <div v-else-if="!loading && searched" class="card p-12 text-center">
      <div class="w-16 h-16 bg-zinc-800 rounded-2xl flex items-center justify-center mx-auto mb-4">
        <svg class="w-8 h-8 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
      </div>
      <p class="font-display font-semibold text-zinc-300">No products found</p>
      <p class="text-zinc-500 text-sm mt-1">Try a different keyword or broaden your search.</p>
    </div>

    <!-- Initial state -->
    <div v-else-if="!loading && !searched" class="card p-12 text-center border-dashed">
      <div class="w-16 h-16 bg-brand-500/10 border border-brand-500/20 rounded-2xl flex items-center justify-center mx-auto mb-4">
        <svg class="w-8 h-8 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
      </div>
      <p class="font-display font-semibold text-zinc-300">Enter a keyword to start hunting</p>
      <p class="text-zinc-500 text-sm mt-1">Searches eBay across 5 countries — returns up to 50 profitable products.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const auth = useAuthStore()

const keyword        = ref('')
const lastKeyword    = ref('')
const results        = ref([])
const loading        = ref(false)
const searched       = ref(false)
const searchError    = ref('')
const sortBy         = ref('profit')
const filterCountry  = ref('')
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

// Unique countries found in results
const resultCountries = computed(() => [...new Set(results.value.map(p => p.country))].sort())

// Margin %
function margin(p) {
  return p.ebayPrice > 0 ? Math.round((p.profit / p.ebayPrice) * 100) : 0
}

const sortedResults = computed(() => {
  let r = [...results.value]
  if (filterCountry.value) r = r.filter(p => p.country === filterCountry.value)
  if (sortBy.value === 'profit')  r.sort((a, b) => b.profit - a.profit)
  if (sortBy.value === 'price')   r.sort((a, b) => a.ebayPrice - b.ebayPrice)
  if (sortBy.value === 'sold')    r.sort((a, b) => b.soldLastWeek - a.soldLastWeek)
  if (sortBy.value === 'reviews') r.sort((a, b) => b.reviews - a.reviews)
  return r
})

// Country animation
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
  filterCountry.value = ''

  startCountryAnimation()
  try {
    const res = await api.post('/search', { keyword: keyword.value.trim() })
    results.value     = res.data.products ?? []
    lastKeyword.value = keyword.value
    searched.value    = true
    auth.decrementSearch()
    await auth.refreshLimits()
  } catch (e) {
    searchError.value = e.response?.status === 429
      ? (e.response.data?.error ?? 'Daily limit reached.')
      : (e.response?.data?.error ?? 'Search failed. Please try again.')
    searched.value = true
  } finally {
    loading.value = false
    stopCountryAnimation()
  }
}

// ── Excel export (pure client-side, no library needed) ────────────────────────
function exportExcel() {
  const data = sortedResults.value
  if (!data.length) return

  // Build CSV, then trigger download as .csv (Excel opens it natively)
  const headers = [
    '#', 'Title', 'Country', 'Currency',
    'eBay Price', 'AliExpress Price', 'Profit', 'Margin %',
    'Sold/Week', 'Reviews', 'Free Shipping', 'Delivery',
    'eBay URL', 'AliExpress URL'
  ]

  const escape = v => {
    const s = String(v ?? '')
    return s.includes(',') || s.includes('"') || s.includes('\n')
      ? `"${s.replace(/"/g, '""')}"` : s
  }

  const rows = data.map((p, i) => [
    i + 1,
    p.title,
    p.country,
    p.currency,
    p.ebayPrice.toFixed(2),
    p.aliexpressPrice.toFixed(2),
    p.profit.toFixed(2),
    margin(p) + '%',
    p.soldLastWeek,
    p.reviews,
    p.freeShipping ? 'Yes' : 'No',
    p.deliveryDays,
    p.ebayUrl,
    p.aliexpressUrl,
  ].map(escape).join(','))

  const csv = [headers.join(','), ...rows].join('\n')
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })  // BOM for Excel
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  const safe = lastKeyword.value.replace(/[^a-z0-9]/gi, '_').toLowerCase()
  a.href     = url
  a.download = `ebay_results_${safe}_${new Date().toISOString().slice(0,10)}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>
