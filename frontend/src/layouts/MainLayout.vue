<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

const route = useRoute()
const apiOk = ref<boolean | null>(null)

const nav = [
  { to: '/', label: '仪表盘' },
  { to: '/listings', label: '房源' },
  { to: '/tasks', label: '任务' },
  { to: '/settings', label: '设置' },
]

const title = computed(() => (route.meta.title as string) ?? '仪表盘')

onMounted(async () => {
  try {
    const response = await fetch('/health')
    const data = await response.json()
    apiOk.value = data.status === 'ok'
  } catch {
    apiOk.value = false
  }
})
</script>

<template>
  <div class="min-h-screen bg-slate-100 lg:flex">
    <aside class="hidden w-60 shrink-0 flex-col bg-ink px-4 py-6 text-slate-300 lg:flex">
      <div class="flex items-center gap-3 px-2">
        <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500 text-sm font-bold text-white">
          RR
        </div>
        <div>
          <div class="text-sm font-semibold text-white">RentRadar</div>
          <div class="text-xs text-slate-500">租房雷达</div>
        </div>
      </div>

      <nav class="mt-8 space-y-1">
        <RouterLink
          v-for="item in nav"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-400 transition hover:bg-white/5 hover:text-white"
          active-class="bg-white/10 text-white"
          :exact-active-class="item.to === '/' ? 'bg-white/10 text-white' : ''"
        >
          <span class="h-1.5 w-1.5 rounded-full bg-emerald-400/70" />
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="mt-auto rounded-xl border border-white/10 bg-white/5 p-3 text-xs leading-5 text-slate-400">
        <div class="flex items-center gap-2">
          <span
            class="h-2 w-2 rounded-full"
            :class="apiOk === null ? 'bg-slate-500' : apiOk ? 'bg-emerald-400' : 'bg-rose-400'"
          />
          {{ apiOk === null ? '连接中…' : apiOk ? 'API 正常' : 'API 异常' }}
        </div>
        <div class="mt-1 text-slate-500">深圳 · 龙岗 · 横岗</div>
      </div>
    </aside>

    <div class="flex min-w-0 flex-1 flex-col">
      <header class="sticky top-0 z-10 border-b border-slate-200 bg-white/85 px-5 py-4 backdrop-blur">
        <div class="flex items-center justify-between gap-4">
          <div>
            <div class="text-xs text-slate-400">RentRadar</div>
            <h1 class="text-lg font-semibold text-slate-900">{{ title }}</h1>
          </div>
          <div class="flex items-center gap-2">
            <a href="/docs" target="_blank" class="btn-ghost hidden sm:inline-flex">API 文档</a>
            <span class="badge bg-emerald-50 text-emerald-700">P0 骨架</span>
          </div>
        </div>
        <nav class="mt-3 flex gap-2 overflow-x-auto lg:hidden">
          <RouterLink
            v-for="item in nav"
            :key="item.to"
            :to="item.to"
            class="whitespace-nowrap rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600"
            active-class="border-emerald-200 bg-emerald-50 text-emerald-700"
          >
            {{ item.label }}
          </RouterLink>
        </nav>
      </header>

      <main class="flex-1 p-5 lg:p-7">
        <RouterView />
      </main>
    </div>
  </div>
</template>
