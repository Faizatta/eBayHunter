<template>
  <div class="min-h-screen flex items-center justify-center px-4 py-12">
    <!-- Background blobs -->
    <div class="fixed inset-0 pointer-events-none overflow-hidden">
      <div class="absolute -top-40 -right-40 w-96 h-96 bg-brand-500/10 rounded-full blur-3xl" />
      <div class="absolute -bottom-40 -left-40 w-96 h-96 bg-brand-600/8 rounded-full blur-3xl" />
    </div>

    <div class="w-full max-w-md animate-fadein">
      <!-- Header -->
      <div class="text-center mb-8">
        <div class="inline-flex items-center justify-center w-14 h-14 bg-brand-500 rounded-2xl mb-4 pulse-glow">
          <svg class="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
        </div>
        <h1 class="text-3xl font-display font-bold text-zinc-100">eBayHunter</h1>
        <p class="mt-1 text-zinc-500 font-body">Sign in to your account</p>
      </div>

      <!-- Card -->
      <div class="card p-8">
        <form @submit.prevent="handleLogin" class="space-y-5">
          <div>
            <label class="block text-sm font-display text-zinc-400 mb-1.5">Email address</label>
            <input v-model="form.email" type="email" class="input" placeholder="you@example.com" required autocomplete="email" />
          </div>

          <div>
            <label class="block text-sm font-display text-zinc-400 mb-1.5">Password</label>
            <div class="relative">
              <input
                v-model="form.password"
                :type="showPassword ? 'text' : 'password'"
                class="input pr-11"
                placeholder="••••••••"
                required
                autocomplete="current-password"
              />
              <button type="button" @click="showPassword = !showPassword"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 transition-colors">
                <svg v-if="!showPassword" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                </svg>
                <svg v-else class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"/>
                </svg>
              </button>
            </div>
          </div>

          <!-- Error -->
          <div v-if="error" class="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-xl px-4 py-3">
            <svg class="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            {{ error }}
          </div>

          <button type="submit" class="btn-primary w-full justify-center" :disabled="loading">
            <div v-if="loading" class="spinner w-4 h-4" />
            <span>{{ loading ? 'Signing in…' : 'Sign In' }}</span>
          </button>
        </form>

        <p class="mt-5 text-center text-sm text-zinc-500 font-body">
          Don't have an account?
          <router-link to="/register" class="text-brand-400 hover:text-brand-300 font-medium transition-colors">Sign up free</router-link>
        </p>
      </div>

      <!-- Plan preview -->
      <!-- <div class="mt-6 grid grid-cols-3 gap-3 text-center">
        <div v-for="plan in plans" :key="plan.name" class="card px-3 py-3">
          <p class="font-display font-bold text-zinc-100 text-sm">{{ plan.name }}</p>
          <p class="text-xs text-zinc-500 mt-0.5">{{ plan.limit }} searches/day</p>
        </div>
      </div> -->
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth   = useAuthStore()

const form         = ref({ email: '', password: '' })
const loading      = ref(false)
const error        = ref('')
const showPassword = ref(false)

const plans = [
  { name: 'Free',  limit: 5   },
  { name: 'Basic', limit: 20  },
  { name: 'Pro',   limit: 100 },
]

async function handleLogin() {
  loading.value = true
  error.value   = ''
  try {
    await auth.login(form.value.email, form.value.password)
    router.push('/dashboard')
  } catch (e) {
    error.value = e.response?.data?.error ?? 'Login failed. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>
