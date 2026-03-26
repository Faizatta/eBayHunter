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
      <p class="text-zinc-500 text-sm mt-1">Find profitable eBay products with AliExpress sourcing — v9 strict rules</p>
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

    <!-- v9 rules notice -->
    <div class="card p-3 mb-4 border border-brand-500/20 bg-brand-500/5 flex items-start gap-2.5">
      <svg class="w-4 h-4 text-brand-400 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/>
      </svg>
      <p class="text-xs text-zinc-400 font-display leading-relaxed">
        <span class="text-brand-300 font-semibold">v9 Strict Rules:</span>
        SOLD listings only (last 30 days) · Each week ≥ 10 sales (not just avg) · Reviews 4★+ on both platforms ·
        <span class="text-emerald-300 font-semibold">China ship-from = ALWAYS rejected</span> ·
        35%+ title word overlap · Profit = Sold Price − Ali Price − Shipping Cost · Max 500 active listings
      </p>
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
            <option value="margin">Margin ↓</option>
            <option value="price">eBay Sold ↑</option>
            <option value="sold">Sales/wk ↓</option>
            <option value="aliReviews">Ali Reviews ↓</option>
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
        <span class="text-xs px-3 py-1.5 rounded-full bg-zinc-800 border border-zinc-700 text-zinc-400 font-display">
          Avg margin: <span class="text-brand-400 font-semibold ml-1">{{ avgMargin }}</span>
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
        <span class="text-xs px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-display">
          ✅ Country matched: <span class="font-semibold ml-1">{{ matchedCount }}/{{ sortedResults.length }}</span>
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
              <!-- Pricing group -->
              <th>
                <span class="flex items-center gap-1">
                  eBay Sold
                  <span class="text-zinc-600 font-normal text-xs">(avg)</span>
                </span>
              </th>
              <th>eBay Listed</th>
              <th>eBay Lowest</th>
              <th>Ali Price</th>
              <th>Ali Ship</th>
              <!-- Profit -->
              <th>
                <span class="flex items-center gap-1">
                  Profit
                  <span class="text-zinc-600 font-normal text-xs">(sold−ali−ship)</span>
                </span>
              </th>
              <th>Margin</th>
              <!-- Sales -->
              <th>Sales/wk</th>
              <th>Weekly</th>
              <th>30d Total</th>
              <!-- Ratings -->
              <th>eBay ★</th>
              <th>Ali ★</th>
              <th>Ali Reviews</th>
              <!-- Logistics -->
              <th>Ali Ships From</th>
              <th>🌍 Match</th>
              <th>Delivery</th>
              <th>Free Ship</th>
              <!-- Competition -->
              <th>Competition</th>
              <th>Active Listings</th>
              <!-- Why good -->
              <th>Why Good</th>
              <!-- Links -->
              <th>Links</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(p, i) in sortedResults" :key="i">

              <td class="text-zinc-600 text-xs font-mono">{{ i + 1 }}</td>

              <!-- Product title + delivery hint -->
              <td class="max-w-xs">
                <p class="text-zinc-200 font-medium text-sm line-clamp-2 leading-snug">{{ p.title || '—' }}</p>
              </td>

              <!-- Country + local shipping flag -->
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

              <!-- eBay Sold Price (used in profit formula) -->
              <td>
                <span class="font-mono text-blue-300 text-sm whitespace-nowrap font-semibold">
                  {{ currencySymbol(p.currency) }}{{ fmt(p.ebaySoldPrice) }}
                </span>
              </td>

              <!-- eBay Listed Price (current listing price) -->
              <td>
                <span class="font-mono text-zinc-400 text-sm whitespace-nowrap">
                  {{ currencySymbol(p.currency) }}{{ fmt(p.ebayPrice) }}
                </span>
              </td>

              <!-- eBay Lowest Active Price -->
              <td>
                <span class="font-mono text-zinc-400 text-sm whitespace-nowrap">
                  {{ currencySymbol(p.currency) }}{{ fmt(p.ebayLowestPrice) }}
                </span>
              </td>

              <!-- AliExpress Price -->
              <td>
                <span class="font-mono text-zinc-300 text-sm whitespace-nowrap">
                  {{ currencySymbol(p.currency) }}{{ fmt(p.aliexpressPrice) }}
                </span>
              </td>

              <!-- AliExpress Shipping Cost -->
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

              <!-- PROFIT = ebaySoldPrice − aliexpressPrice − aliShippingCost -->
              <td>
                <span :class="p.profit >= PREFERRED_MIN_PROFIT ? 'profit-positive' : p.profit > 0 ? 'text-amber-400 font-mono font-semibold' : 'profit-negative'"
                  class="whitespace-nowrap text-sm">
                  {{ p.profit >= 0 ? '+' : '' }}{{ currencySymbol(p.currency) }}{{ fmt(p.profit) }}
                </span>
                <!-- Formula breakdown -->
                <div class="text-xs text-zinc-600 font-mono mt-0.5 leading-tight whitespace-nowrap">
                  {{ fmt(p.ebaySoldPrice) }}−{{ fmt(p.aliexpressPrice) }}−{{ fmt(p.aliShippingCost) }}
                </div>
              </td>

              <!-- Margin % -->
              <td>
                <span class="text-xs font-mono font-semibold"
                  :class="p.profitMarginPct >= 20 ? 'text-emerald-400' : p.profitMarginPct > 0 ? 'text-amber-400' : 'text-red-400'">
                  {{ fmt(p.profitMarginPct, 1) }}%
                </span>
              </td>

              <!-- Sales / week (avg from bot weekly logic) -->
              <td>
                <span class="text-emerald-400 font-mono text-sm font-medium">{{ p.soldPerWeek }}</span>
                <span class="text-zinc-600 text-xs font-display">/wk</span>
              </td>

              <!-- Weekly mini-bar chart (weeklyBreakdown array → "w0/w1/w2/w3") -->
              <td>
                <div v-if="weekBars(p).length" class="flex items-end gap-1 h-6">
                  <div v-for="(w, wi) in weekBars(p)" :key="wi"
                    class="w-2.5 rounded-sm bg-brand-500/60 min-h-[3px]"
                    :style="{ height: barHeight(w, weekBars(p)) }"
                    :title="`Week ${wi + 1}: ${w} sold`" />
                </div>
                <span v-else class="text-zinc-700 text-xs">—</span>
              </td>

              <!-- Total sold in 30d -->
              <td>
                <span class="font-mono text-zinc-400 text-sm">{{ p.totalSoldMonth }}</span>
                <span class="text-zinc-600 text-xs font-display">/30d</span>
              </td>

              <!-- eBay seller rating -->
              <td>
                <span v-if="p.ebayRating > 0" class="flex items-center gap-1 text-amber-400 text-sm font-mono">
                  ★ {{ fmt(p.ebayRating, 1) }}
                </span>
                <span v-else class="text-zinc-700 text-xs">—</span>
              </td>

              <!-- AliExpress rating -->
              <td>
                <span v-if="p.aliRating > 0" class="flex items-center gap-1 text-amber-400 text-sm font-mono">
                  ★ {{ fmt(p.aliRating, 1) }}
                </span>
                <span v-else class="text-zinc-700 text-xs">—</span>
              </td>

              <!-- AliExpress review count -->
              <td>
                <span v-if="p.aliReviews > 0"
                  :class="p.aliReviews >= 50 ? 'text-emerald-400' : p.aliReviews >= 4 ? 'text-zinc-400' : 'text-amber-400'"
                  class="text-sm font-mono">
                  {{ p.aliReviews }}
                </span>
                <span v-else class="text-zinc-700 text-xs">—</span>
              </td>

              <!-- AliExpress Ship-From Country (must match eBay country) -->
              <td>
                <span class="text-xs font-display whitespace-nowrap"
                  :class="isChina(p.aliShipCountry) ? 'text-red-400' : 'text-zinc-300'">
                  {{ p.aliShipCountry || '—' }}
                </span>
              </td>

              <!-- Country Match Badge (STRICT v9 — China always rejected) -->
              <td>
                <span v-if="p.countryMatch"
                  class="flex items-center gap-1 text-emerald-400 text-xs font-display font-semibold whitespace-nowrap bg-emerald-500/10 border border-emerald-500/20 px-2 py-1 rounded-full">
                  <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                  </svg>
                  Match
                </span>
                <span v-else
                  class="flex items-center gap-1 text-red-400 text-xs font-display font-semibold whitespace-nowrap bg-red-500/10 border border-red-500/20 px-2 py-1 rounded-full">
                  ✗ Mismatch
                </span>
              </td>

              <!-- Delivery window -->
              <td>
                <span class="text-xs text-zinc-400 font-display whitespace-nowrap">
                  {{ p.deliveryDays || '—' }}
                </span>
              </td>

              <!-- Free shipping flag -->
              <td>
                <span v-if="p.freeShipping"
                  class="text-xs text-emerald-400 font-display flex items-center gap-1 whitespace-nowrap">
                  <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                  </svg>
                  Free
                </span>
                <span v-else class="text-zinc-600 text-xs font-display">Paid</span>
              </td>

              <!-- Competition level -->
              <td>
                <span :class="compBadgeClass(p.competitionLevel)"
                  class="text-xs font-display font-semibold px-2.5 py-1 rounded-full whitespace-nowrap">
                  {{ compIcon(p.competitionLevel) }} {{ p.competitionLevel }}
                </span>
              </td>

              <!-- Active listing count -->
              <td>
                <span :class="p.activeListings > 500 ? 'text-red-400' : p.activeListings > 200 ? 'text-amber-400' : 'text-zinc-400'"
                  class="text-sm font-mono">
                  {{ p.activeListings }}
                </span>
              </td>

              <!-- whyGoodProduct (from bot) -->
              <td class="max-w-[180px]">
                <p class="text-xs text-zinc-400 line-clamp-2 leading-snug">{{ p.whyGoodProduct || '—' }}</p>
              </td>

              <!-- Links: 4 possible URLs from bot -->
              <td>
                <div class="flex flex-col gap-1.5">
                  <!-- Prefer direct item URL, fall back to filtered search URL -->
                  <a :href="p.ebayItemUrl || p.ebayUrl" target="_blank" rel="noopener noreferrer"
                    :title="p.ebayItemUrl ? 'Direct eBay item' : 'eBay SOLD search (filtered)'"
                    class="text-xs bg-zinc-800 hover:bg-brand-500/20 hover:text-brand-400 border border-zinc-700 hover:border-brand-500/30 text-zinc-300 px-2.5 py-1 rounded-lg transition-all font-display text-center flex items-center justify-center gap-1">
                    eBay
                    <span v-if="p.ebayItemUrl" class="text-brand-500 text-xs">•</span>
                    <span v-else class="text-zinc-600 text-xs">↗</span>
                  </a>
                  <a :href="p.aliItemUrl || p.aliexpressUrl" target="_blank" rel="noopener noreferrer"
                    :title="p.aliItemUrl ? 'Direct AliExpress item' : 'AliExpress local ship search (filtered)'"
                    class="text-xs bg-zinc-800 hover:bg-orange-500/20 hover:text-orange-400 border border-zinc-700 hover:border-orange-500/30 text-zinc-300 px-2.5 py-1 rounded-lg transition-all font-display text-center flex items-center justify-center gap-1">
                    Ali
                    <span v-if="p.aliItemUrl" class="text-orange-500 text-xs">•</span>
                    <span v-else class="text-zinc-600 text-xs">↗</span>
                  </a>
                </div>
                <!-- Dot legend: filled dot = direct item link, ↗ = filtered search -->
                <p class="text-zinc-700 text-xs mt-1 text-center">{{ p.ebayItemUrl || p.aliItemUrl ? '• = item' : '' }}</p>
              </td>

            </tr>
          </tbody>
        </table>

        <div class="px-6 py-3 border-t border-zinc-800 text-xs text-zinc-500 font-display">
          Showing {{ sortedResults.length }} of {{ results.length }} products ·
          SOLD listings only · each week ≥ 10 sales · 4★+ · no China shipping · country match verified
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
        v9 strict rules rejected all candidates — try a different keyword.<br/>
        Common reasons: China-only AliExpress supplier, weekly sales out of 10–50 range, title mismatch, or profit ≤ 0.
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
        Searches eBay SOLD listings across 4 countries — returns only products with matching eBay + AliExpress ship-from country (China always rejected).
      </p>
    </div>

  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const auth = useAuthStore()

// ── Constants mirrored from bot config ────────────────────────────
const PREFERRED_MIN_PROFIT = 5.0
const CHINA_SIGNALS = ['cn', 'china', 'zh', 'shenzhen', 'guangzhou', 'hangzhou',
                       'yiwu', 'beijing', 'shanghai', 'hong kong', 'tw', 'taiwan']

// ── State ─────────────────────────────────────────────────────────
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

// ── Helpers ───────────────────────────────────────────────────────
function fmt(val, decimals = 2) {
  const n = parseFloat(val)
  return isNaN(n) ? (0).toFixed(decimals) : n.toFixed(decimals)
}

function currencySymbol(currency) {
  const map = { GBP: '£', EUR: '€', AUD: 'A$', USD: '$' }
  return map[currency] ?? (currency ? currency + ' ' : '')
}

function isChina(shipCountry) {
  if (!shipCountry) return false
  const s = shipCountry.toLowerCase()
  return CHINA_SIGNALS.some(sig => s.includes(sig))
}

// ── Weekly bars — bot sends weeklyBreakdown as list OR
//    weeklyConsistency as "12/15/10/8" string ───────────────────────
function weekBars(p) {
  // Prefer the actual weeklyBreakdown array the bot sends
  if (Array.isArray(p.weeklyBreakdown) && p.weeklyBreakdown.length) {
    return p.weeklyBreakdown.map(Number)
  }
  // Fall back to weeklyConsistency string "12/15/10/8"
  if (p.weeklyConsistency) {
    return p.weeklyConsistency.split('/').map(s => parseInt(s.trim()) || 0)
  }
  return []
}

function barHeight(w, weeks) {
  const mx = Math.max(...weeks, 1)
  return Math.max(3, Math.round((w / mx) * 24)) + 'px'
}

// ── Competition badge ─────────────────────────────────────────────
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

// ── Normalise — maps ALL ProductResult fields (v9 dataclass) ─────
//    Handles both snake_case (Python JSON default) and camelCase.
function normalise(p) {
  // Core prices
  const ebayPrice       = parseFloat(p.ebayPrice       ?? p.EbayPrice)       || 0
  const ebayLowestPrice = parseFloat(p.ebayLowestPrice ?? p.EbayLowestPrice) || 0
  const ebaySoldPrice   = parseFloat(p.ebaySoldPrice   ?? p.EbaySoldPrice)   || 0
  const aliPrice        = parseFloat(p.aliexpressPrice ?? p.AliexpressPrice)  || 0
  const aliShip         = parseFloat(p.aliShippingCost ?? p.AliShippingCost)  || 0

  // Profit: use bot value, recompute as fallback
  const profit = parseFloat(p.profit ?? p.Profit)
                 ?? parseFloat((ebaySoldPrice - aliPrice - aliShip).toFixed(2))
  const margin = parseFloat(p.profitMarginPct ?? p.ProfitMarginPct)
                 ?? (ebaySoldPrice > 0 ? parseFloat(((profit / ebaySoldPrice) * 100).toFixed(1)) : 0)

  // Weekly breakdown: bot sends list in weeklyBreakdown field
  const weeklyBreakdown = p.weeklyBreakdown ?? p.WeeklyBreakdown ?? []

  // Weekly consistency: "w0/w1/w2/w3" string (legacy or summary)
  const weeklyConsistency = p.weeklyConsistency ?? p.WeeklyConsistency ?? ''

  return {
    // Identity
    title:             p.title             ?? p.Title             ?? '',
    country:           p.country           ?? p.Country           ?? '',
    currency:          p.currency          ?? p.Currency          ?? 'GBP',

    // eBay prices (3 distinct values from bot)
    ebayPrice,
    ebayLowestPrice,
    ebaySoldPrice,
    ebayRating:        parseFloat(p.ebayRating    ?? p.EbayRating)    || 0,

    // AliExpress prices
    aliexpressPrice:   aliPrice,
    aliShippingCost:   aliShip,
    aliRating:         parseFloat(p.aliRating     ?? p.AliRating)     || 0,
    aliReviews:        parseInt  (p.aliReviews    ?? p.AliReviews)    || 0,
    aliShipCountry:    p.aliShipCountry    ?? p.AliShipCountry    ?? '',

    // Profit
    profit:            isNaN(profit) ? 0 : profit,
    profitMarginPct:   isNaN(margin) ? 0 : margin,

    // Sales data (from bot's validate_weekly_sales + get_current_month_sales)
    soldPerWeek:       parseInt(p.soldPerWeek    ?? p.SoldPerWeek)    || 0,
    weeklyBreakdown,          // list [w0, w1, w2, w3] — direct from bot
    totalSoldMonth:    parseInt(p.totalSoldMonth ?? p.TotalSoldMonth) || 0,
    weeklyConsistency,        // "12/15/10/8" string fallback

    // Competition
    competitionLevel:  p.competitionLevel  ?? p.CompetitionLevel  ?? 'medium',
    activeListings:    parseInt(p.activeListings ?? p.ActiveListings) || 0,

    // Logistics flags
    freeShipping:      p.freeShipping  ?? p.FreeShipping  ?? false,
    localShipping:     p.localShipping ?? p.LocalShipping ?? false,
    countryMatch:      p.countryMatch  ?? p.CountryMatch  ?? false,
    deliveryDays:      p.deliveryDays  ?? p.DeliveryDays  ?? '',

    // URLs — v9 sends 4 distinct URL fields
    ebayUrl:          p.ebayUrl      ?? p.EbayUrl      ?? '#',  // filtered SOLD search
    aliexpressUrl:    p.aliexpressUrl ?? p.AliexpressUrl ?? '#', // filtered Ali search
    ebayItemUrl:      p.ebayItemUrl  ?? p.EbayItemUrl  ?? '',   // direct item (if found)
    aliItemUrl:       p.aliItemUrl   ?? p.AliItemUrl   ?? '',   // direct Ali item (if found)

    // Bot reasoning fields
    whyGoodProduct:   p.whyGoodProduct  ?? p.WhyGoodProduct  ?? '',
    rejectionReason:  p.rejectionReason ?? p.RejectionReason ?? '', // not shown in table (rejected items filtered out)
  }
}

// ── Summary stats ─────────────────────────────────────────────────
const avgProfit = computed(() => {
  const r = sortedResults.value
  if (!r.length) return '—'
  const avg = r.reduce((s, p) => s + p.profit, 0) / r.length
  const sym = currencySymbol(r[0]?.currency)
  return (avg >= 0 ? '+' : '') + sym + avg.toFixed(2)
})
const avgMargin = computed(() => {
  const r = sortedResults.value
  if (!r.length) return '—'
  return (r.reduce((s, p) => s + (p.profitMarginPct || 0), 0) / r.length).toFixed(1) + '%'
})
const avgSales = computed(() => {
  const r = sortedResults.value
  if (!r.length) return '—'
  return Math.round(r.reduce((s, p) => s + p.soldPerWeek, 0) / r.length) + '/wk'
})
const lowCompCount  = computed(() => sortedResults.value.filter(p => p.competitionLevel === 'low').length)
const medCompCount  = computed(() => sortedResults.value.filter(p => p.competitionLevel === 'medium').length)
const highCompCount = computed(() => sortedResults.value.filter(p => p.competitionLevel === 'high').length)
const matchedCount  = computed(() => sortedResults.value.filter(p => p.countryMatch).length)

const resultCountries = computed(() =>
  [...new Set(results.value.map(p => p.country))].sort()
)

// ── Filtered + sorted results ─────────────────────────────────────
const sortedResults = computed(() => {
  let r = [...results.value]
  if (filterCountry.value) r = r.filter(p => p.country === filterCountry.value)
  if (filterComp.value)    r = r.filter(p => p.competitionLevel === filterComp.value)
  if (sortBy.value === 'profit')     r.sort((a, b) => b.profit - a.profit)
  if (sortBy.value === 'margin')     r.sort((a, b) => (b.profitMarginPct || 0) - (a.profitMarginPct || 0))
  if (sortBy.value === 'price')      r.sort((a, b) => a.ebaySoldPrice - b.ebaySoldPrice)
  if (sortBy.value === 'sold')       r.sort((a, b) => b.soldPerWeek - a.soldPerWeek)
  if (sortBy.value === 'aliReviews') r.sort((a, b) => b.aliReviews - a.aliReviews)
  return r
})

// ── Country animation ─────────────────────────────────────────────
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

// ── Run search ────────────────────────────────────────────────────
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

// ── CSV export — all v9 ProductResult fields ──────────────────────
function exportCSV() {
  const data = sortedResults.value
  if (!data.length) return

  const headers = [
    '#', 'Title', 'Country', 'Currency',
    'eBay Listed', 'eBay Lowest', 'eBay Sold (Avg)', 'eBay Rating',
    'Ali Price', 'Ali Shipping', 'Ali Rating', 'Ali Reviews',
    'Ali Ships From', 'Country Match',
    'PROFIT', 'MARGIN %',
    'Sales/Week', 'Total (30d)', 'Weekly Breakdown', 'Weekly Consistency',
    'Competition', 'Active Listings',
    'Free Shipping', 'Local Shipping', 'Delivery',
    'eBay Search URL', 'eBay Item URL',
    'Ali Search URL',  'Ali Item URL',
    'Why Good Product',
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
    fmt(p.ebayPrice),
    fmt(p.ebayLowestPrice),
    fmt(p.ebaySoldPrice),
    fmt(p.ebayRating, 1),
    fmt(p.aliexpressPrice),
    fmt(p.aliShippingCost),
    p.aliRating > 0 ? fmt(p.aliRating, 1) : '',
    p.aliReviews,
    p.aliShipCountry,
    p.countryMatch ? 'YES' : 'NO',
    fmt(p.profit),
    fmt(p.profitMarginPct, 1) + '%',
    p.soldPerWeek,
    p.totalSoldMonth,
    Array.isArray(p.weeklyBreakdown) ? p.weeklyBreakdown.join('/') : '',
    p.weeklyConsistency,
    p.competitionLevel,
    p.activeListings,
    p.freeShipping  ? 'Yes' : 'No',
    p.localShipping ? 'Yes' : 'No',
    p.deliveryDays,
    p.ebayUrl,
    p.ebayItemUrl,
    p.aliexpressUrl,
    p.aliItemUrl,
    p.whyGoodProduct,
  ].map(escape).join(','))

  const csv  = [headers.join(','), ...rows].join('\n')
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  const safe = lastKeyword.value.replace(/[^a-z0-9]/gi, '_').toLowerCase()
  a.href     = url
  a.download = `ebay_v9_${safe}_${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>
