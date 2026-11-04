<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Check, Circle, Loader2, X } from 'lucide-vue-next'
import type { AgentCostData, AgentEvalData, AgentSession } from '@/api/types'
import { adminApi } from '@/api/services/admin'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppTabs from '@/components/ui/AppTabs.vue'
import { useToast } from '@/composables/useToast'
import AdminKpi from './AdminKpi.vue'

const { toast } = useToast()
const tab = ref('trace')
const q = ref('')
const status = ref('all')
const selected = ref<AgentSession | null>(null)
const sessions = ref<AgentSession[]>([])
const loading = ref(true)
const loadError = ref('')
const evalData = ref<AgentEvalData | null>(null)
const evalLoading = ref(false)
const evalError = ref('')
const running = ref(false)
const costData = ref<AgentCostData | null>(null)
const costLoading = ref(false)
const costError = ref('')

async function loadSessions() {
  loading.value = true
  loadError.value = ''
  try {
    sessions.value = await adminApi.agentSessions()
  } catch {
    loadError.value = '会话加载失败'
  } finally {
    loading.value = false
  }
}

async function loadEval(refresh = false) {
  if (evalData.value && !refresh) return
  evalLoading.value = true
  evalError.value = ''
  try {
    evalData.value = await adminApi.agentEval()
  } catch {
    evalError.value = '评测数据加载失败'
  } finally {
    evalLoading.value = false
  }
}

async function loadCost(refresh = false) {
  if (costData.value && !refresh) return
  costLoading.value = true
  costError.value = ''
  try {
    costData.value = await adminApi.agentCost(7)
  } catch {
    costError.value = '成本数据加载失败'
  } finally {
    costLoading.value = false
  }
}

onMounted(loadSessions)
watch(tab, (value) => {
  if (value === 'evals') loadEval()
  if (value === 'cost') loadCost()
})

async function runEval() {
  if (running.value) return
  running.value = true
  try {
    await adminApi.runAgentEval()
    toast('基线评测已完成')
    await loadEval(true)
  } catch {
    toast('评测运行失败，请稍后重试')
  } finally {
    running.value = false
  }
}

async function annotate(sessionId: string, label: string) {
  try {
    await adminApi.annotateSession(sessionId, label)
    toast('已记录复核结果')
  } catch {
    toast('操作失败，请稍后重试')
  }
}

const tabs = [
  { key: 'trace', label: '会话与 Trace' },
  { key: 'evals', label: '评测与反馈' },
  { key: 'cost', label: '成本与护栏' },
  { key: 'ops', label: '版本与限制' },
]

const filtered = computed(() =>
  sessions.value.filter((item) => {
    if (q.value && !`${item.id} ${item.query}`.toLowerCase().includes(q.value.toLowerCase())) return false
    if (status.value !== 'all' && item.status !== status.value) return false
    return true
  }),
)
const totalSessions = computed(() => sessions.value.length)
const doneSessions = computed(() => sessions.value.filter((item) => item.status === 'done').length)
const runningSessions = computed(() => sessions.value.filter((item) => item.status === 'running').length)
const blockedSessions = computed(() => sessions.value.filter((item) => item.status === 'blocked').length)
const avgLatency = computed(() => {
  const values = sessions.value
    .map((item) => Number.parseFloat(String(item.latency)))
    .filter(Number.isFinite)
  return values.length ? `${(values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(1)}s` : '—'
})
const toolCallCount = computed(() =>
  sessions.value.reduce((sum, item) => sum + (item.toolCalls?.length ?? 0), 0),
)
const injectionBlocks = computed(
  () =>
    sessions.value.filter((item) =>
      (item.guardrails ?? []).some((guard) => (guard.flags ?? []).includes('prompt_injection_blocked')),
    ).length,
)
const passRate = computed(() => {
  const latest = evalData.value?.latest
  return latest ? `${latest.passed} / ${latest.total}` : '—'
})
const latestEval = computed(() => evalData.value?.latest ?? null)
const evalMetrics = computed(() => latestEval.value?.metrics ?? null)
const failedCases = computed(() =>
  (latestEval.value?.cases ?? []).filter((item) => !item.passed).slice(0, 8),
)
const evalCards = computed(() => {
  const metrics = evalMetrics.value
  if (!metrics) return []
  return [
    ['意图解析', metrics.intent_case_accuracy, '整句条件全部正确'],
    ['字段准确率', metrics.intent_field_accuracy, '预算/通勤/户型/区域/标签'],
    ['工具选择', metrics.tool_accuracy, '规则计划与黄金标签一致'],
    ['参数准确率', metrics.arg_accuracy, '检索参数与解析条件一致'],
    ['Schema 合法', metrics.schema_valid_rate, '白名单工具 + 参数校验'],
    ['接地性', metrics.grounding_rate, '回答只使用卡片真实数值'],
    ['护栏', metrics.guardrail_accuracy, '注入拦截 + PII 脱敏'],
    ['整体通过', metrics.overall_pass_rate, `${metrics.query_cases} 查询 + ${metrics.guardrail_cases} 护栏`],
  ] as Array<[string, number, string]>
})
const costSessions = computed(() => costData.value?.sessions)
const costTools = computed(() => costData.value?.tools)
const costGuardrails = computed(() => costData.value?.guardrails)
const costProvider = computed(() => costData.value?.provider)
const quotaPct = computed(() => {
  const provider = costProvider.value
  if (!provider || !provider.limit) return 0
  return Math.min(100, Math.round((provider.used / provider.limit) * 100))
})
const dailyMax = computed(() => {
  const values = (costData.value?.daily ?? []).map((item) => item.sessions)
  return Math.max(1, ...values)
})

function statusClass(value: AgentSession['status']) {
  if (value === 'done') return 'tag-green'
  if (value === 'running') return 'tag-green'
  if (value === 'blocked') return 'tag-amber'
  return 'tag-coral'
}

function statusLabel(value: AgentSession['status']) {
  if (value === 'done') return '完成'
  if (value === 'running') return '运行中'
  if (value === 'blocked') return '预算拦截'
  return '失败'
}

function planClass(value: string) {
  if (value === 'done') return 'bg-forest text-white'
  if (value === 'now') return 'border border-forest text-forest'
  if (value === 'failed') return 'bg-coral-soft text-coral'
  return 'bg-sand text-faint'
}

function openTrace(session: AgentSession) {
  selected.value = session
}

function num(value: number | null | undefined) {
  return value == null ? '—' : value.toLocaleString('zh-CN')
}

function money(value: number | null | undefined) {
  return value == null ? '—' : `¥${value.toFixed(4)}`
}

function signalClass(value: number) {
  return value >= 0.95 ? 'text-forest' : value >= 0.85 ? 'text-amber' : 'text-coral'
}
</script>

<template>
  <div>
    <h2 class="text-[20px] font-bold tracking-tight">Agent 监控</h2>
    <p class="mt-1 text-[12.5px] text-muted">每一次找房会话的计划、工具调用、护栏与成本都来自真实记录；评测集是确定性规则基线，不调用外部模型。</p>
    <div class="mt-3 rounded-xl border border-forest/15 bg-forest-soft/60 px-3.5 py-2.5 text-[11px] leading-5 text-forest">
      <b>P1 运行时：</b>白名单只读工具（检索/详情/对比/通勤/价格）+ 显式保存监控；预算硬停、PII 脱敏、注入拦截；每次工具调用落 <code>agent_tool_calls</code>，可回放。视觉标签已接 OpenCode Go（默认关闭）；LLM-as-judge 未接入，不做。
    </div>

    <div class="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
      <AdminKpi label="会话总数" :value="totalSessions" :sub="`运行中 ${runningSessions}`" />
      <AdminKpi label="完成推荐" :value="`${doneSessions} / ${totalSessions}`" :sub="totalSessions ? `${Math.round((doneSessions / totalSessions) * 100)}%` : '—'" tone="green" />
      <AdminKpi label="预算拦截" :value="blockedSessions" sub="未调外部模型" tone="coral" />
      <AdminKpi label="平均耗时" :value="avgLatency" sub="真实会话" />
      <AdminKpi label="工具调用" :value="toolCallCount" sub="含失败步骤" />
      <AdminKpi label="评测通过" :value="passRate" sub="规则基线" tone="green" />
    </div>

    <AppTabs v-model="tab" :tabs="tabs" class="mt-4" />

    <!-- Trace -->
    <div v-if="tab === 'trace'" class="mt-4">
      <section class="card p-4">
        <h3 class="panel-title">会话列表 <span class="hint">点行看 trace</span></h3>
        <div class="mt-3 flex flex-wrap items-center gap-2">
          <input v-model="q" type="search" class="input w-[190px]" placeholder="搜索会话 / 需求" />
          <select v-model="status" class="input w-[130px]">
            <option value="all">全部状态</option>
            <option value="done">完成</option>
            <option value="running">运行中</option>
            <option value="blocked">预算拦截</option>
            <option value="failed">失败</option>
          </select>
          <span class="ml-auto text-[11px] text-faint">{{ filtered.length }} 条</span>
        </div>
        <div class="mt-3 overflow-x-auto">
          <table class="w-full text-left text-[12px]">
            <thead class="border-b border-line bg-paper2 text-[10px] uppercase tracking-wide text-faint">
              <tr>
                <th class="px-3 py-2.5 font-semibold">会话</th>
                <th class="px-3 py-2.5 font-semibold">需求</th>
                <th class="px-3 py-2.5 font-semibold">阶段</th>
                <th class="px-3 py-2.5 font-semibold">候选</th>
                <th class="px-3 py-2.5 font-semibold">工具</th>
                <th class="px-3 py-2.5 font-semibold">模型</th>
                <th class="px-3 py-2.5 font-semibold">耗时</th>
                <th class="px-3 py-2.5 font-semibold">状态</th>
                <th class="px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in filtered"
                :key="item.id"
                class="cursor-pointer border-b border-line transition last:border-0 hover:bg-paper2"
                @click="openTrace(item)"
              >
                <td class="mono px-3 py-2.5">{{ item.id }}</td>
                <td class="max-w-[240px] truncate px-3 py-2.5 font-semibold">{{ item.query }}</td>
                <td class="px-3 py-2.5 text-muted">{{ item.stage }}</td>
                <td class="mono px-3 py-2.5">{{ item.cand }}</td>
                <td class="mono px-3 py-2.5">{{ item.toolCalls?.length ?? item.tools }}</td>
                <td class="px-3 py-2.5 text-muted">{{ item.fallback ? '规则兜底' : item.model || '规则版' }}</td>
                <td class="mono px-3 py-2.5">{{ item.latency }}</td>
                <td class="px-3 py-2.5">
                  <span :class="statusClass(item.status)">
                    <span v-if="item.status === 'running'" class="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-forest" />
                    {{ statusLabel(item.status) }}
                  </span>
                </td>
                <td class="px-3 py-2.5">
                  <button class="btn-ghost btn-sm" @click.stop="openTrace(item)">Trace</button>
                </td>
              </tr>
              <tr v-if="loading">
                <td colspan="9" class="px-4 py-8 text-center text-[11.5px] text-faint">会话加载中…</td>
              </tr>
              <tr v-else-if="loadError">
                <td colspan="9" class="px-4 py-8 text-center text-[11.5px] text-coral">
                  {{ loadError }}
                  <button class="btn-ghost btn-sm ml-2" @click="loadSessions">重试</button>
                </td>
              </tr>
              <tr v-else-if="!filtered.length">
                <td colspan="9" class="px-4 py-8 text-center text-[11.5px] text-faint">暂无会话；在用户端发起一次找房即可看到真实 trace。</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <div class="rounded-xl border border-line bg-paper2 px-3 py-2 text-[10.5px] leading-5 text-muted">
            工具只读；<b class="text-ink">save_monitor</b> 仅在明确“保存/监控”时由规则路径调用。
          </div>
          <div class="rounded-xl border border-line bg-paper2 px-3 py-2 text-[10.5px] leading-5 text-muted">
            注入拦截会话 <b class="text-ink">{{ injectionBlocks }}</b> 个：不送外部模型，只走规则。
          </div>
          <div class="rounded-xl border border-line bg-paper2 px-3 py-2 text-[10.5px] leading-5 text-muted">
            预算拦截会让会话状态变为 <b class="text-ink">blocked</b>，SSE 仍返回规则版结果。
          </div>
          <div class="rounded-xl border border-line bg-paper2 px-3 py-2 text-[10.5px] leading-5 text-muted">
            trace 每次调用都记录参数、耗时、摘要与错误，可在右侧抽屉回放。
          </div>
        </div>
      </section>
    </div>

    <!-- Evals -->
    <div v-else-if="tab === 'evals'" class="mt-4">
      <div v-if="evalLoading" class="rounded-xl border border-line bg-paper2 px-3.5 py-3 text-[11px] text-muted">评测数据加载中…</div>
      <div v-else-if="evalError" class="rounded-xl border border-coral/25 bg-coral-soft px-3.5 py-3 text-[11px] text-coral">{{ evalError }}</div>
      <template v-else>
        <section class="card p-4">
          <div class="flex flex-wrap items-center gap-2">
            <h3 class="panel-title">黄金集回归</h3>
            <span class="tag-neutral">{{ evalData?.dataset_version }} · {{ evalData?.dataset_cases }} 条</span>
            <span class="tag-neutral">规则基线 · 不调模型</span>
            <button class="btn btn-sm ml-auto" :disabled="running" @click="runEval">
              <Loader2 v-if="running" :size="13" class="animate-spin" />
              {{ running ? '运行中…' : '运行基线评测' }}
            </button>
          </div>
          <div v-if="!latestEval" class="mt-4 rounded-xl border border-dashed border-line px-4 py-10 text-center text-[12px] text-faint">
            还没有评测记录。点击“运行基线评测”生成第一份可回归基线。
          </div>
          <template v-else>
            <div class="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-muted">
              <span class="tag-green">{{ latestEval.passed }} / {{ latestEval.total }} 通过</span>
              <span>{{ new Date(latestEval.created_at).toLocaleString('zh-CN') }}</span>
              <span>耗时 {{ latestEval.duration_ms }}ms</span>
              <span>版本 {{ latestEval.version }}</span>
            </div>
            <div class="mt-3 grid grid-cols-2 gap-2 lg:grid-cols-4">
              <div v-for="card in evalCards" :key="card[0]" class="rounded-xl border border-line bg-paper2 px-3 py-2.5">
                <div class="text-[10px] text-muted">{{ card[0] }}</div>
                <div class="mt-0.5 text-[20px] font-bold" :class="signalClass(card[1])">{{ Math.round(card[1] * 100) }}%</div>
                <div class="text-[9px] leading-4 text-faint">{{ card[2] }}</div>
              </div>
            </div>
          </template>
        </section>

        <div class="mt-4 grid gap-4 xl:grid-cols-2">
          <section class="card p-4">
            <h3 class="panel-title">历史回归 <span class="hint">最近 10 次</span></h3>
            <div v-if="evalData?.history?.length" class="mt-2 divide-y divide-line text-[11.5px]">
              <div v-for="item in evalData.history" :key="item.id" class="flex items-center gap-3 py-2">
                <span class="mono text-faint">#{{ item.id }}</span>
                <span>{{ item.version }} · {{ item.mode }}</span>
                <span class="ml-auto" :class="item.passed === item.total ? 'text-forest' : 'text-amber'">{{ item.passed }} / {{ item.total }}</span>
              </div>
            </div>
            <div v-else class="mt-3 rounded-xl border border-line bg-paper2 px-3 py-3 text-[11px] text-faint">暂无历史记录。</div>
            <div class="mt-3 rounded-xl border border-line bg-paper2 px-3.5 py-2.5 text-[10.5px] leading-5 text-muted">
              评测覆盖 {{ evalData?.dataset_cases ?? '—' }} 条，其中查询 {{ evalMetrics?.query_cases ?? '—' }}、护栏 {{ evalMetrics?.guardrail_cases ?? '—' }}；指标包含意图、字段、工具、参数、Schema、接地和护栏。LLM 在线打分未接入，页面不展示编造的 judge 分数。
            </div>
          </section>

          <section class="card p-4">
            <h3 class="panel-title">失败样例 <span class="hint">按用例 ID 回归</span></h3>
            <div v-if="failedCases.length" class="mt-2 divide-y divide-line text-[11.5px]">
              <div v-for="item in failedCases" :key="item.id" class="py-2">
                <div class="flex items-center gap-2">
                  <span class="mono text-faint">{{ item.id }}</span>
                  <span class="tag-coral">{{ item.kind === 'query' ? '查询' : '护栏' }}</span>
                </div>
                <div class="mt-1 text-muted">{{ item.message }}</div>
              </div>
            </div>
            <div v-else class="mt-3 rounded-xl border border-forest/15 bg-forest-soft/60 px-3.5 py-3 text-[11px] text-forest">
              当前基线全部通过；新增失败会在这里逐条列出，并保留完整 details 供定位。
            </div>
          </section>
        </div>
      </template>
    </div>

    <!-- Cost -->
    <div v-else-if="tab === 'cost'" class="mt-4">
      <div v-if="costLoading" class="rounded-xl border border-line bg-paper2 px-3.5 py-3 text-[11px] text-muted">成本数据加载中…</div>
      <div v-else-if="costError" class="rounded-xl border border-coral/25 bg-coral-soft px-3.5 py-3 text-[11px] text-coral">{{ costError }}</div>
      <template v-else-if="costData">
        <div class="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
          <AdminKpi label="近 7 天会话" :value="num(costSessions?.total)" :sub="`完成 ${costSessions?.done ?? 0}`" />
          <AdminKpi label="Token" :value="num((costSessions?.prompt_tokens ?? 0) + (costSessions?.completion_tokens ?? 0))" :sub="`输入 ${num(costSessions?.prompt_tokens)}`" />
          <AdminKpi label="模型成本" :value="money(costSessions?.cost)" sub="免费额度 · 仅计 token" tone="green" />
          <AdminKpi label="平均耗时" :value="`${((costSessions?.avg_latency_ms ?? 0) / 1000).toFixed(1)}s`" sub="会话端到端" />
          <AdminKpi label="规则兜底" :value="`${Math.round((costSessions?.fallback_rate ?? 0) * 100)}%`" :sub="`${costSessions?.fallback ?? 0} 个会话`" tone="amber" />
          <AdminKpi label="预算拦截" :value="num(costSessions?.blocked)" sub="未调外部模型" tone="coral" />
        </div>

        <div class="mt-4 grid gap-4 xl:grid-cols-2">
          <section class="card p-4">
            <h3 class="panel-title">模型额度 <span class="hint">今日 · 硬停</span></h3>
            <div class="mt-3 flex items-end justify-between text-[11px] text-muted">
              <span>{{ costProvider?.model }}</span>
              <span class="mono text-ink">{{ costProvider?.used }} / {{ costProvider?.limit }}</span>
            </div>
            <div class="mt-1 h-1.5 overflow-hidden rounded-full bg-sand">
              <div class="h-full rounded-full" :class="quotaPct > 80 ? 'bg-coral' : 'bg-forest'" :style="{ width: `${quotaPct}%` }" />
            </div>
            <div class="mt-3 divide-y divide-line text-[11.5px]">
              <div class="flex items-center py-2"><span>剩余额度</span><b class="ml-auto">{{ costProvider?.remaining ?? '—' }}</b></div>
              <div class="flex items-center py-2"><span>近 7 天调用</span><b class="ml-auto">{{ num(costProvider?.calls) }}</b></div>
              <div class="flex items-center py-2"><span>调用失败</span><b class="ml-auto">{{ num(costProvider?.errors) }}</b></div>
              <div class="flex items-center py-2"><span>平均延迟</span><b class="ml-auto">{{ num(costProvider?.avg_latency_ms) }}ms</b></div>
              <div class="flex items-center py-2"><span>图片 / 视觉模型</span><span class="ml-auto tag-neutral">未调用</span></div>
            </div>
            <div class="mt-2 rounded-xl border border-line bg-paper2 px-3.5 py-2.5 text-[10.5px] leading-5 text-muted">
              调用前检查 <code>aiDailyCap</code>；额度不足直接返回规则版并把会话标记为预算拦截，不发出请求。
            </div>
          </section>

          <section class="card p-4">
            <h3 class="panel-title">工具与护栏 <span class="hint">近 7 天</span></h3>
            <div class="mt-3 grid grid-cols-2 gap-2">
              <div class="rounded-xl border border-line bg-paper2 px-3 py-2.5"><div class="text-[10px] text-muted">工具调用</div><div class="text-[18px] font-bold">{{ num(costTools?.calls) }}</div><div class="text-[9px] text-faint">平均 {{ num(costTools?.avg_latency_ms) }}ms · 成功率 {{ costTools?.success_rate == null ? '—' : `${Math.round(costTools.success_rate * 100)}%` }}</div></div>
              <div class="rounded-xl border border-line bg-paper2 px-3 py-2.5"><div class="text-[10px] text-muted">工具失败</div><div class="text-[18px] font-bold">{{ num(costTools?.errors) }}</div><div class="text-[9px] text-faint">参数/占位/数据缺失</div></div>
              <div class="rounded-xl border border-line bg-paper2 px-3 py-2.5"><div class="text-[10px] text-muted">注入拦截</div><div class="text-[18px] font-bold">{{ num(costGuardrails?.injection_blocks) }}</div><div class="text-[9px] text-faint">未送外部模型</div></div>
              <div class="rounded-xl border border-line bg-paper2 px-3 py-2.5"><div class="text-[10px] text-muted">PII 脱敏</div><div class="text-[18px] font-bold">{{ num(costGuardrails?.pii_masked) }}</div><div class="text-[9px] text-faint">手机号/邮箱/身份证</div></div>
            </div>
            <h3 class="panel-title mt-4">每日会话</h3>
            <div v-if="costData.daily.length" class="mt-2 flex items-end gap-1.5">
              <div v-for="item in costData.daily" :key="item.date" class="flex-1 text-center">
                <div class="mx-auto w-full rounded-t bg-forest/70" :style="{ height: `${Math.max(4, Math.round((item.sessions / dailyMax) * 56))}px` }" />
                <div class="mt-1 text-[9px] text-faint">{{ item.date }}</div>
              </div>
            </div>
            <div v-else class="mt-2 rounded-xl border border-line bg-paper2 px-3 py-3 text-[10.5px] text-faint">暂无会话数据。</div>
          </section>
        </div>
      </template>
    </div>

    <!-- Ops / limitations -->
    <div v-else class="mt-4 grid gap-4 xl:grid-cols-2">
      <section class="card p-4">
        <h3 class="panel-title">已接入</h3>
        <div class="mt-3 divide-y divide-line text-[11.5px]">
          <div class="flex items-center py-2"><span>规则版 + LLM 严格 JSON 计划</span><span class="ml-auto tag-green">已接入</span></div>
          <div class="flex items-center py-2"><span>只读工具白名单（5 个）</span><span class="ml-auto tag-green">已接入</span></div>
          <div class="flex items-center py-2"><span>保存监控（显式意图）</span><span class="ml-auto tag-green">已接入</span></div>
          <div class="flex items-center py-2"><span>预算硬停 / PII / 注入护栏</span><span class="ml-auto tag-green">已接入</span></div>
          <div class="flex items-center py-2"><span>工具 trace 持久化</span><span class="ml-auto tag-green">已接入</span></div>
          <div class="flex items-center py-2"><span>{{ evalData?.dataset_cases ?? '—' }} 条规则回归集</span><span class="ml-auto tag-green">已接入</span></div>
        </div>
      </section>
      <section class="card p-4">
        <h3 class="panel-title">明确未接入 <span class="hint">不展示假数据</span></h3>
        <div class="mt-3 space-y-2 text-[11px] leading-5 text-muted">
          <p><b class="text-ink">LLM 在线 judge：</b>需要单独模型与预算，本页只展示确定性基线，不伪造 groundedness 分数。</p>
          <p><b class="text-ink">视觉分析：</b>OpenCode Go 视觉标签已接，`APP_IMAGE_VISION_ENABLED` 默认关闭；关闭时图片页只做 dHash + 本地信号。</p>
          <p><b class="text-ink">自动下单/外部写操作：</b>永久禁用；工具层没有该能力。</p>
          <p><b class="text-ink">告警：</b>飞书告警/冷却/恢复通知已接；恢复演练尚未执行，不在此页画绿灯。</p>
        </div>
      </section>
    </div>

    <AppDrawer
      :open="!!selected"
      :title="selected?.id || '会话 Trace'"
      :subtitle="selected?.query || ''"
      @close="selected = null"
    >
      <template v-if="selected">
        <div class="flex flex-wrap gap-1.5">
          <span :class="statusClass(selected.status)">{{ statusLabel(selected.status) }}</span>
          <span class="tag-neutral">{{ selected.stage }}</span>
          <span class="tag-neutral">{{ selected.latency }}</span>
          <span class="tag-neutral">{{ selected.fallback ? '规则兜底' : selected.model || '规则版' }}</span>
          <span class="tag-neutral">{{ selected.toolCalls?.length ?? 0 }} 次工具</span>
          <span class="tag-neutral">{{ selected.promptTokens ?? 0 }} + {{ selected.completionTokens ?? 0 }} tok</span>
        </div>

        <h3 class="panel-title mt-4">计划</h3>
        <div class="mt-2 space-y-1.5">
          <div v-for="(step, index) in selected.plan" :key="index" class="flex items-start gap-2 rounded-lg border border-line bg-paper2 px-2.5 py-2">
            <span class="mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full text-[9px]" :class="planClass(step[2])">
              <Check v-if="step[2] === 'done'" :size="10" />
              <Circle v-else-if="step[2] === 'now'" :size="8" />
              <X v-else-if="step[2] === 'failed'" :size="10" />
            </span>
            <div class="min-w-0 flex-1">
              <div class="text-[11.5px] font-semibold">{{ step[0] }}</div>
              <div class="text-[10px] leading-4 text-muted">{{ step[1] }}</div>
            </div>
            <span class="mono text-[9px] text-faint">{{ step[3] }}</span>
          </div>
          <div v-if="!selected.plan?.length" class="text-[11px] text-faint">无计划记录。</div>
        </div>

        <h3 class="panel-title mt-4">工具调用</h3>
        <div class="mt-2 overflow-x-auto">
          <table class="w-full text-left text-[10.5px]">
            <thead class="border-b border-line text-[9px] uppercase tracking-wide text-faint">
              <tr><th class="py-2 font-semibold">步骤</th><th class="py-2 font-semibold">工具</th><th class="py-2 font-semibold">参数</th><th class="py-2 font-semibold">结果</th><th class="py-2 font-semibold">耗时</th></tr>
            </thead>
            <tbody>
              <tr v-for="call in selected.toolCalls" :key="call.step" class="border-b border-line last:border-0">
                <td class="py-2 align-top text-faint">{{ call.step }}</td>
                <td class="py-2 align-top font-semibold">{{ call.tool }}</td>
                <td class="mono max-w-[150px] py-2 align-top text-muted">{{ JSON.stringify(call.args) }}</td>
                <td class="py-2 align-top" :class="call.status === 'ok' ? 'text-muted' : 'text-coral'">{{ call.error || call.summary }}</td>
                <td class="mono py-2 align-top text-faint">{{ call.latency }}</td>
              </tr>
              <tr v-if="!selected.toolCalls?.length">
                <td colspan="5" class="py-4 text-center text-faint">本次会话未记录工具调用（旧会话或纯文本路径）。</td>
              </tr>
            </tbody>
          </table>
        </div>

        <h3 class="panel-title mt-4">护栏</h3>
        <div class="mt-2 space-y-1.5">
          <div v-for="(guard, index) in selected.guardrails" :key="index" class="rounded-lg border border-line bg-paper2 px-2.5 py-2 text-[10.5px]">
            <div class="flex items-center gap-2">
              <span class="tag-neutral">{{ guard.stage }}</span>
              <span class="text-muted">{{ guard.summary || guard.blocked || '通过' }}</span>
              <span v-if="guard.used != null" class="mono ml-auto text-faint">{{ guard.used }} / {{ guard.limit ?? '—' }}</span>
            </div>
            <div v-if="guard.injections?.length" class="mt-1 text-coral">注入：{{ guard.injections.join('、') }}</div>
            <div v-if="guard.pii_hits" class="mt-1 text-amber">已脱敏 {{ guard.pii_hits }} 处 PII（未送外部模型）</div>
          </div>
          <div v-if="!selected.guardrails?.length" class="text-[11px] text-faint">旧会话没有护栏记录。</div>
        </div>

        <h3 class="panel-title mt-4">回答</h3>
        <p class="mt-2 rounded-xl border border-line bg-paper2 px-3 py-2.5 text-[11px] leading-5 text-muted">{{ selected.result || '—' }}</p>
        <div class="mt-3 flex gap-2">
          <button class="btn-ghost btn-sm" @click="annotate(selected.id, 'reviewed')">标记已复核</button>
          <button class="btn-ghost btn-sm" @click="annotate(selected.id, 'dataset')">加入评测集</button>
        </div>
      </template>
    </AppDrawer>
  </div>
</template>
