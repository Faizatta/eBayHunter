<template>
  <div class="main-layout">
    <Sidebar />
    <div class="page">
      <div class="page-header">
        <h1 class="page-title">Product Search</h1>
        <p class="page-subtitle">Find profitable dropshipping products from eBay &amp; AliExpress</p>
      </div>

      <!-- Search form -->
      <div class="card mb-4">
        <div class="flex gap-4" style="flex-wrap:wrap;">
          <div class="form-group" style="flex:2;min-width:200px;">
            <label class="form-label">Product Keyword</label>
            <input
              v-model="keyword"
              type="text"
              class="form-input"
              placeholder="e.g. wireless earbuds, phone case…"
              @keyup.enter="search"
            />
          </div>
          <div class="form-group" style="flex:1;min-width:160px;">
            <label class="form-label">Country</label>
            <select v-model="country" class="form-select">
              <option v-for="c in countries" :key="c.value" :value="c.value">{{ c.label }}</option>
            </select>
          </div>
          <div class="form-group" style="justify-content:flex-end;">
            <label class="form-label">&nbsp;</label>
            <button class="btn btn-primary btn-lg" @click="search" :disabled="loading || !keyword">
              <span v-if="loading" class="spinner"></span>
              {{ loading ? 'Scanning…' : '🔍 Search' }}
            </button>
          </div>
        </div>

        <div v-if="error" class="alert alert-error mt-3">{{ error }}</div>

        <div v-if="loading" class="loading-block mt-4">
          <div class="loading-steps">
            <div
              v-for="(step, i) in loadingSteps"
              :key="i"
              :class="['loading-step', { active: loadingStep === i, done: loadingStep > i }]"
            >
              <span class="step-icon">{{ loadingStep > i ? '✅' : loadingStep === i ? '⏳' : '○' }}</span>
              {{ step }}
            </div>
          </div>
        </div>
      </div>

      <!-- Results header + filters -->
      <div v-if="results.length > 0" class="results-header mb-4">
        <div class="flex items-center gap-3" style="flex-wrap:wrap;">
          <h2 class="font-semibold text-lg">{{ results.length }} Products Found</h2>
          <span class="badge badge-success">{{ country }}</span>
          <span class="text-muted text-sm">sorted by profit margin</span>
        </div>
        <div class="filter-row">
          <button
            v-for="f in filters"
            :key="f.key"
            :class="['filter-btn', { active: activeFilter === f.key }]"
            @click="activeFilter = f.key"
          >
            {{ f.label }}
          </button>
        </div>
      </div>

      <!-- Product cards -->
      <div v-if="filteredResults.length > 0" class="grid gap-4">
        <div
          v-for="(item, i) in filteredResults"
          :key="i"
          class="product-card"
          :class="{ 'card-highlight': item.analysis.profitMargin >= 50 }"
        >
          <!-- Card header -->
          <div class="card-top">
            <div class="product-title">{{ item.productName }}</div>
            <div class="card-badges">
              <span
                class="badge"
                :class="item.analysis.profitMargin >= 50 ? 'badge-success' : 'badge-primary'"
              >
                💰 {{ formatProfit(item) }} profit
              </span>
              <span
                class="badge"
                :class="item.analysis.profitMargin >= 50 ? 'badge-success' : item.analysis.profitMargin >= 30 ? 'badge-primary' : 'badge-warning'"
              >
                {{ item.analysis.profitMargin?.toFixed(1) }}% margin
              </span>
              <span
                class="badge comp-badge"
                :class="{
                  'comp-low':    item.ebay.competitionLevel === 'low',
                  'comp-medium': item.ebay.competitionLevel === 'medium',
                  'comp-high':   item.ebay.competitionLevel === 'high',
                }"
              >
                {{ compIcon(item.ebay.competitionLevel) }} {{ item.ebay.competitionLevel }} competition
              </span>
            </div>
          </div>

          <!-- Platform columns -->
          <div class="platform-grid">

            <!-- eBay column -->
            <div class="platform-box ebay-box">
              <div class="platform-header">
                <span class="platform-icon">🛒</span>
                <span class="platform-name">eBay</span>
                <span class="badge badge-warning" style="margin-left:auto;">Sold</span>
              </div>

              <div class="info-row">
                <span class="info-label">Sell Price</span>
                <span class="info-value font-bold">{{ formatCurrency(item.ebay.price, item.ebay.currency) }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">Weekly Sales</span>
                <span class="info-value">~{{ item.ebay.weeklySales }}/week</span>
              </div>
              <div class="info-row">
                <span class="info-label">Monthly Sold</span>
                <span class="info-value">{{ item.ebay.soldCount }} units</span>
              </div>
              <div class="info-row">
                <span class="info-label">Rating</span>
                <span class="info-value">⭐ {{ item.ebay.rating }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">Active Listings</span>
                <span class="info-value">{{ item.ebay.activeListings ?? '—' }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">Ship From</span>
                <span class="info-value">{{ item.ebay.shippingCountry }}</span>
              </div>

              <!-- Weekly breakdown mini chart -->
              <div v-if="item.ebay.weeklyBreakdown" class="weekly-chart mt-3">
                <div class="weekly-label">Weekly breakdown (last 4 weeks)</div>
                <div class="weekly-bars">
                  <div
                    v-for="(w, wi) in item.ebay.weeklyBreakdown"
                    :key="wi"
                    class="weekly-bar-wrap"
                  >
                    <div
                      class="weekly-bar"
                      :style="{ height: barHeight(w, item.ebay.weeklyBreakdown) + 'px' }"
                      :title="`Week ${wi + 1}: ${w} sold`"
                    ></div>
                    <div class="weekly-bar-label">{{ w }}</div>
                  </div>
                </div>
              </div>

              <a :href="item.ebay.productLink" target="_blank" class="btn btn-ghost btn-sm w-full mt-3">
                View on eBay ↗
              </a>
            </div>

            <!-- AliExpress column -->
            <div class="platform-box ali-box">
              <div class="platform-header">
                <span class="platform-icon">🏪</span>
                <span class="platform-name">AliExpress</span>
                <span class="badge badge-danger" style="margin-left:auto;">Source</span>
              </div>

              <div class="info-row">
                <span class="info-label">Source Price</span>
                <span class="info-value font-bold">${{ item.aliexpress.cost.toFixed(2) }} USD</span>
              </div>
              <div class="info-row">
                <span class="info-label">Shipping</span>
                <span class="info-value">
                  {{ item.aliexpress.shipping === 0 ? '🆓 Free' : '$' + item.aliexpress.shipping.toFixed(2) }}
                </span>
              </div>
              <div class="info-row">
                <span class="info-label">Delivery</span>
                <span class="info-value">📦 {{ item.aliexpress.deliveryTime }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">Supplier Rating</span>
                <span class="info-value">⭐ {{ item.aliexpress.rating }}</span>
              </div>
              <div v-if="item.aliexpress.isEstimated" class="info-row">
                <span class="info-label" style="color:var(--warning);">⚠ Price</span>
                <span class="info-value text-muted" style="font-size:11px;">Estimated — verify on AliExpress</span>
              </div>

              <!-- Matched title -->
              <div v-if="item.aliexpress.matchedTitle" class="ali-match-title mt-3">
                <div class="weekly-label">Matched listing</div>
                <div class="ali-title-text">{{ item.aliexpress.matchedTitle }}</div>
              </div>

              <a :href="item.aliexpress.productLink" target="_blank" class="btn btn-ghost btn-sm w-full mt-3">
                View on AliExpress ↗
              </a>
            </div>
          </div>

          <!-- Profit analysis bar -->
          <div class="analysis-bar mt-4">
            <div class="analysis-item">
              <span class="text-muted text-xs">Source Cost</span>
              <span class="font-semibold">${{ item.aliexpress.cost.toFixed(2) }}</span>
            </div>
            <div class="analysis-arrow">+</div>
            <div class="analysis-item">
              <span class="text-muted text-xs">eBay Fees ~16%</span>
              <span class="font-semibold">{{ formatCurrency((item.ebay.price * 0.16), item.ebay.currency) }}</span>
            </div>
            <div class="analysis-arrow">→</div>
            <div class="analysis-item">
              <span class="text-muted text-xs">Sell Price</span>
              <span class="font-semibold">{{ formatCurrency(item.ebay.price, item.ebay.currency) }}</span>
            </div>
            <div class="analysis-arrow">→</div>
            <div class="analysis-item">
              <span class="text-muted text-xs">Net Profit</span>
              <span
                class="font-bold"
                :class="item.analysis.profit > 0 ? 'text-success' : 'text-danger'"
              >
                {{ formatProfit(item) }}
              </span>
            </div>
            <div class="analysis-item method-pill">
              <span class="text-muted text-xs">Source</span>
              <span class="badge badge-primary" style="font-size:10px;">{{ item.analysis.fetchMethod }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- No results after filter -->
      <div v-else-if="results.length > 0 && filteredResults.length === 0" class="empty-state card">
        <div style="font-size:48px;margin-bottom:16px;">🔎</div>
        <div class="font-semibold text-lg">No products match this filter</div>
        <div class="text-muted mt-2">Try a different filter above.</div>
      </div>

      <!-- Empty state (no search yet or no results) -->
      <div v-else-if="searched && !loading" class="empty-state card">
        <div style="font-size:48px;margin-bottom:16px;">🔍</div>
        <div class="font-semibold text-lg">No profitable products found</div>
        <div class="text-muted mt-2">
          Try a different keyword or country, or lower thresholds in the Admin panel.
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

import api from '@/services/api'

const keyword     = ref('')
const country     = ref('UK')
const loading     = ref(false)
const error       = ref('')
const results     = ref([])
const searched    = ref(false)
const loadingStep = ref(0)
const activeFilter = ref('all')

const countries = [
  { value: 'UK',  label: '🇬🇧 United Kingdom' },
  { value: 'USA', label: '🇺🇸 United States' },
  { value: 'DE',  label: '🇩🇪 Germany' },
  { value: 'AU',  label: '🇦🇺 Australia' },
  { value: 'IT',  label: '🇮🇹 Italy' },
  { value: 'ALL', label: '🌍 All Markets' },
]

const loadingSteps = [
  'Searching eBay sold listings…',
  'Checking competition levels…',
  'Matching AliExpress products…',
  'Calculating profit margins…',
  'Filtering results…',
]

const filters = [
  { key: 'all',    label: 'All' },
  { key: 'low',    label: '🟢 Low Competition' },
  { key: 'profit', label: '💰 High Profit (50%+)' },
  { key: 'weekly', label: '📈 20+ / Week' },
]

// Currency symbols
const currencySymbols = { GBP: '£', USD: '$', EUR: '€', AUD: 'A$' }

function formatCurrency(val, currency = 'GBP') {
  if (val == null) return '—'
  const sym = currencySymbols[currency] || currency + ' '
  return sym + Number(val).toFixed(2)
}

function formatProfit(item) {
  const profit = item.analysis?.profit ?? 0
  const currency = item.ebay?.currency ?? 'GBP'
  const sym = currencySymbols[currency] || currency + ' '
  return sym + Math.abs(profit).toFixed(2)
}

function compIcon(level) {
  return level === 'low' ? '🟢' : level === 'medium' ? '🟡' : '🔴'
}

function barHeight(val, breakdown) {
  const max = Math.max(...breakdown, 1)
  return Math.max(4, Math.round((val / max) * 40))
}

const filteredResults = computed(() => {
  if (activeFilter.value === 'all')    return results.value
  if (activeFilter.value === 'low')    return results.value.filter(r => r.ebay?.competitionLevel === 'low')
  if (activeFilter.value === 'profit') return results.value.filter(r => (r.analysis?.profitMargin ?? 0) >= 50)
  if (activeFilter.value === 'weekly') return results.value.filter(r => (r.ebay?.weeklySales ?? 0) >= 20)
  return results.value
})

let stepTimer = null

function startLoadingAnimation() {
  loadingStep.value = 0
  clearInterval(stepTimer)
  stepTimer = setInterval(() => {
    if (loadingStep.value < loadingSteps.length - 1) {
      loadingStep.value++
    } else {
      clearInterval(stepTimer)
    }
  }, 8000) // step every 8s — bot takes ~40s total
}

function stopLoadingAnimation() {
  clearInterval(stepTimer)
}

async function search() {
  if (!keyword.value.trim()) return
  error.value   = ''
  loading.value = true
  searched.value = false
  results.value  = []
  activeFilter.value = 'all'

  startLoadingAnimation()

  try {
    const { data } = await api.post('/product/search', {
      keyword: keyword.value.trim(),
      country: country.value,
    })
    // Sort by profitMargin descending (bot already sorts, but ensure it here too)
    results.value = (Array.isArray(data) ? data : []).sort(
      (a, b) => (b.analysis?.profitMargin ?? 0) - (a.analysis?.profitMargin ?? 0)
    )
    searched.value = true
  } catch (e) {
    const msg = e.response?.data?.error || e.message || 'Search failed. Please try again.'
    error.value = msg
    if (e.response?.status === 429) {
      error.value = msg + ' Go to your profile or contact admin.'
    }
  } finally {
    loading.value = false
    stopLoadingAnimation()
  }
}
</script>

<style scoped>
/* Platform columns */
.platform-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 16px;
}

@media (max-width: 640px) {
  .platform-grid { grid-template-columns: 1fr; }
}

.platform-box {
  border-radius: 10px;
  padding: 16px;
  border: 1.5px solid var(--border);
}

.ebay-box {
  border-color: #fbbf24;
  background: #fffbeb;
}

.ali-box {
  border-color: #f87171;
  background: #fff5f5;
}

.platform-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-weight: 600;
  font-size: 14px;
}

.platform-icon { font-size: 18px; }

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 5px 0;
  border-bottom: 1px solid rgba(0,0,0,.05);
  font-size: 13px;
}

.info-row:last-of-type { border-bottom: none; }
.info-label { color: var(--text-muted); }
.info-value { font-weight: 500; }

/* Weekly chart */
.weekly-chart { border-top: 1px solid rgba(0,0,0,.06); padding-top: 10px; }
.weekly-label { font-size: 11px; color: var(--text-muted); margin-bottom: 6px; }

.weekly-bars {
  display: flex;
  gap: 6px;
  align-items: flex-end;
  height: 52px;
}

.weekly-bar-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  flex: 1;
}

.weekly-bar {
  width: 100%;
  background: #fbbf24;
  border-radius: 3px 3px 0 0;
  min-height: 4px;
  transition: height 0.3s;
}

.ali-box .weekly-bar { background: #f87171; }

.weekly-bar-label {
  font-size: 10px;
  color: var(--text-muted);
}

/* AliExpress matched title */
.ali-match-title { border-top: 1px solid rgba(0,0,0,.06); padding-top: 10px; }
.ali-title-text {
  font-size: 12px;
  color: var(--text-muted);
  font-style: italic;
  line-height: 1.4;
  margin-top: 4px;
}

/* Card top */
.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}

.product-title {
  font-size: 15px;
  font-weight: 600;
  flex: 1;
  min-width: 200px;
  line-height: 1.4;
}

.card-badges {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

/* Competition badge colors */
.comp-low    { background: #d1fae5 !important; color: #065f46 !important; }
.comp-medium { background: #fef3c7 !important; color: #92400e !important; }
.comp-high   { background: #fee2e2 !important; color: #991b1b !important; }

/* Profit analysis bar */
.analysis-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--bg);
  border-radius: 8px;
  flex-wrap: wrap;
}

.analysis-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
}

.analysis-arrow {
  color: var(--text-muted);
  font-size: 16px;
  flex-shrink: 0;
}

.method-pill { margin-left: auto; }

/* Highlight card */
.card-highlight {
  border-color: var(--success) !important;
  box-shadow: 0 0 0 1px rgba(var(--success-rgb, 16, 185, 129), 0.15);
}

/* Filter row */
.results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}

.filter-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.filter-btn {
  padding: 6px 14px;
  border-radius: 20px;
  border: 1px solid var(--border);
  background: transparent;
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  color: var(--text-muted);
  transition: all .15s;
}

.filter-btn:hover { background: var(--bg); color: var(--text); }
.filter-btn.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

/* Loading steps */
.loading-block {
  background: var(--bg);
  border-radius: 8px;
  padding: 16px;
}

.loading-steps {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.loading-step {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--text-muted);
  transition: color .3s;
}

.loading-step.active { color: var(--text); font-weight: 500; }
.loading-step.done   { color: var(--success); }

.step-icon { font-size: 16px; width: 20px; text-align: center; }

/* Empty state */
.empty-state {
  text-align: center;
  padding: 60px 40px;
}

.text-success { color: var(--success); }
.text-danger  { color: var(--danger, #ef4444); }
</style>
