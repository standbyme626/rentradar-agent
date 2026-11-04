<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import type { CrawlCoverage } from '@/api/contracts'
import type { CityInfo, SourceInfo, Task } from '@/api/types'
import { adminApi } from '@/api/services/admin'
import { useLazyData } from '@/composables/useLazyData'
import { useToast } from '@/composables/useToast'
import AppSheet from '@/components/ui/AppSheet.vue'

const { toast } = useToast()
const helpOpen = ref(false)
const busy = ref(false)
const taskSheet = ref(false)
const taskMode = ref<'create' | 'edit'>('create')
const taskBusy = ref(false)
const cities = ref<CityInfo[]>([])
const sources = ref<SourceInfo[]>([])
const editingFilters = ref<Record<string, unknown>>({})
const taskForm = reactive({
  id: 0,
  name: '',
  cityCode: 'sz',
  sourceCode: 'beike',
  enabled: true,
  fastMinutes: 10,
  slowMinutes: 180,
  line: 'li110460696',
  transport: 'api',
  feedPath: '',
})
const { data: items, loading, error, reload } = useLazyData(() => adminApi.tasks(), [])

async function reloadCatalog() {
  try {
    const [cityRows, sourceRows] = await Promise.all([adminApi.cities(), adminApi.sources()])
    cities.value = cityRows.filter((item) => item.enabled)
    sources.value = sourceRows.filter((item) => item.supported)
  } catch {
    toast('城市/来源加载失败')
  }
}
reloadCatalog()
const emptyCoverage: CrawlCoverage = {
  task_id: null,
  task_name: null,
  line: null,
  shard_cursor: 0,
  shards: [],
  summary: { shards: 0, listings: 0, complete: 0, scanned: 0, last_scan_at: null },
}
const {
  data: coverage,
  loading: coverageLoading,
  error: coverageError,
  reload: reloadCoverage,
} = useLazyData(() => adminApi.crawlCoverage(), emptyCoverage)
const task1 = computed(() => items.value.find((item) => item.id === 1) ?? items.value[0])
const task2 = computed(() => items.value.find((item) => item.id === 2) ?? items.value[1])
const filtersText = computed(() => {
  if (!task1.value) return '{}'
  const text = JSON.stringify(task1.value.filters)
  return text.length > 140 ? `${text.slice(0, 140)}…` : text
})
const fastText = computed(() => `每 ${task1.value?.schedule?.fast_minutes ?? 10} 分钟 · 1 页`)
const slowText = computed(() => `每 ${task1.value?.schedule?.slow_minutes ?? 180} 分钟 · 分片轮转`)
const transport = computed(() => String(task1.value?.filters?.transport ?? 'cdp'))
const shardCount = computed(() => {
  const conditions = task1.value?.filters?.shard_conditions
  return Array.isArray(conditions) ? conditions.length : 0
})
const scopeText = computed(() =>
  shardCount.value ? `shards=${shardCount.value}` : 'scope=line:li110460696',
)
const coverageTime = computed(() =>
  coverage.value.summary.last_scan_at
    ? new Date(coverage.value.summary.last_scan_at).toLocaleString('zh-CN', {
        hour12: false,
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
    : '—',
)

function openCreate() {
  taskMode.value = 'create'
  editingFilters.value = {}
  Object.assign(taskForm, {
    id: 0,
    name: '新建采集任务',
    cityCode: cities.value[0]?.code ?? 'sz',
    sourceCode: 'beike',
    enabled: true,
    fastMinutes: 10,
    slowMinutes: 180,
    line: 'li110460696',
    transport: 'api',
    feedPath: '',
  })
  taskSheet.value = true
}

function openEdit(task: Task) {
  taskMode.value = 'edit'
  const filters = task.filters ?? {}
  editingFilters.value = { ...filters }
  Object.assign(taskForm, {
    id: task.id,
    name: task.name,
    cityCode: task.city_code ?? 'sz',
    sourceCode: task.source_code ?? 'beike',
    enabled: task.enabled,
    fastMinutes: task.schedule?.fast_minutes ?? 10,
    slowMinutes: task.schedule?.slow_minutes ?? 180,
    line: String(filters.line ?? 'li110460696'),
    transport: String(filters.transport ?? 'api'),
    feedPath: String(filters.feed_path ?? ''),
  })
  taskSheet.value = true
}

async function saveTask() {
  if (taskBusy.value) return
  taskBusy.value = true
  try {
    const nextFilters = taskForm.sourceCode === 'manual'
      ? { feed_path: taskForm.feedPath }
      : { line: taskForm.line, transport: taskForm.transport, fast_pages: 1 }
    const filters = taskMode.value === 'edit'
      ? { ...editingFilters.value, ...nextFilters }
      : nextFilters
    const schedule = { fast_minutes: taskForm.fastMinutes, slow_minutes: taskForm.slowMinutes }
    if (taskMode.value === 'create') {
      await adminApi.createTask({
        name: taskForm.name,
        cityCode: taskForm.cityCode,
        sourceCode: taskForm.sourceCode,
        filters,
        schedule,
        enabled: taskForm.enabled,
      })
      toast('任务已创建')
    } else {
      await adminApi.updateTask(taskForm.id, {
        name: taskForm.name,
        enabled: taskForm.enabled,
        filters,
        schedule,
      })
      toast('任务已更新')
    }
    taskSheet.value = false
    reload()
  } catch {
    toast('保存失败，请检查过滤条件')
  } finally {
    taskBusy.value = false
  }
}

async function toggleTask(task: Task) {
  try {
    await adminApi.updateTask(task.id, { enabled: !task.enabled })
    reload()
    toast(`任务 #${task.id} 已${task.enabled ? '暂停' : '启用'}`)
  } catch {
    toast('任务状态更新失败')
  }
}

async function runTaskRow(task: Task) {
  try {
    const result = await adminApi.runTask(task.id)
    toast(`已入队任务 #${result.job_id}`)
  } catch {
    toast('运行失败，请稍后重试')
  }
}

async function runNow() {
  if (!task1.value || busy.value) return
  busy.value = true
  try {
    const result = await adminApi.runTask(task1.value.id)
    toast(`已入队任务 #${result.job_id}`)
  } catch {
    toast('运行失败，请稍后重试')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div>
    <h2 class="text-[20px] font-bold tracking-tight">采集任务</h2>
    <p class="mt-1 text-[12.5px] text-muted">当前采集运行中（贝壳 App API）；CDP 仅作兜底。</p>
    <div v-if="loading" class="mt-3 rounded-xl border border-line bg-paper2 px-3.5 py-2 text-[10.5px] text-muted">任务加载中…</div>
    <div v-else-if="error" class="mt-3 rounded-xl border border-coral/25 bg-coral-soft px-3.5 py-2 text-[10.5px] text-coral">
      {{ error }}
      <button class="ml-2 underline" @click="reload">重试</button>
    </div>

    <div class="mt-4 grid gap-4 xl:grid-cols-2">
      <section class="card p-4">
        <h3 class="panel-title">
          任务 1 · 贝壳 5 号线
          <span class="hint"><span :class="task1?.enabled ? 'tag-green' : 'tag-coral'">{{ task1?.enabled ? '运行中' : '已暂停' }}</span></span>
        </h3>
        <div class="mt-3 space-y-3">
          <div><label class="label">名称</label><input class="input" :value="task1?.name ?? ''" readonly /></div>
          <div><label class="label">过滤</label><input class="input" :value="filtersText" readonly /></div>
          <div class="grid gap-3 sm:grid-cols-2">
            <div><label class="label">快扫</label><input class="input" :value="fastText" readonly /></div>
            <div><label class="label">慢扫</label><input class="input" :value="slowText" readonly /></div>
          </div>
        </div>
        <div class="mt-3 flex flex-wrap gap-1.5">
          <span :class="task1?.enabled ? 'tag-green' : 'tag-coral'">{{ task1?.enabled ? 'enabled=true' : 'enabled=false' }}</span>
          <span class="tag-neutral">transport={{ transport }}</span>
          <span class="tag-neutral">{{ scopeText }}</span>
        </div>
        <div class="mt-3 flex flex-wrap gap-2">
          <button class="btn-primary" :disabled="busy || !task1" @click="runNow">
            {{ busy ? '提交中…' : '立即运行' }}
          </button>
          <button class="btn" @click="helpOpen = true">CDP 兜底说明</button>
        </div>
      </section>

      <section class="card p-4">
        <h3 class="panel-title">任务 2 · 链家 <span class="hint"><span class="tag-neutral">未启用</span></span></h3>
        <div class="mt-3 space-y-3">
          <div><label class="label">名称</label><input class="input" :value="task2?.name ?? ''" readonly /></div>
          <div>
            <label class="label">说明</label>
            <textarea class="input h-24" readonly>链家 robots 全站 Disallow，不自动抓；仅保留手动链接。当前采集以贝壳 App API 为准。</textarea>
          </div>
        </div>
        <div class="mt-3 flex flex-wrap gap-1.5"><span class="tag-neutral">robots 禁止</span><span class="tag-neutral">手动模式</span></div>
      </section>
    </div>

    <section class="card mt-4 p-4">
      <h3 class="panel-title">
        5 号线分片覆盖
        <span class="hint">
          {{ coverage.summary.complete }}/{{ coverage.summary.shards }} 个分片完整 ·
          库内 {{ coverage.summary.listings }} 套 · 最近 {{ coverageTime }}
        </span>
      </h3>
      <div v-if="coverageLoading" class="mt-2 text-[10.5px] text-muted">覆盖数据加载中…</div>
      <div v-else-if="coverageError" class="mt-2 text-[10.5px] text-coral">
        {{ coverageError }}
        <button class="ml-2 underline" @click="reloadCoverage">重试</button>
      </div>
      <div v-else-if="!coverage.shards.length" class="mt-2 rounded-xl border border-dashed border-line2 bg-paper2 px-3.5 py-3 text-[11px] text-muted">
        任务尚未配置分片。运行 <code class="mono">python -m app.cli apply-shards --task-id 1 --line 5号线</code> 后，这里会按站点显示已抓/总数/完整状态。
      </div>
      <div v-else class="mt-2 max-h-[300px] overflow-auto rounded-xl border border-line">
        <table class="w-full text-left text-[11.5px]">
          <thead class="sticky top-0 border-b border-line bg-paper2 text-[9.5px] uppercase tracking-wide text-faint">
            <tr>
              <th class="px-3 py-2 font-semibold">站点</th>
              <th class="px-3 py-2 font-semibold">已抓 / total</th>
              <th class="px-3 py-2 font-semibold">库内</th>
              <th class="px-3 py-2 font-semibold">最近状态</th>
              <th class="px-3 py-2 font-semibold">完整</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="shard in coverage.shards" :key="shard.condition" class="border-b border-line last:border-0">
              <td class="px-3 py-2 font-semibold">{{ shard.station }}</td>
              <td class="px-3 py-2">
                {{ shard.last_run?.fetched ?? '—' }} / {{ shard.last_run?.total ?? '—' }}
                <span class="text-[9px] text-faint">({{ shard.last_run?.pages ?? 0 }} 页)</span>
              </td>
              <td class="px-3 py-2">{{ shard.listings }}</td>
              <td class="px-3 py-2">
                <span v-if="shard.last_run" :class="shard.last_run.status === 'done' ? 'tag-green' : 'tag-amber'">
                  {{ shard.last_run.status }}
                </span>
                <span v-else class="tag-neutral">未扫描</span>
                <span v-if="shard.last_run?.suspect_skipped" class="ml-1 text-[9px] text-amber">跳过 suspect</span>
              </td>
              <td class="px-3 py-2">
                <span :class="shard.complete ? 'tag-green' : 'tag-amber'">{{ shard.complete ? '完整' : '未完成' }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="mt-2 text-[10px] leading-5 text-faint">
        分片轮转：慢扫每次只跑下一个站点分片（cursor {{ coverage.shard_cursor }}），在 {{ coverage.summary.scanned }}/{{ coverage.summary.shards }} 个分片留下运行记录；未完整抓取的分片不会做 suspect。
      </p>
    </section>

    <section class="card mt-4 p-4">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h3 class="panel-title">全部任务 <span class="hint">城市 / 来源独立开关</span></h3>
        <button class="btn" @click="openCreate">新建任务</button>
      </div>
      <div class="mt-3 overflow-x-auto rounded-xl border border-line">
        <table class="w-full text-left text-[11.5px]">
          <thead class="border-b border-line bg-paper2 text-[9.5px] uppercase tracking-wide text-faint">
            <tr>
              <th class="px-3 py-2 font-semibold">任务</th>
              <th class="px-3 py-2 font-semibold">城市 / 来源</th>
              <th class="px-3 py-2 font-semibold">节奏</th>
              <th class="px-3 py-2 font-semibold">状态</th>
              <th class="px-3 py-2 font-semibold">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="task in items" :key="task.id" class="border-b border-line last:border-0">
              <td class="px-3 py-2">
                <div class="font-semibold">#{{ task.id }} · {{ task.name }}</div>
                <div class="mono text-[9.5px] text-faint">{{ JSON.stringify(task.filters).slice(0, 90) }}</div>
              </td>
              <td class="px-3 py-2">{{ task.city_code ?? 'sz' }} / {{ task.source_code ?? 'beike' }}</td>
              <td class="px-3 py-2 text-muted">{{ task.schedule?.fast_minutes ?? 10 }} / {{ task.schedule?.slow_minutes ?? 180 }} 分钟</td>
              <td class="px-3 py-2">
                <span :class="task.enabled ? 'tag-green' : 'tag-neutral'">{{ task.enabled ? '运行中' : '已暂停' }}</span>
              </td>
              <td class="px-3 py-2">
                <div class="flex flex-wrap gap-2 text-[10px]">
                  <button class="underline" @click="openEdit(task)">编辑</button>
                  <button class="underline" @click="toggleTask(task)">{{ task.enabled ? '暂停' : '启用' }}</button>
                  <button class="underline" @click="runTaskRow(task)">运行</button>
                </div>
              </td>
            </tr>
            <tr v-if="!items.length"><td colspan="5" class="px-3 py-8 text-center text-[10.5px] text-faint">暂无任务</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="card mt-4 p-4">
      <h3 class="panel-title">采集器行为 <span class="hint">当前主通道</span></h3>
      <div class="mt-3 grid gap-4 sm:grid-cols-3">
        <div><div class="text-[10px] text-faint">通道</div><div class="mt-0.5 text-[13px] font-semibold">贝壳 App API</div><div class="text-[10px] text-muted">免登录、免签名；CDP 兜底</div></div>
        <div><div class="text-[10px] text-faint">翻页</div><div class="mt-0.5 text-[13px] font-semibold">feed_query_id 链式</div><div class="text-[10px] text-muted">30 页/轮，按 house_code 去重</div></div>
        <div><div class="text-[10px] text-faint">验证码</div><div class="mt-0.5 text-[13px] font-semibold">CDP 检测即停</div><div class="text-[10px] text-muted">自动 enabled=false，不反复撞</div></div>
      </div>
    </section>

    <AppSheet :open="helpOpen" title="CDP 兜底说明" @close="helpOpen = false">
      <div class="space-y-3 text-[12px] leading-6 text-muted">
        <div class="rounded-xl border border-line bg-paper2 px-3.5 py-2.5">
          默认走贝壳 App API。只有 API 不可用时才切 CDP；CDP 需要受控 Chrome 的登录态。
        </div>
        <ol class="list-decimal space-y-1.5 pl-5">
          <li>打开受控 Windows Chrome（`C:\Chrome-debug`）。</li>
          <li>刷新贝壳 5 号线页面，手动完成人机验证。</li>
          <li>确认页面能正常显示房源列表。</li>
          <li>手动运行 `python -m app.cli crawl --task-id 1 --pages 1 --transport cdp`。</li>
        </ol>
        <div class="rounded-xl border border-amber/25 bg-amber-soft px-3.5 py-2.5 text-[10.5px] leading-5 text-amber">
          CDP 检测到验证页会立即停止，并把任务置为 enabled=false。不要在验证码未通过时连续重试。
        </div>
      </div>
      <template #footer>
        <button class="btn" @click="helpOpen = false">关闭</button>
      </template>
    </AppSheet>

    <AppSheet :open="taskSheet" :title="taskMode === 'create' ? '新建任务' : '编辑任务'" @close="taskSheet = false">
      <div class="grid gap-3 sm:grid-cols-2">
        <div><label class="label">名称</label><input v-model="taskForm.name" class="input" /></div>
        <div><label class="label">启用</label><input v-model="taskForm.enabled" type="checkbox" class="mt-2" /></div>
        <div v-if="taskMode === 'create'">
          <label class="label">城市</label>
          <select v-model="taskForm.cityCode" class="input">
            <option v-for="city in cities" :key="city.code" :value="city.code">{{ city.name }}</option>
          </select>
        </div>
        <div v-if="taskMode === 'create'">
          <label class="label">来源</label>
          <select v-model="taskForm.sourceCode" class="input">
            <option v-for="source in sources" :key="source.code" :value="source.code">{{ source.name }}</option>
          </select>
        </div>
        <div><label class="label">快扫（分钟）</label><input v-model.number="taskForm.fastMinutes" type="number" min="1" class="input" /></div>
        <div><label class="label">慢扫（分钟）</label><input v-model.number="taskForm.slowMinutes" type="number" min="1" class="input" /></div>
        <template v-if="taskForm.sourceCode === 'manual'">
          <div class="sm:col-span-2"><label class="label">feed 文件路径</label><input v-model="taskForm.feedPath" class="input" placeholder="data/manual/brand-apartments.json" /></div>
        </template>
        <template v-else>
          <div><label class="label">线路 condition</label><input v-model="taskForm.line" class="input" /></div>
          <div><label class="label">通道</label><input v-model="taskForm.transport" class="input" /></div>
        </template>
      </div>
      <template #footer>
        <button class="btn" @click="taskSheet = false">取消</button>
        <button class="btn-primary" :disabled="taskBusy" @click="saveTask">{{ taskBusy ? '保存中…' : '保存' }}</button>
      </template>
    </AppSheet>
  </div>
</template>
