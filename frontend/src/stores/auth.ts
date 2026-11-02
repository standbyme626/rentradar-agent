import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { AuthUser } from '@/api/contracts'
import { authApi } from '@/api/services/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthUser | null>(null)
  const ready = ref(false)
  let pending: Promise<void> | null = null

  const isAdmin = computed(() => user.value?.role === 'admin')
  const displayName = computed(() => user.value?.username ?? '')

  async function ensureLoaded(force = false) {
    if (ready.value && !force) return
    if (pending) return pending
    pending = (async () => {
      try {
        user.value = await authApi.me()
      } catch {
        user.value = null
      } finally {
        ready.value = true
        pending = null
      }
    })()
    return pending
  }

  async function login(username: string, password: string) {
    user.value = await authApi.login(username, password)
    ready.value = true
    return user.value
  }

  async function logout() {
    try {
      await authApi.logout()
    } finally {
      user.value = null
      ready.value = true
    }
  }

  function clear() {
    user.value = null
    ready.value = true
  }

  return {
    user,
    ready,
    isAdmin,
    displayName,
    ensureLoaded,
    login,
    logout,
    clear,
  }
})
