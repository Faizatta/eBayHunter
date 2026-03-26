<template>
  <div class="p-6 max-w-7xl mx-auto">

    <div class="mb-7">
      <h1 class="text-2xl font-display font-bold text-zinc-100">faiz </h1>
      <div class="flex items-center gap-2 mt-1.5 mb-1">
        <img src="https://flagcdn.com/w40/de.png" alt="Germany" class="w-6 h-4 rounded-sm object-cover" />
        <img src="https://flagcdn.com/w40/gb.png" alt="UK"      class="w-6 h-4 rounded-sm object-cover" />
        <img src="https://flagcdn.com/w40/it.png" alt="Italy"   class="w-6 h-4 rounded-sm object-cover" />
        <img src="https://flagcdn.com/w40/au.png" alt="Australia" class="w-6 h-4 rounded-sm object-cover" />
      </div>
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
        <button
          type="submit" class="btn-primary shrink-0 px-8"
          :disabled="loading || (auth.remaining === 0 && !auth.isAdmin)">
          <div v-if="loading" class="spinner w-4 h-4" />
          <svg v-else class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
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
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
        </svg>
        Daily limit reached. Resets tomorrow or contact admin to upgrade your plan.
      </div>
    </div>

    <!-- Error -->
    <div v-if="searchError"
      class="mb-5 flex items-center gap-2 text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-xl px-4 py-3">
      <svg class="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
      </svg>
      {{ searchError }}
    </div>

    <!-- ── Results ── -->
    <div v-if="results.length > 0" class="animate-fadein">

      <!-- Result header + controls -->
      <div class="flex items-center justify-between mb-4 flex-wrap gap-3">
        <h2 class="font-display font-semibold text-zinc-100">
          {{ sortedResults.length }} products
          <span class="text-zinc-500 font-normal">for "{{ lastKeyword }}"</span>
        </h2>

        <div class="flex items-center gap-2 flex-wrap">
          <select v-model="filterCountry"
            class="bg-zinc-800 border border-zinc-700 text-zinc-300 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:border-brand-500">
            <option value="">All countries</option>
            <option v-for="c in resultCountries" :key="c" :value="c">{{ flagFor(c) }} {{ c }}</option>
          </select>

          <select v-model="filterComp"
            class="bg-zinc-800 border border-zinc-700 text-zinc-300 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:border-brand-500">
            <option value="">All competition</option>
            <option value="low">🟢 Low</option>
            <option value="medium">🟡 Medium</option>
            <option value="high">🔴 High</option>
          </select>

          <select v-model="sortBy"
            class="bg-zinc-800 border border-zinc-700 text-zinc-300 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:border-brand-500">
            <option value="profit">Profit ↓</option>
            <option value="price">eBay Price ↑</option>
            <option value="sold">Sales/wk ↓</option>
            <option value="aliReviews">Ali Reviews ↓</option>
            <option value="margin">Margin ↓</option>
          </select>

          <button @click="exportExcel" class="btn-secondary">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
            </svg>
            Export CSV
          </button>
        </div>
      </div>

      <!-- Summary pills -->
      <div class="flex gap-2 flex-wrap mb-4">
        <span class="text-xs px-3 py-1.5 rounded-full bg-zinc-800 border border-zinc-700 text-zinc-400 font-display">
          Avg profit: <span class="text-emerald-400 font-semibold ml-1">{{ avgProfit }}</span>
        </span>
        <span class="text-xs px-3 py-1.5 rounded-full bg-zinc-800 border border-zinc-700 text-zinc-400 font-display">
          Avg sales/wk: <span class="text-brand-400 font-semibold ml-1">{{ avgSales }}</span>
        </span>
        <span class="text-xs px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-display">
          🟢 Low comp: <span class="font-semibold ml-1">{{ lowCompCount }}</span>
        </span>
        <span class="text-xs px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 font-display">
          🟡 Medium: <span class="font-semibold ml-1">{{ medCompCount }}</span>
        </span>
        <span class="text-xs px-3 py-1.5 rounded-full bg-red-500/10 border border-red-500/20 text-red-400 font-display">
          🔴 High: <span class="font-semibold ml-1">{{ highCompCount }}</span>
        </span>
      </div>

      <!-- Table -->
      <div class="table-container">
        <table class="table-base">
          <thead>
            <tr>
              <th class="w-8">#</th>
              <th>Product</th>
              <th>Country</th>
              <th>eBay Low</th>
              <th>Ali Price</th>
              <th>Profit</th>
              <th>Margin</th>
              <th>Sales/wk</th>
              <th>Weekly Sales</th>
              <th>Competition</th>
              <th>Ali ★</th>
              <th>Reviews</th>
              <th>Shipping</th>
              <th>Links</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(p, i) in sortedResults" :key="i">

              <td class="text-zinc-600 text-xs font-mono">{{ i + 1 }}</td>

              <td class="max-w-xs">
                <p class="text-zinc-200 font-medium text-sm line-clamp-2 leading-snug">{{ p.title || '—' }}</p>
                <p class="text-xs text-zinc-600 mt-0.5">{{ p.deliveryDays }}</p>
              </td>

              <td>
                <div class="flex flex-col gap-1">
                  <span class="flex items-center gap-1.5 text-sm text-zinc-400 whitespace-nowrap">
                    <span>{{ flagFor(p.country) }}</span>{{ p.country }}
                  </span>
                  <span v-if="p.localShipping"
                    class="text-xs text-emerald-400 font-display flex items-center gap-1">
                    <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                    </svg>
                    Local
                  </span>
                  <span v-else class="text-xs text-zinc-600 font-display">Intl.</span>
                </div>
              </td>

              <td>
                <div class="flex flex-col">
                  <span class="font-mono text-zinc-200 text-sm whitespace-nowrap">
                    {{ currencySymbol(p.currency) }}{{ fmt(p.ebayLowestPrice) }}
                  </span>
                  <span class="text-xs text-zinc-600 font-mono">
                    list: {{ currencySymbol(p.currency) }}{{ fmt(p.ebayPrice) }}
                  </span>
                </div>
              </td>

              <td>
                <span class="font-mono text-zinc-400 text-sm whitespace-nowrap">
                  {{ currencySymbol(p.currency) }}{{ fmt(p.aliexpressPrice) }}
                </span>
              </td>

              <td>
                <span :class="p.profit >= 0 ? 'profit-positive' : 'profit-negative'" class="whitespace-nowrap">
                  {{ p.profit >= 0 ? '+' : '' }}{{ currencySymbol(p.currency) }}{{ fmt(p.profit) }}
                </span>
              </td>

              <td>
                <span class="text-xs font-mono" :class="marginPct(p) >= 20 ? 'text-emerald-400' : 'text-zinc-500'">
                  {{ marginPct(p) }}%
                </span>
              </td>

              <td>
                <span class="text-emerald-400 font-mono text-sm font-medium">{{ p.soldPerWeek }}</span>
                <span class="text-zinc-600 text-xs font-display">/wk</span>
                <div class="text-xs text-zinc-600 font-mono mt-0.5">{{ p.totalSoldMonth }} / 30d</div>
              </td>

              <td>
                <div v-if="p.weeklyConsistency" class="flex items-end gap-1 h-6">
                  <div v-for="(w, wi) in parseWeeks(p.weeklyConsistency)" :key="wi"
                    class="w-2.5 rounded-sm bg-brand-500/60 min-h-[3px]"
                    :style="{ height: barHeight(w, p.weeklyConsistency) }"
                    :title="`Week ${wi + 1}: ${w} sold`" />
                </div>
                <span v-else class="text-zinc-700 text-xs">—</span>
              </td>

              <td>
                <span :class="compBadgeClass(p.competitionLevel)"
                  class="text-xs font-display font-semibold px-2.5 py-1 rounded-full whitespace-nowrap">
                  {{ compIcon(p.competitionLevel) }} {{ p.competitionLevel }}
                </span>
                <div class="text-xs text-zinc-600 font-mono mt-1">{{ p.activeListings }} listings</div>
              </td>

              <td>
                <span v-if="p.aliRating > 0" class="flex items-center gap-1 text-amber-400 text-sm font-mono font-medium">
                  ★ {{ fmt(p.aliRating, 1) }}
                </span>
                <span v-else class="text-zinc-700 text-xs">—</span>
              </td>

              <td>
                <span v-if="p.aliReviews > 0" class="text-zinc-400 text-sm font-mono">{{ p.aliReviews }}</span>
                <span v-else class="text-zinc-700 text-xs">—</span>
              </td>

              <td>
                <span v-if="p.freeShipping"
                  class="flex items-center gap-1 text-emerald-400 text-xs font-display whitespace-nowrap">
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                  </svg>
                  Free
                </span>
                <span v-else class="text-zinc-500 text-xs">Paid</span>
              </td>

              <td>
                <div class="flex flex-col gap-1.5">
                  <a :href="p.ebayUrl" target="_blank" rel="noopener noreferrer"
                    class="text-xs bg-zinc-800 hover:bg-brand-500/20 hover:text-brand-400 border border-zinc-700 hover:border-brand-500/30 text-zinc-300 px-2.5 py-1 rounded-lg transition-all font-display text-center">
                    eBay 
                  </a>
                  <a :href="p.aliexpressUrl" target="_blank" rel="noopener noreferrer"
                    class="text-xs bg-zinc-800 hover:bg-orange-500/20 hover:text-orange-400 border border-zinc-700 hover:border-orange-500/30 text-zinc-300 px-2.5 py-1 rounded-lg transition-all font-display text-center">
                    Ali ↗
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
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
            d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
      </div>
      <p class="font-display font-semibold text-zinc-300">No products found</p>
      <p class="text-zinc-500 text-sm mt-1">Try a different keyword or broaden your search.</p>
    </div>

    <!-- Initial state -->
    <div v-else-if="!loading && !searched" class="card p-12 text-center border-dashed">
      <div class="w-16 h-16 bg-brand-500/10 border border-brand-500/20 rounded-2xl flex items-center justify-center mx-auto mb-4">
        <svg class="w-8 h-8 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
      </div>
      <p class="font-display font-semibold text-zinc-300">Enter a keyword to start hunting</p>
      <p class="text-zinc-500 text-sm mt-1">Searches eBay across 4 countries — returns up to 40 profitable products.</p>
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
const filterComp     = ref('')
const currentCountry = ref('')

const countries = [
  { name: 'Germany',   flag: '🇩🇪' },
  { name: 'UK',        flag: '🇬🇧' },
  { name: 'Italy',     flag: '🇮🇹' },
  { name: 'Australia', flag: '🇦🇺' },
]
const countryFlags = Object.fromEntries(countries.map(c => [c.name, c.flag]))
function flagFor(name) { return countryFlags[name] ?? '🌐' }

// ── fmt: safe toFixed — never crashes on null/undefined ───────────────────
function fmt(val, decimals = 2) {
  const n = parseFloat(val)
  return isNaN(n) ? (0).toFixed(decimals) : n.toFixed(decimals)
}

// ── Currency symbol ────────────────────────────────────────────────────────
function currencySymbol(currency) {
  const map = { GBP: '£', EUR: '€', AUD: 'A$', USD: '$' }
  return map[currency] ?? (currency ? currency + ' ' : '')
}

// ── Margin % ───────────────────────────────────────────────────────────────
function marginPct(p) {
  const price  = parseFloat(p.ebayLowestPrice) || 0
  const profit = parseFloat(p.profit) || 0
  return price > 0 ? Math.round((profit / price) * 100) : 0
}

// ── Weekly bars ────────────────────────────────────────────────────────────
function parseWeeks(str) {
  if (!str) return []
  return str.split('/').map(s => parseInt(s.trim()) || 0)
}
function barHeight(w, str) {
  const weeks = parseWeeks(str)
  const mx = Math.max(...weeks, 1)
  return Math.max(3, Math.round((w / mx) * 24)) + 'px'
}

// ── Competition badge ──────────────────────────────────────────────────────
function compBadgeClass(level) {
  return {
    low:    'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20',
    medium: 'bg-amber-500/15 text-amber-400 border border-amber-500/20',
    high:   'bg-red-500/15 text-red-400 border border-red-500/20',
  }[level] ?? 'bg-zinc-800 text-zinc-400 border border-zinc-700'
}
function compIcon(level) {
  return { low: '🟢', medium: '🟡', high: '🔴' }[level] ?? '⚪'
}

// ── Normalise product — handles camelCase AND PascalCase from ASP.NET ─────
// This is the key fix: all fields are guaranteed safe types before rendering
function normalise(p) {
  return {
    title:             p.title            ?? p.Title            ?? '',
    country:           p.country          ?? p.Country          ?? '',
    currency:          p.currency         ?? p.Currency         ?? 'GBP',
    ebayPrice:         parseFloat(p.ebayPrice        ?? p.EbayPrice)        || 0,
    ebayLowestPrice:   parseFloat(p.ebayLowestPrice  ?? p.EbayLowestPrice)  || 0,
    aliexpressPrice:   parseFloat(p.aliexpressPrice  ?? p.AliexpressPrice)  || 0,
    aliRating:         parseFloat(p.aliRating        ?? p.AliRating)        || 0,
    aliReviews:        parseInt  (p.aliReviews       ?? p.AliReviews)       || 0,
    profit:            parseFloat(p.profit           ?? p.Profit)           || 0,
    soldPerWeek:       parseInt  (p.soldPerWeek      ?? p.SoldPerWeek)      || 0,
    totalSoldMonth:    parseInt  (p.totalSoldMonth   ?? p.TotalSoldMonth)   || 0,
    weeklyConsistency: p.weeklyConsistency ?? p.WeeklyConsistency           ?? '',
    competitionLevel:  p.competitionLevel  ?? p.CompetitionLevel            ?? 'medium',
    activeListings:    parseInt  (p.activeListings   ?? p.ActiveListings)   || 0,
    freeShipping:      p.freeShipping      ?? p.FreeShipping                ?? false,
    localShipping:     p.localShipping     ?? p.LocalShipping               ?? false,
    deliveryDays:      p.deliveryDays      ?? p.DeliveryDays                ?? '',
    ebayUrl:           p.ebayUrl           ?? p.EbayUrl                     ?? '#',
    aliexpressUrl:     p.aliexpressUrl     ?? p.AliexpressUrl               ?? '#',
  }
}

// ── Summary stats ──────────────────────────────────────────────────────────
const avgProfit = computed(() => {
  const r = sortedResults.value
  if (!r.length) return '—'
  const avg = r.reduce((s, p) => s + p.profit, 0) / r.length
  return (avg >= 0 ? '+' : '') + currencySymbol(r[0]?.currency) + avg.toFixed(2)
})
const avgSales = computed(() => {
  const r = sortedResults.value
  if (!r.length) return '—'
  return Math.round(r.reduce((s, p) => s + p.soldPerWeek, 0) / r.length) + '/wk'
})
const lowCompCount  = computed(() => sortedResults.value.filter(p => p.competitionLevel === 'low').length)
const medCompCount  = computed(() => sortedResults.value.filter(p => p.competitionLevel === 'medium').length)
const highCompCount = computed(() => sortedResults.value.filter(p => p.competitionLevel === 'high').length)

const resultCountries = computed(() =>
  [...new Set(results.value.map(p => p.country))].sort()
)

// ── Filtered + sorted results ──────────────────────────────────────────────
const sortedResults = computed(() => {
  let r = [...results.value]
  if (filterCountry.value) r = r.filter(p => p.country === filterCountry.value)
  if (filterComp.value)    r = r.filter(p => p.competitionLevel === filterComp.value)
  if (sortBy.value === 'profit')     r.sort((a, b) => b.profit - a.profit)
  if (sortBy.value === 'price')      r.sort((a, b) => a.ebayLowestPrice - b.ebayLowestPrice)
  if (sortBy.value === 'sold')       r.sort((a, b) => b.soldPerWeek - a.soldPerWeek)
  if (sortBy.value === 'aliReviews') r.sort((a, b) => b.aliReviews - a.aliReviews)
  if (sortBy.value === 'margin')     r.sort((a, b) => marginPct(b) - marginPct(a))
  return r
})

// ── Country animation ──────────────────────────────────────────────────────
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

// ── Run search ─────────────────────────────────────────────────────────────
async function runSearch() {
  if (!keyword.value.trim()) return
  loading.value       = true
  searchError.value   = ''
  results.value       = []
  searched.value      = false
  filterCountry.value = ''
  filterComp.value    = ''

  startCountryAnimation()
  try {
    const res = await api.post('/search', { keyword: keyword.value.trim() })
    // normalise() converts every field to a safe type — no more blank page crashes
    results.value     = (res.data.products ?? []).map(normalise)
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

// ── CSV export ─────────────────────────────────────────────────────────────
function exportExcel() {
  const data = sortedResults.value
  if (!data.length) return

  const headers = [
    '#', 'Title', 'Country', 'Currency',
    'eBay Price (Listed)', 'eBay Lowest Price',
    'AliExpress Price', 'Ali Rating', 'Ali Reviews',
    'Profit', 'Margin %',
    'Sales/Week', 'Total Sold (30d)', 'Weekly Breakdown',
    'Competition', 'Active Listings',
    'Free Shipping', 'Local Shipping', 'Delivery Days',
    'eBay URL', 'AliExpress URL',
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
    p.ebayLowestPrice.toFixed(2),
    p.aliexpressPrice.toFixed(2),
    p.aliRating > 0 ? p.aliRating.toFixed(1) : '',
    p.aliReviews,
    p.profit.toFixed(2),
    marginPct(p) + '%',
    p.soldPerWeek,
    p.totalSoldMonth,
    p.weeklyConsistency,
    p.competitionLevel,
    p.activeListings,
    p.freeShipping ? 'Yes' : 'No',
    p.localShipping ? 'Yes' : 'No',
    p.deliveryDays,
    p.ebayUrl,
    p.aliexpressUrl,
  ].map(escape).join(','))

  const csv  = [headers.join(','), ...rows].join('\n')
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  const safeName = lastKeyword.value.replace(/[^a-z0-9]/gi, '_').toLowerCase()
  a.href     = url
  a.download = `ebay_results_${safeName}_${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>
