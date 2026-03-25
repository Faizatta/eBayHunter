import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/',        redirect: '/dashboard' },
  { path: '/login',   component: () => import('../views/LoginView.vue'),     meta: { guest: true } },
  { path: '/register',component: () => import('../views/RegisterView.vue'),  meta: { guest: true } },
  {
    path: '/dashboard',
    component: () => import('../views/DashboardView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/history',
    component: () => import('../views/HistoryView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/admin',
    component: () => import('../views/AdminView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _, next) => {
  const auth = useAuthStore()

  if (to.meta.requiresAuth && !auth.isLoggedIn) return next('/login')
  if (to.meta.guest && auth.isLoggedIn) return next('/dashboard')
  if (to.meta.requiresAdmin && !auth.isAdmin) return next('/dashboard')
  next()
})

export default router
