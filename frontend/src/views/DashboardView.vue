<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { Dashboard } from '@/api/types'
import StatCard from '@/components/StatCard.vue'
import { eventClass, eventLabels, formatDateTime, notifyLabel } from '@/lib/format'

const data = ref<Dashboard | null>(null)
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api<Dashboard>('/api/dashboard')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-5">
    <div v-if="error" class="card border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
      加载失败：{{ error }}
    </div>

    <div v-if="loading" class="grid gap-4 md:grid-cols-4">
      <div v-for="i in 4" :key="i" class="card h-28 animate-pulse bg-slate-50" />
    </div>

    <template v-else-if="data">
      <div class="grid gap-4 md:grid-cols-4">
        <StatCard label="在售房源" :value="data.active_listings" hint="当前 active" tone="emerald" />
        <StatCard label="今日新增" :value="data.new_today" hint="首次发现" tone="sky" />
        <StatCard label="今日降价" :value="data.price_drops_today" hint="price_drop 事件" tone="amber" />
        <StatCard label="今日下架" :value="data.gone_today" hint="gone 事件" />
      </div>

      <div class="grid gap-5 lg:grid-cols-3">
        <section class="card p-5 lg:col-span-2">
          <div class="flex items-center justify-between">
            <div>
              <h2 class="text-sm font-semibold text-slate-900">最近事件</h2>
              <p class="mt-1 text-xs text-slate-400">新上架、降价与下架</p>
            </div>
            <button class="btn-ghost" @click="load">刷新</button>
          </div>
          <div v-if="data.recent_events.length === 0" class="mt-6 rounded-xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-400">
            暂无事件，等待第一次采集
          </div>
          <div v-else class="mt-4 divide-y divide-slate-100">
            <div v-for="event in data.recent_events" :key="event.id" class="flex items-center gap-3 py-3">
              <span class="badge" :class="eventClass(event.type)">{{ eventLabels[event.type] ?? event.type }}</span>
              <div class="min-w-0 flex-1">
                <div class="truncate text-sm text-slate-700">{{ event.listing_title ?? '未知房源' }}</div>
                <div class="text-xs text-slate-400">{{ formatDateTime(event.created_at) }}</div>
              </div>
              <span class="text-xs text-slate-400">{{ notifyLabel(event.payload, event.notified) }}</span>
            </div>
          </div>
        </section>

        <section class="card p-5">
          <h2 class="text-sm font-semibold text-slate-900">数据源健康</h2>
          <p class="mt-1 text-xs text-slate-400">最近一次运行状态</p>
          <div class="mt-4 space-y-3">
            <div v-for="source in data.sources" :key="source.id" class="rounded-xl border border-slate-100 p-3">
              <div class="flex items-center justify-between">
                <div class="text-sm font-medium text-slate-800">{{ source.name }}</div>
                <span
                  class="badge"
                  :class="source.enabled ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'"
                >
                  {{ source.enabled ? '启用' : '停用' }}
                </span>
              </div>
              <div class="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-500">
                <div>在售 {{ source.active_listings }}</div>
                <div>排队 {{ source.queued_jobs }}</div>
                <div class="col-span-2">
                  最近：{{ source.last_run_status ?? '未运行' }} · {{ formatDateTime(source.last_run_at) }}
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>
