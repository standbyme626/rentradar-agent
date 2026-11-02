<script setup lang="ts">
import { computed, ref } from 'vue'
import { adminApi } from '@/api/services/admin'
import { useLazyData } from '@/composables/useLazyData'
import { formatTime, runs as runsSnapshot } from './adminData'

const status = ref('all')
const { data: runsData, loading, error, reload } = useLazyData(() => adminApi.runs(), runsSnapshot)
const runs = computed(() => runsData.value)
const filteredRuns = computed(() =>
  status.value === 'all' ? runs.value : runs.value.filter((run) => run.status === status.value),
)

const events = [
  ['✓', '采集恢复：贝壳 App API', '10-30 21:18', '任务 1 切 transport=api；30 页慢扫 900 条，按 house_code 去重。', 'green'],
  ['✓', 'Provider 管理上线', '10-31 01:10', '接入贝壳 API/CDP、高德、天地图、滴滴 MCP；/admin/providers 可用。', 'green'],
  ['✓', '管理端切真实数据', '10-31 01:40', '/api/admin/* BFF 上线；总览、候选、质量、任务、设置读取真实库。', 'green'],
  ['✓', 'Agent 规则版上线', '10-31 02:15', 'SSE + sessions/monitors + 管理端 Trace 已上线；LLM/详情/AI 仍待接入。', 'green'],
  ['!', '通勤多时段未接入', '—', '当前 286 条单次采样；p50/p90 待 Top 10 候选。', 'coral'],
]
</script>

<template>
  <div>
    <h2 class="text-[20px] font-bold tracking-tight">运行日志</h2>
    <p class="mt-1 text-[12.5px] text-muted">最近 10 次运行与关键事件；验证码、富化中断、重评分都在这里。</p>

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

    <section class="card mt-4 p-4">
      <h3 class="panel-title">关键事件</h3>
      <div class="mt-3 space-y-4">
        <div v-for="(event, index) in events" :key="index" class="flex gap-3">
          <span
            class="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full text-[10px] font-bold"
            :class="
              event[4] === 'coral'
                ? 'bg-coral-soft text-coral'
                : event[4] === 'green'
                  ? 'bg-forest text-white'
                  : 'bg-sand text-muted'
            "
          >
            {{ event[0] }}
          </span>
          <div>
            <div class="flex flex-wrap items-center gap-2">
              <b class="text-[12px] text-ink">{{ event[1] }}</b>
              <span class="mono text-[9.5px] text-faint">{{ event[2] }}</span>
            </div>
            <p class="mt-0.5 text-[10.5px] leading-5 text-muted">{{ event[3] }}</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
