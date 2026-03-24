<template>
  <div class="p-6 max-w-5xl mx-auto">
    <div class="mb-7">
      <h1 class="text-2xl font-display font-bold text-zinc-100">Search History</h1>
      <p class="text-zinc-500 text-sm mt-1">Your recent product searches</p>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="spinner w-8 h-8" />
    </div>

    <!-- History list -->
    <div v-else-if="history.length > 0" class="space-y-3">
      <div
        v-for="item in history"
        :key="item.id"
        class="card p-5 hover:border-zinc-700 transition-colors cursor-pointer"
        @click="expanded = expanded === item.id ? null : item.id"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 bg-brand-500/15 border border-brand-500/20 rounded-lg flex items-center justify-center">
              <svg class="w-4 h-4 text-brand-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
              </svg>
            </div>
            <div>
              <p class="font-display font-medium text-zinc-100">"{{ item.keyword }}"</p>
              <p class="text-xs text-zinc-500 mt-0.5">{{ formatDate(item.createdAt) }}</p>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <span class="badge bg-zinc-800 text-zinc-400 border border-zinc-700">
              {{ item.resultCount }} results
            </span>
            <svg
              class="w-4 h-4 text-zinc-500 transition-transform duration-200"
              :class="expanded === item.id ? 'rotate-180' : ''"
              fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
          </div>
        </div>

        <!-- Expanded results mini table -->
        <div v-if="expanded === item.id && item.parsedResults?.length" class="mt-4 table-container">
          <table class="table-base text-xs">
            <thead>
              <tr>
                <th>Title</th>
                <th>Country</th>
                <th>eBay</th>
                <th>Profit</th>
                <th>Links</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(p, i) in item.parsedResults.slice(0, 10)" :key="i">
                <td class="max-w-xs">
                  <p class="line-clamp-1 text-zinc-300">{{ p.title }}</p>
                </td>
                <td class="text-zinc-500">{{ p.country }}</td>
                <td class="font-mono text-zinc-300">${{ p.ebayPrice?.toFixed(2) }}</td>
                <td :class="(p.profit ?? 0) >= 0 ? 'profit-positive' : 'profit-negative'">
                  {{ (p.profit ?? 0) >= 0 ? '+' : '' }}${{ p.profit?.toFixed(2) }}
                </td>
                <td>
                  <div class="flex gap-1.5">
                    <a :href="p.ebayUrl" target="_blank" class="text-brand-400 hover:underline">eBay</a>
                    <span class="text-zinc-700">·</span>
                    <a :href="p.aliexpressUrl" target="_blank" class="text-orange-400 hover:underline">Ali</a>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else-if="expanded === item.id" class="mt-4 text-center text-zinc-600 text-sm py-4">
          No detailed results stored.
        </div>
      </div>
    </div>

    <!-- Empty -->
    <div v-else class="card p-12 text-center border-dashed">
      <div class="w-16 h-16 bg-zinc-800 rounded-2xl flex items-center justify-center mx-auto mb-4">
        <svg class="w-8 h-8 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>
        </svg>
      </div>
      <p class="font-display font-semibold text-zinc-300">No search history yet</p>
      <p class="text-zinc-500 text-sm mt-1">Your searches will appear here.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const history = ref([])
const loading = ref(true)
const expanded = ref(null)

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  })
}

onMounted(async () => {
  try {
    const res = await api.get('/user/history')
    history.value = (res.data ?? []).map(item => ({
      ...item,
      parsedResults: (() => {
        try { return JSON.parse(item.results ?? '[]') }
        catch { return [] }
      })()
    }))
  } catch {
    history.value = []
  } finally {
    loading.value = false
  }
})
</script>
