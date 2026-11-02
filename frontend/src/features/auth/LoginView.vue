<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowRight, LockKeyhole, MapPin, UserRound } from 'lucide-vue-next'
import { ApiError } from '@/api/http'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const redirect = computed(() => {
  const value = route.query.redirect
  return typeof value === 'string' && value.startsWith('/') ? value : '/'
})

onMounted(async () => {
  await auth.ensureLoaded()
  if (auth.user) await router.replace(redirect.value)
})

async function submit() {
  if (loading.value) return
  error.value = ''
  if (!username.value.trim() || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    await router.replace(redirect.value)
  } catch (err) {
    if (err instanceof ApiError) {
      error.value = typeof err.detail === 'string' ? err.detail : `登录失败（${err.status}）`
    } else {
      error.value = '登录失败，请检查网络后重试'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="relative flex min-h-screen items-center justify-center overflow-hidden bg-canvas px-4 py-10 text-ink">
    <div class="pointer-events-none absolute -right-48 -top-52 h-[620px] w-[620px] rounded-full bg-forest/10 blur-3xl" />
    <div class="pointer-events-none absolute -bottom-64 -left-48 h-[560px] w-[560px] rounded-full bg-coral/10 blur-3xl" />

    <div class="relative w-full max-w-[420px]">
      <div class="mb-6 flex items-center gap-3">
        <div class="grid h-10 w-10 place-items-center rounded-xl bg-forest text-white shadow-lg shadow-forest/20">
          <MapPin :size="18" />
        </div>
        <div>
          <div class="text-[19px] font-bold tracking-tight">RentRadar</div>
          <div class="text-[11px] text-muted">深圳 5 号线 · 租房情报工作台</div>
        </div>
      </div>

      <section class="card p-5 sm:p-6">
        <h1 class="text-[17px] font-bold tracking-tight">登录</h1>
        <p class="mt-1 text-[11.5px] leading-5 text-muted">
          账号由管理员创建。登录后才能使用 Agent、监控和管理端。
        </p>

        <form class="mt-5 space-y-3" @submit.prevent="submit">
          <div>
            <label class="label" for="username">用户名</label>
            <div class="relative">
              <UserRound :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
              <input
                id="username"
                v-model="username"
                class="input pl-9"
                autocomplete="username"
                placeholder="admin"
                :disabled="loading"
              />
            </div>
          </div>
          <div>
            <label class="label" for="password">密码</label>
            <div class="relative">
              <LockKeyhole :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
              <input
                id="password"
                v-model="password"
                type="password"
                class="input pl-9"
                autocomplete="current-password"
                placeholder="输入密码"
                :disabled="loading"
              />
            </div>
          </div>

          <div v-if="error" class="rounded-lg border border-coral/25 bg-coral-soft px-3 py-2 text-[11px] leading-5 text-coral">
            {{ error }}
          </div>

          <button type="submit" class="btn-primary h-10 w-full justify-center" :disabled="loading">
            {{ loading ? '登录中…' : '登录' }}
            <ArrowRight v-if="!loading" :size="15" />
          </button>
        </form>

        <div class="mt-4 rounded-xl border border-line bg-paper2 px-3.5 py-2.5 text-[10.5px] leading-5 text-muted">
          忘记密码：在服务器执行
          <code class="mono rounded bg-sand px-1.5 py-0.5 text-[10px]">python -m app.cli set-password --username &lt;name&gt;</code>
        </div>
      </section>

      <p class="mt-4 text-center text-[10px] text-faint">RentRadar · LAN only · 所有操作写入审计日志</p>
    </div>
  </div>
</template>
