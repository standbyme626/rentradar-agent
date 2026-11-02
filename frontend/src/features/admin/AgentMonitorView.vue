<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Check, Circle, Loader2, X } from 'lucide-vue-next'
import type { AgentSession } from '@/api/types'
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
onMounted(loadSessions)

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
  { key: 'ops', label: '版本与告警' },
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
const avgAmap = computed(() => {
  const values = sessions.value.map((item) => Number(item.amap)).filter(Number.isFinite)
  return values.length ? (values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(1) : '—'
})
const avgLatency = computed(() => {
  const values = sessions.value
    .map((item) => Number.parseFloat(String(item.latency)))
    .filter(Number.isFinite)
  return values.length ? `${(values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(1)}s` : '—'
})

const spans = [
  { label: 'LLM 规划', left: 0, width: 14, type: 'llm', time: '1.1s' },
  { label: 'search_listings', left: 14, width: 1, type: 'io', time: '12ms' },
  { label: 'commute ×6', left: 15, width: 36, type: 'tool', time: '4.1s' },
  { label: 'fetch_detail ×3', left: 51, width: 30, type: 'io', time: '5.2s' },
  { label: 'analyze_images ×3', left: 81, width: 8, type: 'tool', time: '1.2s' },
  { label: 'LLM 汇总', left: 89, width: 11, type: 'llm', time: '0.9s' },
]

const evalCards = [
  { name: 'Groundedness', score: '0.92', note: '阈值 0.85 · 9/9 通过', state: 'ok' },
  { name: '答案相关性', score: '0.88', note: '阈值 0.80 · 8/9 通过', state: 'ok' },
  { name: '工具正确性', score: '0.96', note: '阈值 0.90 · 9/9 通过', state: 'ok' },
  { name: '参数正确性', score: '0.84', note: '阈值 0.90 · 1 次预算参数错误', state: 'warn' },
  { name: '计划质量', score: '0.86', note: '阈值 0.85 · 1 次冗余调用', state: 'warn' },
  { name: '安全性', score: '1.00', note: '无违规 · 无自动下单', state: 'ok' },
]

const funnel = [
  ['12', '会话'],
  ['9', '完成推荐'],
  ['7', '打开详情'],
  ['5', '对比'],
  ['2', '保存监控'],
  ['1', '联系'],
]

const reviews = [
  ['S-1035', '证据不足 · 只有封面', '0.71', '待复核'],
  ['S-1032', '负反馈 · 通勤太长', '0.78', '待复核'],
  ['S-1028', '工具参数错误', '0.84', '已复核'],
]

const toolReliability = [
  ['commute', '18', '1 timeout', '1 成功', '620ms', '38%', '正常'],
  ['poi', '6', '0', '0', '210ms', '67%', '正常'],
  ['fetch_detail', '9', '1 403', '回退封面', '2.1s', '0%', '部分'],
  ['analyze_images', '0', '—', '—', '—', '—', '未接入'],
]

const versions = [
  ['agent v0.3.2 / prompt v7', '12', '75%', '14.2s', '0.91', '¥0.010', '当前'],
  ['agent v0.3.1 / prompt v6', '48', '67%', '16.8s', '0.86', '¥0.012', '上一版'],
]

const slos = [
  ['可用性', '99.6%'],
  ['p95 端到端', '< 15s'],
  ['任务成功率', '> 70%'],
  ['Groundedness', '> 0.85'],
  ['工具错误率', '< 5%'],
  ['单会话成本', '< ¥0.05'],
]

const alertRules = [
  ['工具错误率', '> 10% / 1h', '飞书', '正常'],
  ['p95 端到端', '> 20s / 15min', '飞书', '正常'],
  ['Groundedness', '< 0.80 / 24h', '飞书 + 邮件', '1 次'],
  ['单会话高德', '> 15 次', '硬停止', '生效'],
  ['月度高德', '> 80%（4000）', '飞书', '正常'],
  ['负反馈率', '> 20% / 24h', '飞书', '正常'],
]

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
</script>

<template>
  <div>
    <h2 class="text-[20px] font-bold tracking-tight">Agent 监控</h2>
    <p class="mt-1 text-[12.5px] text-muted">看每一次找房会话：计划、工具调用、预算、推荐和反馈。规则版 Agent 已接入，会话来自真实后端。</p>
    <div class="mt-3 rounded-xl border border-forest/15 bg-forest-soft/60 px-3.5 py-2.5 text-[11px] leading-5 text-forest">
      <b>Phase 3：</b>规则版 Agent 已接入；会话、Trace、工具为真实记录，评测/成本/护栏面板仍为设计预览。
    </div>

    <div class="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
      <AdminKpi label="会话总数" :value="totalSessions" :sub="`运行中 ${runningSessions}`" />
      <AdminKpi label="完成推荐" :value="`${doneSessions} / ${totalSessions}`" :sub="totalSessions ? `${Math.round((doneSessions / totalSessions) * 100)}%` : '—'" tone="green" />
      <AdminKpi label="平均耗时" :value="avgLatency" sub="真实会话" />
      <AdminKpi label="平均高德" :value="`${avgAmap} 次`" sub="单会话上限 15" tone="amber" />
      <AdminKpi label="预算拦截" :value="blockedSessions" sub="未调外部接口" tone="coral" />
      <AdminKpi label="用户采纳" value="—" sub="埋点待接入" />
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
                <th class="px-3 py-2.5 font-semibold">高德</th>
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
                <td class="px-3 py-2.5 font-semibold">{{ item.query }}</td>
                <td class="px-3 py-2.5 text-muted">{{ item.stage }}</td>
                <td class="mono px-3 py-2.5">{{ item.cand }}</td>
                <td class="mono px-3 py-2.5">{{ item.tools }}</td>
                <td class="mono px-3 py-2.5">{{ item.amap }}</td>
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
                <td colspan="9" class="px-4 py-8 text-center text-[11.5px] text-faint">
                  暂无 Agent 会话；Phase 3 接入运行时后显示。
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="mt-3 rounded-xl border border-forest/15 bg-forest-soft/60 px-3.5 py-2.5 text-[10.5px] leading-5 text-forest">
          成功会话的典型路径：本地检索 0 次外部调用 → 只对 6 套算通勤 → 只对 3 套抓详情 → 推荐 3 套。预算拦截的会话完全不调外部接口。
        </div>
      </section>

      <div class="mt-4 grid gap-4 xl:grid-cols-2">
        <section class="card p-4">
          <h3 class="panel-title">预算与护栏</h3>
          <div class="mt-2 text-[11px] text-muted">单会话高德 <b class="float-right text-ink">7.2 / 15</b></div>
          <div class="mt-1 h-1.5 overflow-hidden rounded-full bg-sand"><div class="h-full w-[48%] rounded-full bg-forest" /></div>
          <div class="mt-3 text-[11px] text-muted">本月高德 <b class="float-right text-ink">876 / 5000</b></div>
          <div class="mt-1 h-1.5 overflow-hidden rounded-full bg-sand"><div class="h-full w-[17.5%] rounded-full bg-amber" /></div>
          <div class="mt-2 divide-y divide-line text-[11.5px]">
            <div class="flex items-center py-2"><span>自动下单</span><span class="ml-auto tag-green">禁用</span></div>
            <div class="flex items-center py-2"><span>工具白名单</span><span class="ml-auto tag-neutral">6 / 8</span></div>
            <div class="flex items-center py-2"><span>超限拦截</span><span class="ml-auto tag-amber">2 次</span></div>
            <div class="flex items-center py-2"><span>图片/AI 调用</span><span class="ml-auto tag-neutral">未接入</span></div>
          </div>
        </section>

        <section class="card p-4">
          <h3 class="panel-title">今日工具调用</h3>
          <div class="mt-2 divide-y divide-line text-[11px]">
            <div v-for="item in [
              ['search_listings', '本地检索 · 0 外部', '24'],
              ['commute', '高德 · 缓存 38%', '18'],
              ['poi', '高德 · 缓存 67%', '6'],
              ['fetch_detail', 'CDP · 候选 only', '9'],
              ['analyze_images', '未接入', '0'],
              ['save_monitor', '飞书 · 本地', '3'],
            ]" :key="item[0]" class="flex items-center gap-3 py-2">
              <span class="w-[105px] font-semibold text-ink">{{ item[0] }}</span>
              <span class="flex-1 text-muted">{{ item[1] }}</span>
              <span class="mono text-faint">{{ item[2] }}</span>
            </div>
          </div>
        </section>

        <section class="card p-4">
          <h3 class="panel-title">反馈与质量</h3>
          <div class="mt-2 divide-y divide-line text-[11.5px]">
            <div class="flex items-center py-2"><span>推荐采纳</span><b class="ml-auto">4 / 9</b></div>
            <div class="flex items-center py-2"><span>详情打开</span><b class="ml-auto">7</b></div>
            <div class="flex items-center py-2"><span>对比</span><b class="ml-auto">5</b></div>
            <div class="flex items-center py-2"><span>保存监控</span><b class="ml-auto">2</b></div>
            <div class="flex items-center py-2"><span>负反馈</span><span class="ml-auto tag-amber">1 · 通勤太长</span></div>
            <div class="flex items-center py-2"><span>低置信</span><span class="ml-auto tag-amber">1 · 证据不足</span></div>
          </div>
        </section>

        <section class="card p-4">
          <h3 class="panel-title">保存的监控</h3>
          <div class="mt-2 divide-y divide-line text-[11.5px]">
            <div class="flex items-center py-2"><span>5 号线 · ≤4500 · 通勤≤40</span><span class="ml-auto tag-green">新 2</span></div>
            <div class="flex items-center py-2"><span>龙岗 · 3000 · 两居</span><span class="ml-auto tag-neutral">新 0</span></div>
            <div class="flex items-center py-2"><span>会展中心 · 步行接驳</span><span class="ml-auto tag-green">新 1</span></div>
          </div>
        </section>
      </div>

      <section class="card mt-4 p-4">
        <h3 class="panel-title">Trace 示例 · S-1042 <span class="hint">8.1s · 9 次工具 · 3 次 LLM</span></h3>
        <div class="mt-3 space-y-2">
          <div v-for="span in spans" :key="span.label" class="grid grid-cols-[120px_1fr_44px] items-center gap-2 text-[10.5px]">
            <span class="truncate text-muted">{{ span.label }}</span>
            <div class="relative h-[18px] overflow-hidden rounded border border-line bg-paper2">
              <div
                class="absolute inset-y-0 rounded-sm opacity-80"
                :class="span.type === 'llm' ? 'bg-amber' : span.type === 'io' ? 'bg-[#8aa7b3]' : 'bg-forest'"
                :style="{ left: `${span.left}%`, width: `${span.width}%` }"
              />
            </div>
            <span class="mono text-right text-faint">{{ span.time }}</span>
          </div>
        </div>
        <div class="mt-3 rounded-xl border border-line bg-paper2 px-3.5 py-2.5 text-[10.5px] leading-5 text-muted">
          LLM：Qwen2.5-72B · 3.2k in / 1.1k out · cached 1.8k · ¥0.012 · TTFT 0.6s。工具：9 次调用，2 次缓存命中；高德 7 次，图片 AI 0 次（未接入）。
        </div>
      </section>
    </div>

    <!-- Evals -->
    <div v-else-if="tab === 'evals'" class="mt-4">
      <div class="grid gap-4 xl:grid-cols-2">
        <section class="card p-4">
          <h3 class="panel-title">在线评测 <span class="hint">LLM-as-judge · 每次会话</span></h3>
          <div class="mt-3 grid grid-cols-2 gap-2 lg:grid-cols-3">
            <div v-for="item in evalCards" :key="item.name" class="rounded-xl border border-line bg-paper2 px-3 py-2.5">
              <div class="text-[10px] text-muted">{{ item.name }}</div>
              <div class="mt-0.5 text-[20px] font-bold" :class="item.state === 'ok' ? 'text-forest' : 'text-amber'">{{ item.score }}</div>
              <div class="text-[9px] leading-4 text-faint">{{ item.note }}</div>
            </div>
          </div>
          <div class="mt-3 rounded-xl border border-forest/15 bg-forest-soft/60 px-3.5 py-2.5 text-[10.5px] leading-5 text-forest">
            评测对象是 trace，不是最终文案：工具选择、参数、证据、计划都要单独打分。
          </div>
        </section>

        <section class="card p-4">
          <h3 class="panel-title">业务结果漏斗 <span class="hint">{{ totalSessions }} 个会话</span></h3>
          <div class="mt-3 flex overflow-hidden rounded-xl border border-line">
            <div v-for="(step, index) in funnel" :key="step[1]" class="flex-1 border-r border-line bg-paper2 px-2 py-2.5 text-center last:border-r-0">
              <div class="text-[17px] font-bold leading-5">{{ step[0] }}</div>
              <div class="text-[9px] text-muted">{{ step[1] }}</div>
            </div>
          </div>
          <div class="mt-3 rounded-xl border border-line bg-paper2 px-3.5 py-2.5 text-[10.5px] leading-5 text-muted">
            从“推荐”到“打开详情”的转化 78%；从“对比”到“保存监控”只有 40%，说明对比页的决策信息还不够。
          </div>
        </section>
      </div>

      <div class="mt-4 grid gap-4 xl:grid-cols-2">
        <section class="card p-4">
          <h3 class="panel-title">人工复核队列 <span class="hint">采样 10% · 2 条待处理</span></h3>
          <table class="mt-2 w-full text-left text-[11.5px]">
            <thead class="border-b border-line text-[10px] uppercase tracking-wide text-faint">
              <tr><th class="py-2 font-semibold">会话</th><th class="py-2 font-semibold">原因</th><th class="py-2 font-semibold">评测分</th><th class="py-2 font-semibold">状态</th><th class="py-2" /></tr>
            </thead>
            <tbody>
              <tr v-for="row in reviews" :key="row[0]" class="border-b border-line last:border-0">
                <td class="mono py-2.5">{{ row[0] }}</td>
                <td class="py-2.5 text-muted">{{ row[1] }}</td>
                <td class="py-2.5">{{ row[2] }}</td>
                <td class="py-2.5"><span :class="row[3] === '已复核' ? 'tag-green' : 'tag-amber'">{{ row[3] }}</span></td>
                <td class="py-2.5"><button class="btn-ghost btn-sm" @click="annotate(row[0], row[3] === '已复核' ? 'dataset' : 'review')">{{ row[3] === '已复核' ? '加入评测集' : '复核' }}</button></td>
              </tr>
            </tbody>
          </table>
        </section>

        <section class="card p-4">
          <h3 class="panel-title">反馈闭环 <span class="hint">trace → 数据集 → 回归</span></h3>
          <div class="mt-3 flex flex-wrap items-center gap-1.5 text-[10.5px] text-muted">
            <span class="rounded-lg border border-line bg-paper2 px-2.5 py-1.5">生产 trace</span><span>→</span>
            <span class="rounded-lg border border-line bg-paper2 px-2.5 py-1.5">人工/自动打分</span><span>→</span>
            <span class="rounded-lg border border-line bg-paper2 px-2.5 py-1.5">失败样本入集</span><span>→</span>
            <span class="rounded-lg border border-forest bg-forest-soft px-2.5 py-1.5 text-forest">回归评测</span><span>→</span>
            <span class="rounded-lg border border-line bg-paper2 px-2.5 py-1.5">上线门槛</span>
          </div>
          <div class="mt-3 divide-y divide-line text-[11.5px]">
            <div class="flex items-center py-2"><span>评测集</span><b class="ml-auto">14 条</b></div>
            <div class="flex items-center py-2"><span>最近回归</span><b class="ml-auto">13 / 14 通过</b></div>
            <div class="flex items-center py-2"><span>回归门槛</span><span class="ml-auto tag-green">≥ 90%</span></div>
            <div class="flex items-center py-2"><span>用户反馈</span><b class="ml-auto">赞 3 · 踩 1</b></div>
          </div>
          <div class="mt-3 rounded-xl border border-line bg-paper2 px-3.5 py-2.5 text-[10.5px] leading-5 text-muted">
            没有评测的监控只是昂贵的日志；失败样本必须能回到评测集。
          </div>
        </section>
      </div>
    </div>

    <!-- Cost -->
    <div v-else-if="tab === 'cost'" class="mt-4">
      <div class="grid gap-4 xl:grid-cols-2">
        <section class="card p-4">
          <h3 class="panel-title">成本拆解 <span class="hint">今日</span></h3>
          <div class="mt-3 grid grid-cols-2 gap-2">
            <div class="rounded-xl border border-line bg-paper2 px-3 py-2.5"><div class="text-[10px] text-muted">LLM</div><div class="text-[20px] font-bold">¥0.12</div><div class="text-[9px] text-faint">42k in / 12k out</div></div>
            <div class="rounded-xl border border-line bg-paper2 px-3 py-2.5"><div class="text-[10px] text-muted">高德</div><div class="text-[20px] font-bold">86 次</div><div class="text-[9px] text-faint">本月 876/5000</div></div>
            <div class="rounded-xl border border-line bg-paper2 px-3 py-2.5"><div class="text-[10px] text-muted">图片 AI</div><div class="text-[20px] font-bold">0</div><div class="text-[9px] text-faint">未接入</div></div>
            <div class="rounded-xl border border-line bg-paper2 px-3 py-2.5"><div class="text-[10px] text-muted">单会话成本</div><div class="text-[20px] font-bold">¥0.010</div><div class="text-[9px] text-faint">12 会话</div></div>
          </div>
          <div class="mt-3 text-[10.5px] leading-5 text-muted">成本按 trace 汇总：LLM token + 外部 API + 图片/OCR；每个 span 记 estimated cost，会话结束做 rollup。</div>
          <div class="mt-3 h-1.5 overflow-hidden rounded-full bg-sand"><div class="h-full w-[17.5%] rounded-full bg-forest" /></div>
          <div class="mt-1 text-[9.5px] text-faint">本月高德 876 / 5000（17.5%）</div>
        </section>

        <section class="card p-4">
          <h3 class="panel-title">护栏与隐私 <span class="hint">执行前 / 执行中 / 输出</span></h3>
          <div class="mt-2 divide-y divide-line text-[11.5px]">
            <div class="flex items-center py-2"><span>输入 prompt injection 拦截</span><b class="ml-auto">1</b></div>
            <div class="flex items-center py-2"><span>PII 脱敏（地址/电话）</span><b class="ml-auto">12 条</b></div>
            <div class="flex items-center py-2"><span>最大步数 / 单会话</span><b class="ml-auto">12</b></div>
            <div class="flex items-center py-2"><span>高德 / 单会话</span><b class="ml-auto">15</b></div>
            <div class="flex items-center py-2"><span>自动下单</span><span class="ml-auto tag-green">禁用</span></div>
            <div class="flex items-center py-2"><span>付费模型</span><span class="ml-auto tag-green">禁用</span></div>
            <div class="flex items-center py-2"><span>工具白名单</span><b class="ml-auto">6 / 8</b></div>
            <div class="flex items-center py-2"><span>日志保留</span><b class="ml-auto">30 天</b></div>
          </div>
        </section>
      </div>

      <div class="mt-4 grid gap-4 xl:grid-cols-2">
        <section class="card p-4">
          <h3 class="panel-title">工具可靠性 <span class="hint">今日</span></h3>
          <table class="mt-2 w-full text-left text-[11.5px]">
            <thead class="border-b border-line text-[10px] uppercase tracking-wide text-faint">
              <tr><th class="py-2 font-semibold">工具</th><th class="py-2 font-semibold">调用</th><th class="py-2 font-semibold">错误</th><th class="py-2 font-semibold">重试</th><th class="py-2 font-semibold">p95</th><th class="py-2 font-semibold">缓存</th><th class="py-2 font-semibold">状态</th></tr>
            </thead>
            <tbody>
              <tr v-for="row in toolReliability" :key="row[0]" class="border-b border-line last:border-0">
                <td class="py-2.5 font-semibold">{{ row[0] }}</td><td class="py-2.5">{{ row[1] }}</td><td class="py-2.5">{{ row[2] }}</td><td class="py-2.5">{{ row[3] }}</td><td class="mono py-2.5">{{ row[4] }}</td><td class="py-2.5">{{ row[5] }}</td>
                <td class="py-2.5"><span :class="row[6] === '正常' ? 'tag-green' : row[6] === '部分' ? 'tag-amber' : 'tag-neutral'">{{ row[6] }}</span></td>
              </tr>
            </tbody>
          </table>
        </section>
        <section class="card p-4">
          <h3 class="panel-title">成本异常 <span class="hint">按会话</span></h3>
          <div class="mt-2 rounded-xl border border-line bg-paper2 px-3.5 py-2.5 text-[10.5px] leading-5 text-muted">
            S-1039 预算拦截：0 次外部调用，避免了一次无效高德；S-1041 8 次高德，是今日最高，但带来了保存监控。
          </div>
          <div class="mt-3 divide-y divide-line text-[11.5px]">
            <div class="flex items-center py-2"><span>最高单会话高德</span><b class="ml-auto">8 次 · S-1041</b></div>
            <div class="flex items-center py-2"><span>缓存节省</span><b class="ml-auto">约 6 次</b></div>
            <div class="flex items-center py-2"><span>本月额度风险</span><span class="ml-auto tag-green">低 · 17.5%</span></div>
          </div>
        </section>
      </div>
    </div>

    <!-- Ops -->
    <div v-else class="mt-4">
      <div class="grid gap-4 xl:grid-cols-2">
        <section class="card p-4">
          <h3 class="panel-title">版本与实验 <span class="hint">按版本对比</span></h3>
          <table class="mt-2 w-full text-left text-[11.5px]">
            <thead class="border-b border-line text-[10px] uppercase tracking-wide text-faint">
              <tr><th class="py-2 font-semibold">版本</th><th class="py-2 font-semibold">会话</th><th class="py-2 font-semibold">成功率</th><th class="py-2 font-semibold">p95</th><th class="py-2 font-semibold">评测分</th><th class="py-2 font-semibold">成本/会话</th><th class="py-2 font-semibold">状态</th></tr>
            </thead>
            <tbody>
              <tr v-for="row in versions" :key="row[0]" class="border-b border-line last:border-0">
                <td class="py-2.5 font-semibold">{{ row[0] }}</td><td class="py-2.5">{{ row[1] }}</td><td class="py-2.5">{{ row[2] }}</td><td class="py-2.5">{{ row[3] }}</td><td class="py-2.5">{{ row[4] }}</td><td class="py-2.5">{{ row[5] }}</td>
                <td class="py-2.5"><span :class="row[6] === '当前' ? 'tag-green' : 'tag-neutral'">{{ row[6] }}</span></td>
              </tr>
            </tbody>
          </table>
          <div class="mt-3 rounded-xl border border-forest/15 bg-forest-soft/60 px-3.5 py-2.5 text-[10.5px] leading-5 text-forest">
            prompt v7 把“只对候选算通勤”写进计划约束，成功率 +8pp；回归门槛 ≥90%，低于门槛不允许上线。
          </div>
        </section>
        <section class="card p-4">
          <h3 class="panel-title">SLO <span class="hint">Agent 服务</span></h3>
          <div class="mt-2 divide-y divide-line text-[11.5px]">
            <div v-for="row in slos" :key="row[0]" class="flex items-center py-2"><span>{{ row[0] }}</span><b class="ml-auto">{{ row[1] }}</b></div>
          </div>
        </section>
      </div>

      <section class="card mt-4 p-4">
        <h3 class="panel-title">告警规则 <span class="hint">质量优先，不只是存活</span></h3>
        <table class="mt-2 w-full text-left text-[11.5px]">
          <thead class="border-b border-line text-[10px] uppercase tracking-wide text-faint">
            <tr><th class="py-2 font-semibold">规则</th><th class="py-2 font-semibold">阈值</th><th class="py-2 font-semibold">通知</th><th class="py-2 font-semibold">状态</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in alertRules" :key="row[0]" class="border-b border-line last:border-0">
              <td class="py-2.5 font-semibold">{{ row[0] }}</td><td class="py-2.5">{{ row[1] }}</td><td class="py-2.5">{{ row[2] }}</td>
              <td class="py-2.5"><span :class="row[3] === '正常' || row[3] === '生效' ? 'tag-green' : 'tag-amber'">{{ row[3] }}</span></td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>

    <AppDrawer
      :open="!!selected"
      :title="selected ? `${selected.id} · Agent Trace` : 'Agent Trace'"
      :subtitle="selected ? `${selected.query} · ${selected.stage}` : ''"
      @close="selected = null"
    >
      <template v-if="selected">
        <div class="rounded-xl border border-line bg-paper2 px-3.5 py-3 text-[11px] leading-6 text-muted">
          <b class="text-ink">{{ selected.query }}</b><br />
          {{ selected.stage }} · 候选 {{ selected.cand }} · 工具 {{ selected.tools }} · 高德 {{ selected.amap }} · {{ selected.latency }}
        </div>
        <div class="mt-1 text-[9.5px] text-faint">
          模型 {{ selected.model || '规则版' }} · tokens {{ selected.promptTokens ?? 0 }} / {{ selected.completionTokens ?? 0 }} · 成本 ¥{{ (selected.cost ?? 0).toFixed(4) }}
        </div>

        <h4 class="mt-4 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">计划</h4>
        <div class="mt-2 rounded-xl border border-line bg-paper2 px-3.5 py-2">
          <div v-for="step in selected.plan" :key="step[0]" class="flex items-start gap-2 border-b border-line py-1.5 last:border-0">
            <span class="mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full" :class="planClass(step[2])">
              <Check v-if="step[2] === 'done'" :size="10" />
              <Loader2 v-else-if="step[2] === 'now'" :size="10" class="animate-spin" />
              <Circle v-else-if="step[2] === 'pending'" :size="7" />
              <X v-else :size="10" />
            </span>
            <div class="flex-1 text-[10.5px] leading-5">
              <b class="text-ink">{{ step[0] }}</b> <span class="text-muted">· {{ step[1] }}</span>
            </div>
            <span class="mono text-[9px] text-faint">{{ step[3] }}</span>
          </div>
        </div>

        <h4 class="mt-4 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">工具调用</h4>
        <div class="mt-2 overflow-x-auto rounded-xl border border-line bg-paper2 px-3 py-2">
          <div v-for="tool in selected.toolsList" :key="tool[0] + tool[1]" class="flex items-start gap-2 border-b border-line py-1.5 text-[10px] last:border-0">
            <span class="w-[90px] shrink-0 font-semibold text-ink">{{ tool[0] }}</span>
            <span class="flex-1 break-all text-muted">{{ tool[1] }}</span>
            <span class="mono w-[42px] shrink-0 text-right text-faint">{{ tool[2] }}</span>
            <span class="mono w-[92px] shrink-0 text-right text-faint">{{ tool[3] }}</span>
          </div>
        </div>

        <h4 class="mt-4 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">LLM 调用</h4>
        <div class="mt-2 rounded-xl border border-line bg-paper2 px-3.5 py-2.5 text-[10.5px] leading-5 text-muted">
          Qwen2.5-72B · 3.2k in / 1.1k out · cached 1.8k · ¥0.012 · TTFT 0.6s · 2 次调用
        </div>

        <h4 class="mt-4 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">护栏</h4>
        <div class="mt-2 rounded-xl border border-line bg-paper2 px-3.5 py-2.5 text-[10.5px] leading-5 text-muted">
          高德 {{ selected.amap }} / 15 · 自动下单关闭 · 付费模型 0 · {{ selected.status === 'blocked' ? '超限拦截：未调用外部接口' : '工具白名单内' }}
        </div>

        <h4 class="mt-4 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">结果</h4>
        <div class="mt-2 rounded-xl border border-line bg-paper2 px-3.5 py-2.5 text-[10.5px] leading-5 text-muted">{{ selected.result }}</div>

        <div class="mt-4 flex gap-2">
          <button class="btn flex-1" @click="annotate(selected.id, 'review')">标记需复核</button>
          <button class="btn flex-1" @click="annotate(selected.id, 'dataset')">加入评测集</button>
        </div>
      </template>
    </AppDrawer>
  </div>
</template>
