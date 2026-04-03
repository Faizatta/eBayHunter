<template>
  <div class="p-6 max-w-7xl mx-auto">

    <div class="mb-7">
      <h1 class="text-2xl font-display font-bold text-zinc-100">Product Search</h1>
      <div class="flex items-center gap-2 mt-1.5 mb-1">
        <img src="https://flagcdn.com/w40/de.png" alt="Germany"   class="w-6 h-4 rounded-sm object-cover" />
        <img src="https://flagcdn.com/w40/gb.png" alt="UK"        class="w-6 h-4 rounded-sm object-cover" />
        <img src="https://flagcdn.com/w40/it.png" alt="Italy"     class="w-6 h-4 rounded-sm object-cover" />
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
          </select>

          <button @click="exportCSV" class="btn-secondary">
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
              <th>eBay Price</th>
              <th>AliExpress</th>
              <th>Profit</th>
              <th>Shipping</th>
              <th>Links</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(p, i) in sortedResults" :key="i">

              <td class="text-zinc-600 text-xs font-mono">{{ i + 1 }}</td>

              <!-- Product title -->
              <td class="max-w-xs">
                <p class="text-zinc-200 font-medium text-sm line-clamp-2 leading-snug">{{ p.title || '—' }}</p>
              </td>

              <!-- Country -->
              <td>
                <span class="flex items-center gap-1.5 text-sm text-zinc-400 whitespace-nowrap">
                  <span>{{ flagFor(p.country) }}</span>{{ p.country }}
                </span>
              </td>

              <!-- eBay Price (sold avg) -->
              <td>
                <span class="font-mono text-blue-300 text-sm whitespace-nowrap font-semibold">
                  {{ currencySymbol(p.currency) }}{{ fmt(p.ebaySoldPrice || p.ebayPrice) }}
                </span>
              </td>

              <!-- AliExpress Price -->
              <td>
                <span class="font-mono text-zinc-300 text-sm whitespace-nowrap">
                  {{ currencySymbol(p.currency) }}{{ fmt(p.aliexpressPrice) }}
                </span>
              </td>

              <!-- Profit -->
              <td>
                <span
                  :class="p.profit >= PREFERRED_MIN_PROFIT
                    ? 'profit-positive'
                    : p.profit > 0
                      ? 'text-amber-400 font-mono font-semibold'
                      : 'profit-negative'"
                  class="whitespace-nowrap text-sm">
                  {{ p.profit >= 0 ? '+' : '' }}{{ currencySymbol(p.currency) }}{{ fmt(p.profit) }}
                </span>
              </td>

              <!-- Shipping -->
              <td>
                <span v-if="p.freeShipping || p.aliShippingCost === 0"
                  class="flex items-center gap-1 text-emerald-400 text-xs font-display whitespace-nowrap">
                  <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                  </svg>
                  Free
                </span>
                <span v-else class="font-mono text-amber-400 text-sm whitespace-nowrap">
                  +{{ currencySymbol(p.currency) }}{{ fmt(p.aliShippingCost) }}
                </span>
              </td>

              <!-- Links -->
              <td>
                <div class="flex flex-col gap-1.5">
                  <a :href="buildEbayLink(p)" target="_blank" rel="noopener noreferrer"
                    class="text-xs bg-zinc-800 hover:bg-brand-500/20 hover:text-brand-400 border border-zinc-700 hover:border-brand-500/30 text-zinc-300 px-2.5 py-1 rounded-lg transition-all font-display text-center">
                    eBay ↗
                  </a>
                  <a :href="p.aliItemUrl || p.aliexpressUrl" target="_blank" rel="noopener noreferrer"
                    class="text-xs bg-zinc-800 hover:bg-orange-500/20 hover:text-orange-400 border border-zinc-700 hover:border-orange-500/30 text-zinc-300 px-2.5 py-1 rounded-lg transition-all font-display text-center">
                    Ali ↗
                  </a>
                </div>
              </td>

            </tr>
          </tbody>
        </table>

        <div class="px-6 py-3 border-t border-zinc-800 text-xs text-zinc-500 font-display">
          Showing {{ sortedResults.length }} of {{ results.length }} products ·
          SOLD listings only · last 30 days
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
      <p class="text-zinc-500 text-sm mt-1">
        Try a different keyword. Common reasons: weekly sales out of range, no recent sold data, or profit ≤ 0.
      </p>
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
      <p class="text-zinc-500 text-sm mt-1">
        Searches eBay SOLD listings across 4 countries — last 30 days only, products with consistent weekly sales.
      </p>
    </div>

  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const auth = useAuthStore()

// ── Constants ──────────────────────────────────────────────────────
const PREFERRED_MIN_PROFIT = 5.0

// ── eBay base URLs per country name ───────────────────────────────
const EBAY_BASE_URLS = {
  'UK':        'https://www.ebay.co.uk',
  'Germany':   'https://www.ebay.de',
  'Italy':     'https://www.ebay.it',
  'Australia': 'https://www.ebay.com.au',
  'USA':       'https://www.ebay.com',
}

// ── State ──────────────────────────────────────────────────────────
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

// ── Build correct eBay sold-search link for the product's country ──
function buildEbayLink(p) {
  // If we already have a direct item URL, use it
  const itemUrl = p.ebayItemUrl || p.ebayUrl || ''
  if (itemUrl && itemUrl !== '#') return itemUrl

  // Otherwise build a country-correct sold-search URL
  const base = EBAY_BASE_URLS[p.country] ?? 'https://www.ebay.co.uk'
  const q    = encodeURIComponent(p.title || '')
  return (
    `${base}/sch/i.html?_nkw=${q}` +
    `&LH_Sold=1&LH_Complete=1&LH_BIN=1` +
    `&LH_ItemCondition=1000&LH_PrefLoc=1&_sop=10`
  )
}

// ── Helpers ────────────────────────────────────────────────────────
function fmt(val, decimals = 2) {
  const n = parseFloat(val)
  return isNaN(n) ? (0).toFixed(decimals) : n.toFixed(decimals)
}

function currencySymbol(currency) {
  const map = { GBP: '£', EUR: '€', AUD: 'A$', USD: '$' }
  return map[currency] ?? (currency ? currency + ' ' : '')
}

// ── Normalise API response ─────────────────────────────────────────
function normalise(p) {
  const ebayPrice     = parseFloat(p.ebayPrice     ?? p.EbayPrice)     || 0
  const ebaySoldPrice = parseFloat(p.ebaySoldPrice ?? p.EbaySoldPrice) || 0
  const aliPrice      = parseFloat(p.aliexpressPrice ?? p.AliexpressPrice) || 0
  const aliShip       = parseFloat(p.aliShippingCost ?? p.AliShippingCost) || 0

  const profit = parseFloat(p.profit ?? p.Profit)
    ?? parseFloat((ebaySoldPrice - aliPrice - aliShip).toFixed(2))
  const margin = parseFloat(p.profitMarginPct ?? p.ProfitMarginPct)
    ?? (ebaySoldPrice > 0 ? parseFloat(((profit / ebaySoldPrice) * 100).toFixed(1)) : 0)

  return {
    title:            p.title            ?? p.Title            ?? '',
    country:          p.country          ?? p.Country          ?? '',
    currency:         p.currency         ?? p.Currency         ?? 'GBP',
    ebayPrice,
    ebaySoldPrice,
    aliexpressPrice:  aliPrice,
    aliShippingCost:  aliShip,
    profit:           isNaN(profit) ? 0 : profit,
    profitMarginPct:  isNaN(margin) ? 0 : margin,
    freeShipping:     p.freeShipping ?? p.FreeShipping ?? false,
    competitionLevel: p.competitionLevel ?? p.CompetitionLevel ?? 'medium',
    ebayUrl:          p.ebayUrl     ?? p.EbayUrl     ?? '#',
    aliexpressUrl:    p.aliexpressUrl ?? p.AliexpressUrl ?? '#',
    ebayItemUrl:      p.ebayItemUrl ?? p.EbayItemUrl ?? '',
    aliItemUrl:       p.aliItemUrl  ?? p.AliItemUrl  ?? '',
  }
}

// ── Summary stats ──────────────────────────────────────────────────
const avgProfit = computed(() => {
  const r = sortedResults.value
  if (!r.length) return '—'
  const avg = r.reduce((s, p) => s + p.profit, 0) / r.length
  const sym = currencySymbol(r[0]?.currency)
  return (avg >= 0 ? '+' : '') + sym + avg.toFixed(2)
})
const lowCompCount  = computed(() => sortedResults.value.filter(p => p.competitionLevel === 'low').length)
const medCompCount  = computed(() => sortedResults.value.filter(p => p.competitionLevel === 'medium').length)
const highCompCount = computed(() => sortedResults.value.filter(p => p.competitionLevel === 'high').length)

const resultCountries = computed(() =>
  [...new Set(results.value.map(p => p.country))].sort()
)

// ── Filtered + sorted results ──────────────────────────────────────
const sortedResults = computed(() => {
  let r = [...results.value]
  if (filterCountry.value) r = r.filter(p => p.country === filterCountry.value)
  if (filterComp.value)    r = r.filter(p => p.competitionLevel === filterComp.value)
  if (sortBy.value === 'profit') r.sort((a, b) => b.profit - a.profit)
  if (sortBy.value === 'price')  r.sort((a, b) => a.ebaySoldPrice - b.ebaySoldPrice)
  return r
})

// ── Country animation ──────────────────────────────────────────────
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

// ── Run search ─────────────────────────────────────────────────────
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

// ── CSV export ─────────────────────────────────────────────────────
function exportCSV() {
  const data = sortedResults.value
  if (!data.length) return

  const headers = [
    '#', 'Title', 'Country', 'Currency',
    'eBay Price', 'AliExpress Price', 'Ali Shipping',
    'Profit', 'Free Shipping', 'Competition',
    'eBay URL', 'Ali URL',
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
    fmt(p.ebaySoldPrice || p.ebayPrice),
    fmt(p.aliexpressPrice),
    fmt(p.aliShippingCost),
    fmt(p.profit),
    p.freeShipping ? 'Yes' : 'No',
    p.competitionLevel,
    buildEbayLink(p),
    p.aliItemUrl || p.aliexpressUrl,
  ].map(escape).join(','))

  const csv  = [headers.join(','), ...rows].join('\n')
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  const safe = lastKeyword.value.replace(/[^a-z0-9]/gi, '_').toLowerCase()
  a.href     = url
  a.download = `ebay_${safe}_${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>
