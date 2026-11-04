<script setup lang="ts">
import { computed, ref } from 'vue'
import { adminApi } from '@/api/services/admin'
import { useLazyData } from '@/composables/useLazyData'
import { formatTime } from './adminData'

const status = ref('all')
const { data: runsData, loading, error, reload } = useLazyData(() => adminApi.runs(), [])
const runs = computed(() => runsData.value)
const filteredRuns = computed(() =>
  status.value === 'all' ? runs.value : runs.value.filter((run) => run.status === status.value),
)

</script>

<template>
  <div>
    <h2 class="text-[20px] font-bold tracking-tight">运行日志</h2>
    <p class="mt-1 text-[12.5px] text-muted">最近运行记录；验证码、富化中断、重评分都在这里。</p>

    <section class="card mt-4 p-4">
      <h3 class="panel-title">运行记录 <span class="hint">最近 {{ runs.length }} 次 · {{ loading ? '加载中' : '已同步' }}</span></h3>
      <div v-if="error" class="mt-2 rounded-xl border border-coral/25 bg-coral-soft px-3.5 py-2 text-[10.5px] text-coral">
        {{ error }}
        <button class="ml-2 underline" @click="reload">重试</button>
      </div>
      <div class="mt-2 flex items-center gap-2">
        <select v-model="status" class="input w-[130px]">
          <option value="all">全部状态</option>
          <option value="done">完成</option>
          <option value="failed">失败</option>
        </select>
        <span class="text-[11px] text-faint">{{ filteredRuns.length }} 条</span>
      </div>
      <div class="mt-2 overflow-x-auto">
        <table class="w-full text-left text-[12px]">
          <thead class="border-b border-line bg-paper2 text-[10px] uppercase tracking-wide text-faint">
            <tr>
              <th class="px-3 py-2.5 font-semibold">Run</th>
              <th class="px-3 py-2.5 font-semibold">状态</th>
              <th class="px-3 py-2.5 font-semibold">抓取</th>
              <th class="px-3 py-2.5 font-semibold">新增</th>
              <th class="px-3 py-2.5 font-semibold">评分</th>
              <th class="px-3 py-2.5 font-semibold">时间</th>
              <th class="px-3 py-2.5 font-semibold">错误</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="run in filteredRuns" :key="run.id" class="border-b border-line last:border-0">
              <td class="mono px-3 py-2.5">#{{ run.id }}</td>
              <td class="px-3 py-2.5"><span :class="run.status === 'done' ? 'tag-green' : 'tag-coral'">{{ run.status === 'done' ? '完成' : '失败' }}</span></td>
              <td class="px-3 py-2.5">{{ run.stats.fetched ?? 0 }}</td>
              <td class="px-3 py-2.5">{{ run.stats.new ?? 0 }}</td>
              <td class="px-3 py-2.5">{{ run.stats.scored ?? 0 }}</td>
              <td class="mono px-3 py-2.5 text-faint">{{ formatTime(run.started_at) }}</td>
              <td class="px-3 py-2.5 text-muted">{{ (run.error || '—').slice(0, 40) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

  </div>
</template>
