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
            <input
              v-model="form.email"
              type="email"
              class="input"
              :class="{ 'border-red-500 focus:ring-red-500': fieldError === 'email' }"
              placeholder="you@example.com"
              required
              autocomplete="email"
              @input="clearError"
            />
          </div>

          <div>
            <label class="block text-sm font-display text-zinc-400 mb-1.5">Password</label>
            <div class="relative">
              <input
                v-model="form.password"
                :type="showPassword ? 'text' : 'password'"
                class="input pr-11"
                :class="{ 'border-red-500 focus:ring-red-500': fieldError === 'password' }"
                placeholder="••••••••"
                required
                autocomplete="current-password"
                @input="clearError"
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

          <!-- Error Banner -->
          <Transition name="error-slide">
            <div
              v-if="error"
              class="flex items-start gap-3 text-sm rounded-xl px-4 py-3 border"
              :class="errorClass"
            >
              <!-- Icon: network -->
              <svg v-if="errorType === 'network'" class="w-4 h-4 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 5.636a9 9 0 010 12.728M15.536 8.464a5 5 0 010 7.072M6.343 6.343a9 9 0 000 12.728M9.172 9.172a5 5 0 000 7.071M12 12h.01"/>
              </svg>
              <!-- Icon: server -->
              <svg v-else-if="errorType === 'server'" class="w-4 h-4 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2"/>
              </svg>
              <!-- Icon: auth / default -->
              <svg v-else class="w-4 h-4 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>

              <div>
                <p class="font-medium leading-snug">{{ error }}</p>
                <p v-if="errorHint" class="mt-1 opacity-75">{{ errorHint }}</p>
              </div>
            </div>
          </Transition>

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
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'

const router = useRouter()

const form         = ref({ email: '', password: '' })
const loading      = ref(false)
const error        = ref('')
const errorHint    = ref('')
const errorType    = ref('')      // 'auth' | 'network' | 'server' | 'unknown'
const errorClass   = ref('')
const fieldError   = ref('')      // 'email' | 'password' — highlights the offending input
const showPassword = ref(false)

function clearError() {
  error.value      = ''
  errorHint.value  = ''
  errorType.value  = ''
  fieldError.value = ''
  errorClass.value = ''
}

function setError(type, message, hint = '', field = '') {
  errorType.value  = type
  error.value      = message
  errorHint.value  = hint
  fieldError.value = field
  errorClass.value = type === 'network' || type === 'server'
    ? 'text-amber-400 bg-amber-400/10 border-amber-400/20'
    : 'text-red-400 bg-red-400/10 border-red-400/20'
}

async function handleLogin() {
  loading.value = true
  clearError()

  try {
    const response = await api.post('/api/login', {
      email:    form.value.email,
      password: form.value.password,
    })

    localStorage.setItem('token', response.data.token)
    router.push('/dashboard')

  } catch (e) {
    const status    = e.response?.status
    const serverMsg = e.response?.data?.error || e.response?.data?.message || ''

    if (!e.response) {
      // No response = CORS block or network is down
      setError(
        'network',
        'Cannot reach the server.',
        'Check your internet connection or try again in a moment.'
      )
    } else if (status === 401) {
      setError(
        'auth',
        'Incorrect email or password.',
        'Double-check your credentials and try again.',
        'password'
      )
    } else if (status === 404) {
      setError(
        'auth',
        'No account found with that email.',
        'Check the address or sign up for a free account.',
        'email'
      )
    } else if (status === 429) {
      setError(
        'auth',
        'Too many login attempts.',
        'Please wait a few minutes before trying again.'
      )
    } else if (status >= 500) {
      setError(
        'server',
        'Server error — something went wrong on our end.',
        serverMsg || 'Please try again in a moment.'
      )
    } else {
      setError(
        'unknown',
        serverMsg || 'Login failed. Please try again.'
      )
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.error-slide-enter-active,
.error-slide-leave-active {
  transition: all 0.2s ease;
}
.error-slide-enter-from,
.error-slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>