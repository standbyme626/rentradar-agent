<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  Plug,
  RefreshCw,
  Zap,
} from 'lucide-vue-next'
import AdminKpi from './AdminKpi.vue'
import { providersApi } from '@/api/services/providers'
import type {
  ProviderCall,
  ProviderDomain,
  ProviderInfo,
  ProviderTestResult,
} from '@/api/contracts'
import { formatTime } from './adminData'

type DomainKey = 'all' | ProviderDomain

const domains: Array<{ value: DomainKey; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'housing', label: '房源' },
  { value: 'maps', label: '地图' },
  { value: 'transit', label: '地铁 / 公交' },
  { value: 'opendata', label: '开放数据' },
  { value: 'reputation', label: '口碑' },
  { value: 'ai', label: 'AI' },
  { value: 'notify', label: '通知' },
]

const domainLabels: Record<ProviderDomain, string> = {
  housing: '房源',
  maps: '地图',
  transit: '地铁 / 公交',
  opendata: '开放数据',
  reputation: '口碑',
  ai: 'AI',
  notify: '通知',
}

const capLabels: Record<string, string> = {
  listing_search: '房源列表',
  listing_detail: '房源详情',
  geocode: '地理编码',
  reverse_geocode: '逆地理',
  poi_search: 'POI',
  route_driving: '驾车路线',
  route_transit: '公交路线',
  taxi_estimate: '打车估价',
  metro_time: '地铁时间',
  rent_reference: '参考租金',
  reputation: '口碑',
  image_tagging: '图片标签',
  chat: '对话',
}

const providers = ref<ProviderInfo[]>([])
const calls = ref<ProviderCall[]>([])
const loading = ref(false)
const error = ref('')
const domain = ref<DomainKey>('all')
const testing = ref<string | null>(null)
const saving = ref<string | null>(null)
const results = ref<Record<string, ProviderTestResult>>({})

const filtered = computed(() =>
  domain.value === 'all'
    ? providers.value
    : providers.value.filter((item) => item.domain === domain.value),
)
const healthyCount = computed(
  () => providers.value.filter((item) => item.health.status === 'ok').length,
)
const configuredCount = computed(
  () => providers.value.filter((item) => item.configured).length,
)
const attentionCount = computed(
  () =>
    providers.value.filter(
      (item) =>
        !item.configured ||
        item.health.status === 'error' ||
        (item.quota.limit > 0 && item.quota.used / item.quota.limit >= 0.8),
    ).length,
)

const errorText = (value: unknown) => (value instanceof Error ? value.message : String(value))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [providerList, callList] = await Promise.all([
      providersApi.list(),
      providersApi.calls(undefined, 30),
    ])
    providers.value = providerList
    calls.value = callList
  } catch (value) {
    error.value = errorText(value)
  } finally {
    loading.value = false
  }
}

async function runTest(provider: ProviderInfo) {
  testing.value = provider.code
  try {
    results.value[provider.code] = await providersApi.test(provider.code)
    await load()
  } catch (value) {
    results.value[provider.code] = {
      provider: provider.code,
      ok: false,
      message: errorText(value),
      latency_ms: 0,
      quota_units: 0,
      health: provider.health,
    }
  } finally {
    testing.value = null
  }
}

async function toggle(provider: ProviderInfo) {
  saving.value = provider.code
  try {
    await providersApi.update(provider.code, { enabled: !provider.enabled })
    await load()
  } catch (value) {
    error.value = errorText(value)
  } finally {
    saving.value = null
  }
}

const domainCount = (key: DomainKey) =>
  key === 'all' ? providers.value.length : providers.value.filter((item) => item.domain === key).length

const statusOf = (provider: ProviderInfo) => {
  if (!provider.enabled) return { text: '已禁用', cls: 'tag-neutral' }
  if (!provider.configured) return { text: '未配置', cls: 'tag-amber' }
  if (provider.health.status === 'ok') return { text: '正常', cls: 'tag-green' }
  if (provider.health.status === 'error') return { text: '异常', cls: 'tag-coral' }
  return { text: '待测试', cls: 'tag-neutral' }
}

const quotaText = (provider: ProviderInfo) =>
  provider.quota.limit > 0
    ? `${provider.quota.used} / ${provider.quota.limit}`
    : `${provider.quota.used} / 未设上限`

const quotaPct = (provider: ProviderInfo) =>
  provider.quota.limit > 0
    ? Math.min(100, Math.round((provider.quota.used / provider.quota.limit) * 100))
    : 0

const quotaBar = (provider: ProviderInfo) => {
  if (!provider.quota.limit) return 'bg-forest/40'
  const ratio = provider.quota.used / provider.quota.limit
  if (ratio >= 0.8) return 'bg-coral'
  if (ratio >= 0.6) return 'bg-amber'
  return 'bg-forest'
}

const lastCallText = (provider: ProviderInfo) => {
  if (!provider.last_call) return '暂无调用记录'
  const call = provider.last_call
  const latency = call.latency_ms == null ? '' : ` · ${call.latency_ms}ms`
  return `${formatTime(call.created_at)} · ${call.status}${latency}`
}

onMounted(load)
</script>

<template>
  <div>
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 class="text-[20px] font-bold tracking-tight">API 管理</h2>
        <p class="mt-1 text-[12.5px] text-muted">
          外部数据源按域管理：房源、地图、地铁 / 公交、开放数据、口碑、AI、通知。此页始终读取真实后端。
        </p>
        <p class="mt-1 text-[10px] text-faint">
          启用 / 优先级与额度在运行时生效：天地图、SZMC、贝壳与 LLM 调用前会校验 Provider 状态、熔断和剩余额度。
        </p>
      </div>
      <button class="btn btn-sm" :disabled="loading" @click="load">
        <RefreshCw :size="14" :class="loading ? 'animate-spin' : ''" />
        刷新
      </button>
    </div>

    <div v-if="error" class="mt-3 rounded-xl border border-coral/25 bg-coral-soft px-3.5 py-2 text-[10.5px] text-coral">
      {{ error }}
      <button class="ml-2 underline" @click="load">重试</button>
    </div>

    <div class="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
      <AdminKpi label="已接入数据源" :value="providers.length" sub="按 provider 计" />
      <AdminKpi label="健康" :value="healthyCount" :sub="`已配置 ${configuredCount} 个`" tone="green" />
      <AdminKpi label="需要关注" :value="attentionCount" sub="未配置 / 异常 / 额度 ≥80%" tone="coral" />
      <AdminKpi label="调用记录" :value="calls.length" sub="最近 30 条" tone="amber" />
    </div>

    <div class="mt-4 flex flex-wrap gap-1.5">
      <button
        v-for="item in domains"
        :key="item.value"
        class="rounded-full border px-3 py-1 text-[10.5px] transition"
        :class="
          domain === item.value
            ? 'border-forest bg-forest text-white'
            : 'border-line bg-paper text-muted hover:border-forest/40'
        "
        @click="domain = item.value"
      >
        {{ item.label }}
        <span class="ml-1 opacity-70">{{ domainCount(item.value) }}</span>
      </button>
    </div>

    <div v-if="loading && !providers.length" class="mt-4 rounded-xl border border-line bg-paper2 px-3.5 py-3 text-[11px] text-muted">
      正在读取 provider 状态…
    </div>

    <div v-else class="mt-4 grid gap-4 xl:grid-cols-2">
      <section v-for="provider in filtered" :key="provider.code" class="card p-4">
        <div class="flex items-start gap-3">
          <div class="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-forest-soft text-forest">
            <Plug :size="16" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <h3 class="text-[13px] font-semibold text-ink">{{ provider.name }}</h3>
              <span :class="statusOf(provider).cls">{{ statusOf(provider).text }}</span>
            </div>
            <div class="mono mt-0.5 text-[9.5px] text-faint">
              {{ provider.code }} · {{ domainLabels[provider.domain] }}
            </div>
          </div>
          <button
            class="btn btn-sm shrink-0"
            :disabled="saving === provider.code"
            @click="toggle(provider)"
          >
            {{ provider.enabled ? '禁用' : '启用' }}
          </button>
        </div>

        <p class="mt-2 text-[11px] leading-5 text-muted">{{ provider.description }}</p>

        <div class="mt-2 flex flex-wrap gap-1.5">
          <span v-for="cap in provider.capabilities" :key="cap" class="tag-neutral">
            {{ capLabels[cap] ?? cap }}
          </span>
          <span v-if="!provider.implemented" class="tag-amber">未实现</span>
        </div>

        <div class="mt-3 grid grid-cols-2 gap-2 text-[10px] text-muted sm:grid-cols-4">
          <div>认证 <b class="text-ink">{{ provider.auth }}</b></div>
          <div>坐标 <b class="text-ink">{{ provider.coord_system }}</b></div>
          <div>优先级 <b class="text-ink">{{ provider.priority }}</b></div>
          <div>出口 <b class="text-ink">{{ provider.proxy || '直连' }}</b></div>
        </div>

        <div class="mt-3">
          <div class="flex items-center justify-between text-[10px] text-muted">
            <span>额度（{{ provider.quota.period }}）</span>
            <span class="mono text-ink">{{ quotaText(provider) }}</span>
          </div>
          <div class="mt-1.5 h-1.5 overflow-hidden rounded-full bg-sand">
            <div class="h-1.5 rounded-full transition-all" :class="quotaBar(provider)" :style="{ width: `${quotaPct(provider)}%` }" />
          </div>
          <div v-if="!provider.quota.limit" class="mt-1 text-[9px] text-faint">
            未设置硬上限；当前先记录调用，后续在业务调用链路里接配额保护。
          </div>
        </div>

        <div
          v-if="provider.test_note"
          class="mt-2 rounded-lg border border-line bg-paper2 px-2.5 py-1.5 text-[9.5px] text-muted"
        >
          {{ provider.test_note }}
        </div>

        <div
          v-if="results[provider.code]"
          class="mt-2 flex items-start gap-1.5 rounded-lg px-2.5 py-1.5 text-[9.5px]"
          :class="
            results[provider.code].ok
              ? 'border border-forest/20 bg-forest-soft text-forest'
              : 'border border-coral/20 bg-coral-soft text-coral'
          "
        >
          <CheckCircle2 v-if="results[provider.code].ok" :size="12" class="mt-0.5 shrink-0" />
          <AlertTriangle v-else :size="12" class="mt-0.5 shrink-0" />
          <span>
            {{ results[provider.code].message }}
            <span class="opacity-70">· {{ results[provider.code].latency_ms }}ms</span>
          </span>
        </div>

        <div class="mt-3 flex flex-wrap items-center justify-between gap-2">
          <div class="flex items-center gap-1.5 text-[9.5px] text-faint">
            <Activity :size="11" />
            {{ lastCallText(provider) }}
          </div>
          <div class="flex gap-1.5">
            <a
              v-if="provider.docs_url"
              :href="provider.docs_url"
              target="_blank"
              rel="noreferrer"
              class="btn btn-sm"
            >
              <ExternalLink :size="12" /> 文档
            </a>
            <button
              class="btn btn-sm"
              :disabled="testing === provider.code"
              @click="runTest(provider)"
            >
              <Zap :size="12" />
              {{ testing === provider.code ? '测试中…' : '测试连接' }}
            </button>
          </div>
        </div>
      </section>
    </div>

    <div v-if="!loading && !filtered.length" class="mt-4 rounded-xl border border-dashed border-line bg-paper2 px-4 py-8 text-center text-[11px] text-muted">
      这个域还没有接入 provider。后续按 Phase 4 接入地铁 / 公交 / 开放数据 / 口碑。
    </div>

    <section class="card mt-4 p-4">
      <h3 class="panel-title">
        最近调用
        <span class="hint">健康检查与测试记录</span>
      </h3>
      <div v-if="!calls.length" class="mt-3 text-[11px] text-muted">暂无调用记录，点上面的“测试连接”生成一条。</div>
      <div v-else class="mt-2 overflow-x-auto">
        <table class="w-full text-left text-[11.5px]">
          <thead class="border-b border-line text-[9.5px] uppercase tracking-wide text-faint">
            <tr>
              <th class="py-2 pr-3 font-semibold">时间</th>
              <th class="py-2 pr-3 font-semibold">Provider</th>
              <th class="py-2 pr-3 font-semibold">能力</th>
              <th class="py-2 pr-3 font-semibold">状态</th>
              <th class="py-2 pr-3 font-semibold">耗时</th>
              <th class="py-2 font-semibold">错误</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="call in calls" :key="call.id" class="border-b border-line last:border-0">
              <td class="mono py-2 pr-3 text-faint">{{ formatTime(call.created_at) }}</td>
              <td class="mono py-2 pr-3">{{ call.provider }}</td>
              <td class="py-2 pr-3">{{ capLabels[call.capability] ?? call.capability }}</td>
              <td class="py-2 pr-3">
                <span :class="call.status === 'ok' ? 'tag-green' : 'tag-coral'">{{ call.status }}</span>
              </td>
              <td class="mono py-2 pr-3">{{ call.latency_ms == null ? '—' : `${call.latency_ms}ms` }}</td>
              <td class="max-w-[280px] truncate py-2 text-coral">{{ call.error_message || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
