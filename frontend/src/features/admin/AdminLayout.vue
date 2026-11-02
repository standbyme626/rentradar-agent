<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Component } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import {
  Bot,
  Clock3,
  Image,
  LayoutGrid,
  ListFilter,
  LogOut,
  Menu,
  Plug,
  Route,
  ScrollText,
  Settings,
  TriangleAlert,
  X,
} from 'lucide-vue-next'
import { adminApi } from '@/api/services/admin'
import { mockOverview } from '@/api/mock/admin'
import { useLazyData } from '@/composables/useLazyData'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const mobileOpen = ref(false)
const { data: overview } = useLazyData(() => adminApi.overview(), mockOverview)
const stats = computed(() => overview.value.stats)

type NavItem = {
  to: string
  label: string
  icon: Component
  badge?: string
  badgeTone?: 'coral'
}

const groups: Array<{ label: string; items: NavItem[] }> = [
  {
    label: '概览',
    items: [{ to: '/admin/overview', label: '总览', icon: LayoutGrid }],
  },
  {
    label: '数据',
    items: [
      { to: '/admin/candidates', label: '候选工作台', icon: ListFilter },
      { to: '/admin/commute', label: '通勤与预算', icon: Route },
      { to: '/admin/quality', label: '数据质量', icon: TriangleAlert },
    ],
  },
  {
    label: 'Agent',
    items: [{ to: '/admin/agent', label: 'Agent 监控', icon: Bot }],
  },
  {
    label: '内容',
    items: [{ to: '/admin/images', label: '图片 / AI', icon: Image, badge: '0', badgeTone: 'coral' }],
  },
  {
    label: '运营',
    items: [
      { to: '/admin/providers', label: 'API 管理', icon: Plug },
      { to: '/admin/tasks', label: '采集任务', icon: Clock3, badge: 'API' },
      { to: '/admin/logs', label: '运行日志', icon: ScrollText },
      { to: '/admin/settings', label: '设置', icon: Settings },
    ],
  },
]

const title = computed(() => (route.meta.title as string) ?? '总览')
const crumb = computed(() => (route.meta.crumb as string) ?? '概览 / 总览')

async function signOut() {
  await auth.logout()
  await router.replace('/login')
}

watch(
  () => route.fullPath,
  () => {
    mobileOpen.value = false
  },
)
</script>

<template>
  <div class="flex min-h-screen bg-canvas text-ink">
    <Transition name="fade">
      <div v-if="mobileOpen" class="fixed inset-0 z-40 bg-ink/35 md:hidden" @click="mobileOpen = false" />
    </Transition>

    <aside
      class="fixed inset-y-0 left-0 z-50 flex w-[220px] shrink-0 flex-col overflow-y-auto border-r border-sidebar-line bg-sidebar transition-transform md:sticky md:top-0 md:h-screen md:translate-x-0"
      :class="mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'"
    >
      <div class="flex items-center gap-2.5 border-b border-sidebar-line px-4 py-4">
        <div class="grid h-7 w-7 place-items-center rounded-lg bg-forest text-white">
          <LayoutGrid :size="14" />
        </div>
        <div class="min-w-0 flex-1">
          <div class="text-[13.5px] font-bold leading-5 text-[#f2f7f3]">RentRadar</div>
          <div class="-mt-0.5 text-[9.5px] text-[#7f9489]">数据控制台 v2</div>
        </div>
        <button class="text-[#7f9489] md:hidden" @click="mobileOpen = false">
          <X :size="16" />
        </button>
      </div>

      <nav class="flex-1 py-2">
        <template v-for="group in groups" :key="group.label">
          <div class="px-4 pb-1.5 pt-4 text-[9.5px] font-semibold uppercase tracking-[0.12em] text-[#6f8579]">
            {{ group.label }}
          </div>
          <RouterLink
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            class="mx-2 flex items-center gap-2.5 rounded-lg px-3 py-2 text-[12.5px] text-[#b9c9c0] transition hover:bg-sidebar-2 hover:text-[#e9f1ec]"
            active-class="bg-forest text-white font-semibold"
          >
            <component :is="item.icon" :size="14" class="shrink-0 opacity-90" />
            <span class="flex-1">{{ item.label }}</span>
            <span
              v-if="item.badge"
              class="rounded-full px-1.5 py-0.5 text-[9px] font-semibold"
              :class="
                item.badgeTone === 'coral'
                  ? 'bg-[#5a2a22] text-[#f0a08c]'
                  : 'bg-sidebar-2 text-[#a9bdb1]'
              "
            >
              {{ item.badge }}
            </span>
          </RouterLink>
        </template>
      </nav>

      <div class="border-t border-sidebar-line px-4 py-3 text-[10px] leading-5 text-[#7f9489]">
        <div><b class="text-[#b9c9c0]">API</b> :8010 · <b class="text-[#b9c9c0]">DB</b> :5433</div>
        <div><b class="text-[#b9c9c0]">采集</b> 运行中 · 任务 1</div>
        <div>
          <b class="text-[#b9c9c0]">数据源</b>
          <RouterLink to="/admin/providers" class="underline hover:text-[#e9f1ec]">API 管理</RouterLink>
        </div>
        <div class="mt-1 text-[#5f7267]">库内 {{ stats.listings }} 套 · {{ stats.scored }} 已评分</div>
      </div>
    </aside>

    <div class="flex min-w-0 flex-1 flex-col">
      <header
        class="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-canvas/88 px-4 backdrop-blur sm:px-6"
      >
        <button class="btn-ghost btn-sm md:hidden" @click="mobileOpen = true">
          <Menu :size="16" />
        </button>
        <h1 class="text-[14.5px] font-semibold text-ink">{{ title }}</h1>
        <span class="hidden text-[11px] text-faint sm:inline">{{ crumb }}</span>
        <div class="ml-auto flex items-center gap-2">
          <span class="hidden items-center gap-1.5 rounded-full border border-line bg-paper px-2.5 py-1 text-[10.5px] text-muted lg:inline-flex">
            <span class="h-1.5 w-1.5 rounded-full bg-forest" />API ok
          </span>
          <span class="hidden items-center gap-1.5 rounded-full border border-line bg-paper px-2.5 py-1 text-[10.5px] text-muted sm:inline-flex">
            <span class="h-1.5 w-1.5 rounded-full bg-forest" />采集运行中
          </span>
          <RouterLink
            to="/admin/providers"
            class="hidden items-center gap-1.5 rounded-full border border-line bg-paper px-2.5 py-1 text-[10.5px] text-muted hover:text-forest lg:inline-flex"
          >
            <span class="h-1.5 w-1.5 rounded-full bg-amber" />数据源管理
          </RouterLink>
          <RouterLink
            to="/"
            class="hidden rounded-full border border-line bg-paper px-2.5 py-1 text-[10.5px] text-muted hover:text-forest sm:inline-flex"
          >
            用户端
          </RouterLink>
          <span class="hidden max-w-[120px] truncate text-[10.5px] text-muted sm:inline">
            {{ auth.displayName || '—' }}
          </span>
          <span class="hidden rounded-full bg-forest-soft px-2 py-0.5 text-[9px] font-semibold text-forest sm:inline">
            {{ auth.user?.role === 'admin' ? '管理员' : '只读' }}
          </span>
          <button class="btn-ghost btn-sm" title="退出登录" @click="signOut">
            <LogOut :size="15" />
          </button>
          <div class="grid h-7 w-7 place-items-center rounded-full bg-ink text-[10px] font-semibold text-paper">
            {{ (auth.displayName || 'R').slice(0, 1).toUpperCase() }}
          </div>
        </div>
      </header>

      <main class="w-full max-w-[1520px] flex-1 px-4 pb-24 pt-5 sm:px-6">
        <RouterView />
      </main>
    </div>
  </div>
</template>
