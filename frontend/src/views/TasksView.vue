<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api } from '@/api/client'
import type { TaskItem } from '@/api/types'
import { formatDateTime } from '@/lib/format'

const tasks = ref<TaskItem[]>([])
const loading = ref(true)
const error = ref('')
const message = ref('')
const form = reactive({ name: '新监控任务', city_code: 'sz', source_code: 'beike' })

async function load() {
  loading.value = true
  error.value = ''
  try {
    tasks.value = await api<TaskItem[]>('/api/tasks')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

async function createTask() {
  message.value = ''
  try {
    await api<TaskItem>('/api/tasks', {
      method: 'POST',
      body: JSON.stringify(form),
    })
    message.value = '任务已创建'
    await load()
  } catch (err) {
    message.value = err instanceof Error ? err.message : String(err)
  }
}

async function toggle(task: TaskItem) {
  message.value = ''
  try {
    await api(`/api/tasks/${task.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled: !task.enabled }),
    })
    await load()
  } catch (err) {
    message.value = err instanceof Error ? err.message : String(err)
  }
}

async function run(task: TaskItem) {
  message.value = ''
  try {
    const result = await api<{ job_id: number }>(`/api/tasks/${task.id}/run`, { method: 'POST' })
    message.value = `已入队，job #${result.job_id}`
    await load()
  } catch (err) {
    message.value = err instanceof Error ? err.message : String(err)
  }
}

function scheduleText(task: TaskItem): string {
  const fast = task.schedule.fast_minutes ?? '—'
  const slow = task.schedule.slow_minutes ?? '—'
  return `快 ${fast} 分 / 慢 ${slow} 分`
}

onMounted(load)
</script>

<template>
  <div class="space-y-5">
    <div class="card p-5">
      <h2 class="text-sm font-semibold text-slate-900">新建任务</h2>
      <div class="mt-3 grid gap-3 md:grid-cols-4">
        <input v-model="form.name" class="input" placeholder="任务名" />
        <input v-model="form.city_code" class="input" placeholder="城市 code（sz）" />
        <input v-model="form.source_code" class="input" placeholder="源 code（beike）" />
        <button class="btn-primary" @click="createTask">创建</button>
      </div>
      <div v-if="message" class="mt-3 text-xs text-emerald-600">{{ message }}</div>
    </div>

    <div v-if="error" class="card border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
      加载失败：{{ error }}
    </div>

    <div class="card overflow-hidden">
      <div v-if="loading" class="p-10 text-center text-sm text-slate-400">加载中…</div>
      <div v-else-if="tasks.length === 0" class="p-10 text-center text-sm text-slate-400">暂无任务</div>
      <table v-else class="min-w-full text-sm">
        <thead class="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th class="px-4 py-3 text-left font-medium">任务</th>
            <th class="px-4 py-3 text-left font-medium">城市 / 源</th>
            <th class="px-4 py-3 text-left font-medium">调度</th>
            <th class="px-4 py-3 text-left font-medium">最近运行</th>
            <th class="px-4 py-3 text-left font-medium">状态</th>
            <th class="px-4 py-3 text-right font-medium">操作</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr v-for="task in tasks" :key="task.id">
            <td class="px-4 py-3">
              <div class="font-medium text-slate-800">{{ task.name }}</div>
              <div class="text-xs text-slate-400">#{{ task.id }} · {{ task.account_strategy }} / {{ task.proxy_strategy }}</div>
            </td>
            <td class="px-4 py-3 text-slate-600">{{ task.city_code }} / {{ task.source_code }}</td>
            <td class="px-4 py-3 text-slate-600">{{ scheduleText(task) }}</td>
            <td class="px-4 py-3 text-xs text-slate-400">
              {{ task.last_run_status ?? '未运行' }}<br />
              {{ formatDateTime(task.last_run_at) }}
            </td>
            <td class="px-4 py-3">
              <span class="badge" :class="task.enabled ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'">
                {{ task.enabled ? '启用' : '停用' }}
              </span>
            </td>
            <td class="px-4 py-3 text-right">
              <div class="flex justify-end gap-2">
                <button class="btn-ghost" @click="toggle(task)">{{ task.enabled ? '停用' : '启用' }}</button>
                <button class="btn-primary" @click="run(task)">立即运行</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
