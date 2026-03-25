<template>
  <div class="min-h-screen flex items-center justify-center px-4 py-12">
    <div class="fixed inset-0 pointer-events-none overflow-hidden">
      <div class="absolute -top-40 -right-40 w-96 h-96 bg-brand-500/10 rounded-full blur-3xl" />
    </div>

    <div class="w-full max-w-md animate-fadein">
      <div class="text-center mb-8">
        <div class="inline-flex items-center justify-center w-14 h-14 bg-brand-500 rounded-2xl mb-4">
          <svg class="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
        </div>
        <h1 class="text-3xl font-display font-bold text-zinc-100">Create Account</h1>
        <p class="mt-1 text-zinc-500">Start with 5 free searches per day</p>
      </div>

      <div class="card p-8">
        <form @submit.prevent="handleRegister" class="space-y-5">
          <div>
            <label class="block text-sm font-display text-zinc-400 mb-1.5">Email address</label>
            <input v-model="form.email" type="email" class="input" placeholder="you@example.com" required />
          </div>

          <div>
            <label class="block text-sm font-display text-zinc-400 mb-1.5">Password</label>
            <input v-model="form.password" type="password" class="input" placeholder="Min. 6 characters" required minlength="6" />
          </div>

          <div>
            <label class="block text-sm font-display text-zinc-400 mb-1.5">Confirm password</label>
            <input v-model="form.confirm" type="password" class="input" placeholder="Re-enter password" required />
          </div>

          <div v-if="error" class="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-xl px-4 py-3">
            <svg class="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            {{ error }}
          </div>

          <button type="submit" class="btn-primary w-full justify-center" :disabled="loading">
            <div v-if="loading" class="spinner w-4 h-4" />
            {{ loading ? 'Creating account…' : 'Create Account' }}
          </button>
        </form>

        <p class="mt-5 text-center text-sm text-zinc-500">
          Already have an account?
          <router-link to="/login" class="text-brand-400 hover:text-brand-300 font-medium transition-colors">Sign in</router-link>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth   = useAuthStore()

const form    = ref({ email: '', password: '', confirm: '' })
const loading = ref(false)
const error   = ref('')

async function handleRegister() {
  error.value = ''
  if (form.value.password !== form.value.confirm) {
    error.value = 'Passwords do not match.'
    return
  }
  loading.value = true
  try {
    await auth.register(form.value.email, form.value.password)
    router.push('/dashboard')
  } catch (e) {
    error.value = e.response?.data?.error ?? 'Registration failed. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>
