<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ExternalLink, Loader2, Plus, Search, ShieldAlert, Trash2 } from 'lucide-vue-next'
import type {
  ReputationMention,
  ReputationOverview,
  ReputationSummary,
} from '@/api/types'
import type { ReputationDraft } from '@/api/contracts'
import { adminApi } from '@/api/services/admin'
import { useToast } from '@/composables/useToast'
import AdminKpi from './AdminKpi.vue'

const { toast } = useToast()
const data = ref<ReputationOverview | null>(null)
const loading = ref(true)
const loadError = ref('')
const selectedId = ref<number | null>(null)
const selectedName = ref('')
const selectedDistrict = ref<string | null>(null)
const selectedSummary = ref<ReputationSummary | null>(null)
const mentions = ref<ReputationMention[]>([])
const detailLoading = ref(false)
const saving = ref(false)
const extracting = ref(false)
const drafts = ref<ReputationDraft[]>([])
const searchQ = ref('')
const searchResults = ref<Array<{ id: number; name: string; district: string | null }>>([])

const form = ref({
  source: 'manual',
  url: '',
  title: '',
  excerpt: '',
  issueType: 'noise',
  severity: 'medium' as 'low' | 'medium' | 'high',
  confidence: 0.7,
  matchStatus: 'verified' as 'verified' | 'uncertain' | 'rejected',
  publishedAt: '',
})

const SOURCE_LABELS: Record<string, string> = {
  douban: '豆瓣',
  xiaohongshu: '小红书',
  '12345': '12345',
  dianping: '大众点评',
  web: '网页',
  manual: '人工',
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    data.value = await adminApi.reputation()
  } catch {
    loadError.value = '口碑概览加载失败'
  } finally {
    loading.value = false
  }
}
onMounted(load)

const stats = computed(() => data.value?.stats)
const issueTypes = computed(() => data.value?.issue_types ?? {})

async function searchCommunities() {
  try {
    searchResults.value = await adminApi.reputationCommunities(searchQ.value)
  } catch {
    toast('小区搜索失败')
  }
}

async function selectCommunity(id: number, name?: string, district?: string | null) {
  selectedId.value = id
  selectedName.value = name || ''
  selectedDistrict.value = district ?? null
  detailLoading.value = true
  drafts.value = []
  try {
    const result = await adminApi.reputationCommunity(id)
    selectedName.value = result.community.name
    selectedDistrict.value = result.community.district
    selectedSummary.value = result.summary
    mentions.value = result.mentions
  } catch {
    toast('小区口碑加载失败')
  } finally {
    detailLoading.value = false
  }
}

async function refreshSelected() {
  if (selectedId.value == null) return
  const id = selectedId.value
  await selectCommunity(id, selectedName.value, selectedDistrict.value)
  await load()
}

async function submit() {
  if (selectedId.value == null) {
    toast('先选择小区')
    return
  }
  if (form.value.excerpt.trim().length < 4) {
    toast('证据原文至少 4 个字')
    return
  }
  saving.value = true
  try {
    await adminApi.createReputationMention({
      communityId: selectedId.value,
      source: form.value.source,
      url: form.value.url.trim() || null,
      title: form.value.title.trim() || null,
      excerpt: form.value.excerpt.trim(),
      issueType: form.value.issueType || null,
      severity: form.value.severity,
      confidence: form.value.confidence,
      matchStatus: form.value.matchStatus,
      publishedAt: form.value.publishedAt || null,
    })
    toast('证据已录入，小区评分会在下次 rescore 时更新')
    form.value.excerpt = ''
    form.value.url = ''
    form.value.title = ''
    drafts.value = []
    await refreshSelected()
  } catch {
    toast('录入失败：链接可能重复或字段不合法')
  } finally {
    saving.value = false
  }
}

async function extract() {
  if (selectedId.value == null) {
    toast('先选择小区')
    return
  }
  const text = form.value.excerpt.trim()
  if (text.length < 10) {
    toast('把网页/帖子原文粘贴到“证据原文”后再抽取')
    return
  }
  extracting.value = true
  try {
    const result = await adminApi.extractReputation(selectedId.value, text)
    drafts.value = result.drafts
    toast(result.drafts.length ? `抽取到 ${result.drafts.length} 条草稿，需人工确认` : '没有抽取到可用证据')
  } catch {
    toast('抽取失败；可能是模型未配置或额度不足')
  } finally {
    extracting.value = false
  }
}

function useDraft(draft: ReputationDraft) {
  form.value.excerpt = draft.excerpt
  form.value.issueType = draft.issue_type
  form.value.severity = draft.severity
  form.value.confidence = draft.confidence
  form.value.matchStatus = 'uncertain'
  drafts.value = []
}

async function setStatus(mention: ReputationMention, status: 'verified' | 'uncertain' | 'rejected') {
  try {
    await adminApi.updateReputationMention(mention.id, status)
    toast('匹配状态已更新')
    await refreshSelected()
  } catch {
    toast('更新失败')
  }
}

async function removeMention(mention: ReputationMention) {
  if (!window.confirm('删除这条口碑证据？')) return
  try {
    await adminApi.deleteReputationMention(mention.id)
    toast('已删除')
    await refreshSelected()
  } catch {
    toast('删除失败')
  }
}

function riskClass(status: string | undefined) {
  if (status === 'high') return 'tag-coral'
  if (status === 'watch') return 'tag-amber'
  if (status === 'low') return 'tag-green'
  return 'tag-neutral'
}

function matchClass(status: string) {
  if (status === 'verified') return 'tag-green'
  if (status === 'uncertain') return 'tag-amber'
  return 'tag-neutral'
}

function matchLabel(status: string) {
  if (status === 'verified') return '已确认'
  if (status === 'uncertain') return '待确认'
  return '已排除'
}

function sourceLabel(source: string) {
  return SOURCE_LABELS[source] || source
}

function pct(value: number | null | undefined) {
  return value == null ? '—' : `${Math.round(value * 100)}%`
}
</script>

<template>
  <div>
    <h2 class="text-[20px] font-bold tracking-tight">口碑证据</h2>
    <p class="mt-1 text-[12.5px] text-muted">按需采集、人工确认后再参与评分；没有证据的小区显示“数据不足”，不拿中性分冒充实测。</p>
    <div class="mt-3 rounded-xl border border-forest/15 bg-forest-soft/60 px-3.5 py-2.5 text-[11px] leading-5 text-forest">
      <b>证据链：</b>来源 + 原文 + 链接 + 置信度 + 实体匹配状态。评分按 180 天半衰期衰减；<b>uncertain</b> 只展示不参与评分，<b>rejected</b> 直接排除。
    </div>

    <div v-if="loading" class="mt-3 rounded-xl border border-line bg-paper2 px-3.5 py-2 text-[10.5px] text-muted">口碑数据加载中…</div>
    <div v-else-if="loadError" class="mt-3 rounded-xl border border-coral/25 bg-coral-soft px-3.5 py-2 text-[10.5px] text-coral">
      {{ loadError }}
      <button class="ml-2 underline" @click="load">重试</button>
    </div>

    <div class="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
      <AdminKpi label="小区总数" :value="stats?.communities ?? 0" sub="需要对齐" />
      <AdminKpi label="有证据" :value="stats?.with_evidence ?? 0" sub="参与评分" tone="green" />
      <AdminKpi label="无证据" :value="stats?.without_evidence ?? 0" sub="显示数据不足" tone="amber" />
      <AdminKpi label="高风险" :value="stats?.high_risk ?? 0" sub="证据聚合" tone="coral" />
      <AdminKpi label="已确认证据" :value="stats?.verified ?? 0" sub="含链接可追溯" />
      <AdminKpi label="待确认 / 来源" :value="`${stats?.uncertain ?? 0} / ${stats?.sources ?? 0}`" sub="uncertain 不计分" />
    </div>

    <div class="mt-4 grid gap-4 xl:grid-cols-2">
      <section class="card p-4">
        <h3 class="panel-title flex items-center gap-2"><ShieldAlert :size="15" class="text-coral" />高风险小区 <span class="hint">按证据分排序</span></h3>
        <div class="mt-2 overflow-x-auto">
          <table class="w-full text-left text-[11.5px]">
            <thead class="border-b border-line bg-paper2 text-[9.5px] uppercase tracking-wide text-faint">
              <tr><th class="px-2 py-2.5 font-semibold">小区</th><th class="px-2 py-2.5 font-semibold">证据</th><th class="px-2 py-2.5 font-semibold">风险</th><th class="px-2 py-2.5 font-semibold">主要问题</th><th class="px-2 py-2.5" /></tr>
            </thead>
            <tbody>
              <tr v-for="item in data?.risky ?? []" :key="item.community_id" class="border-b border-line last:border-0">
                <td class="px-2 py-2.5">
                  <div class="font-semibold">{{ item.name }}</div>
                  <div class="text-[9.5px] text-faint">{{ item.district || '—' }}</div>
                </td>
                <td class="px-2 py-2.5">{{ item.count }} 条</td>
                <td class="px-2 py-2.5"><span :class="riskClass(item.status)">{{ item.label }}</span></td>
                <td class="px-2 py-2.5 text-muted">{{ item.top_issue_label || '—' }}</td>
                <td class="px-2 py-2.5">
                  <button class="btn-ghost btn-sm" @click="selectCommunity(item.community_id, item.name, item.district)">查看</button>
                </td>
              </tr>
              <tr v-if="!(data?.risky?.length)">
                <td colspan="5" class="px-4 py-8 text-center text-[11px] text-faint">暂无有证据的小区。先给候选小区录入人工验证证据。</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="card p-4">
        <h3 class="panel-title">优先补证据 <span class="hint">按在库房源数</span></h3>
        <div class="mt-2 overflow-x-auto">
          <table class="w-full text-left text-[11.5px]">
            <thead class="border-b border-line bg-paper2 text-[9.5px] uppercase tracking-wide text-faint">
              <tr><th class="px-2 py-2.5 font-semibold">小区</th><th class="px-2 py-2.5 font-semibold">房源</th><th class="px-2 py-2.5 font-semibold">状态</th><th class="px-2 py-2.5" /></tr>
            </thead>
            <tbody>
              <tr v-for="item in data?.missing ?? []" :key="item.community_id" class="border-b border-line last:border-0">
                <td class="px-2 py-2.5">
                  <div class="font-semibold">{{ item.name }}</div>
                  <div class="text-[9.5px] text-faint">{{ item.district || '—' }}</div>
                </td>
                <td class="mono px-2 py-2.5">{{ item.listings }}</td>
                <td class="px-2 py-2.5"><span class="tag-neutral">数据不足</span></td>
                <td class="px-2 py-2.5">
                  <button class="btn-ghost btn-sm" @click="selectCommunity(item.community_id, item.name, item.district)">补证据</button>
                </td>
              </tr>
              <tr v-if="!(data?.missing?.length)">
                <td colspan="4" class="px-4 py-8 text-center text-[11px] text-faint">所有小区都已有证据。</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <div class="mt-4 grid gap-4 xl:grid-cols-2">
      <section class="card p-4">
        <h3 class="panel-title flex items-center gap-2"><Plus :size="15" class="text-forest" />录入 / 抽取证据</h3>
        <div class="mt-3 flex flex-wrap items-center gap-2">
          <input v-model="searchQ" class="input w-[180px]" placeholder="搜索小区名" @keyup.enter="searchCommunities" />
          <button class="btn btn-sm" @click="searchCommunities"><Search :size="13" /> 搜索</button>
          <span v-if="selectedId" class="tag-green">{{ selectedName }} · {{ selectedDistrict || '—' }}</span>
        </div>
        <div v-if="searchResults.length" class="mt-2 flex flex-wrap gap-1.5">
          <button v-for="item in searchResults" :key="item.id" class="btn-ghost btn-sm" @click="selectCommunity(item.id, item.name, item.district); searchResults = []">
            {{ item.name }} · {{ item.district || '—' }}
          </button>
        </div>
        <div v-if="selectedSummary" class="mt-2 rounded-xl border border-line bg-paper2 px-3 py-2 text-[10.5px] leading-5 text-muted">
          当前：<b :class="riskClass(selectedSummary.status)">{{ selectedSummary.label }}</b> · 已确认 {{ selectedSummary.count }} 条 · 待确认 {{ selectedSummary.uncertain }} 条
          <span v-if="selectedSummary.top_issue_label"> · 主要问题：{{ selectedSummary.top_issue_label }}</span>
        </div>

        <div class="mt-3 grid gap-2 sm:grid-cols-2">
          <label class="text-[10.5px] text-muted">来源
            <select v-model="form.source" class="input mt-1 w-full">
              <option v-for="source in data?.sources ?? ['manual']" :key="source" :value="source">{{ sourceLabel(source) }}</option>
            </select>
          </label>
          <label class="text-[10.5px] text-muted">问题类型
            <select v-model="form.issueType" class="input mt-1 w-full">
              <option v-for="(label, key) in issueTypes" :key="key" :value="key">{{ label }}</option>
            </select>
          </label>
          <label class="text-[10.5px] text-muted">严重度
            <select v-model="form.severity" class="input mt-1 w-full">
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
            </select>
          </label>
          <label class="text-[10.5px] text-muted">匹配状态
            <select v-model="form.matchStatus" class="input mt-1 w-full">
              <option value="verified">已确认（参与评分）</option>
              <option value="uncertain">待确认（只展示）</option>
              <option value="rejected">已排除</option>
            </select>
          </label>
          <label class="text-[10.5px] text-muted sm:col-span-2">证据链接（可选）
            <input v-model="form.url" class="input mt-1 w-full" placeholder="https://..." />
          </label>
          <label class="text-[10.5px] text-muted sm:col-span-2">标题（可选）
            <input v-model="form.title" class="input mt-1 w-full" maxlength="255" />
          </label>
          <label class="text-[10.5px] text-muted sm:col-span-2">证据原文（必填，或粘贴网页原文用于抽取）
            <textarea v-model="form.excerpt" class="input mt-1 min-h-[86px] w-full" maxlength="2000" />
          </label>
          <label class="text-[10.5px] text-muted">置信度 {{ pct(form.confidence) }}
            <input v-model.number="form.confidence" type="range" min="0.05" max="1" step="0.05" class="mt-3 w-full" />
          </label>
          <label class="text-[10.5px] text-muted">发布时间（可选）
            <input v-model="form.publishedAt" type="date" class="input mt-1 w-full" />
          </label>
        </div>
        <div class="mt-3 flex flex-wrap gap-2">
          <button class="btn btn-sm" :disabled="saving || selectedId == null" @click="submit">
            <Loader2 v-if="saving" :size="13" class="animate-spin" /> 录入证据
          </button>
          <button class="btn-ghost btn-sm" :disabled="extracting || selectedId == null" @click="extract">
            <Loader2 v-if="extracting" :size="13" class="animate-spin" /> 从原文抽取草稿
          </button>
        </div>
        <div v-if="drafts.length" class="mt-2 space-y-2">
          <div v-for="(draft, index) in drafts" :key="index" class="rounded-xl border border-amber/25 bg-amber-soft px-3 py-2 text-[10.5px] leading-5 text-amber">
            <div>{{ draft.excerpt }}</div>
            <div class="mt-1 flex items-center gap-2">
              <span>{{ issueTypes[draft.issue_type] || draft.issue_type }} · {{ draft.severity }} · {{ pct(draft.confidence) }}</span>
              <button class="btn-ghost btn-sm ml-auto" @click="useDraft(draft)">填入表单</button>
            </div>
          </div>
        </div>
        <p class="mt-2 text-[9.5px] leading-4 text-faint">抽取只是草稿，默认 uncertain；必须人工确认链接和实体匹配后才参与评分。抽取调用已配置的 ModelScope 文本模型，受 aiDailyCap 约束。</p>
      </section>

      <section class="card p-4">
        <h3 class="panel-title">证据列表 <span class="hint">{{ mentions.length }} 条 · {{ selectedName || '未选择小区' }}</span></h3>
        <div v-if="detailLoading" class="mt-3 text-[11px] text-muted">小区证据加载中…</div>
        <div v-else-if="!selectedId" class="mt-3 rounded-xl border border-dashed border-line px-4 py-10 text-center text-[11px] text-faint">
          从左侧“高风险小区 / 优先补证据”选一个小区，或搜索小区名。
        </div>
        <div v-else-if="!mentions.length" class="mt-3 rounded-xl border border-dashed border-line px-4 py-10 text-center text-[11px] text-faint">
          该小区还没有证据；评分显示“数据不足（中性分）”。
        </div>
        <div v-else class="mt-2 space-y-2">
          <div v-for="mention in mentions" :key="mention.id" class="rounded-xl border border-line bg-paper2 px-3 py-2.5">
            <div class="flex flex-wrap items-center gap-1.5 text-[10px]">
              <span class="tag-neutral">{{ sourceLabel(mention.source) }}</span>
              <span :class="matchClass(mention.match_status)">{{ matchLabel(mention.match_status) }}</span>
              <span class="tag-neutral">{{ issueTypes[mention.issue_type || ''] || mention.issue_type || '其他' }}</span>
              <span class="tag-neutral">{{ mention.severity }}</span>
              <span class="tag-neutral">置信度 {{ pct(mention.confidence) }}</span>
              <a v-if="mention.url" :href="mention.url" target="_blank" rel="noopener noreferrer" class="ml-auto inline-flex items-center gap-1 text-forest hover:underline">
                原文 <ExternalLink :size="10" />
              </a>
            </div>
            <div class="mt-1.5 text-[11px] leading-5 text-muted">{{ mention.excerpt }}</div>
            <div class="mt-1 flex flex-wrap items-center gap-1.5">
              <button v-if="mention.match_status !== 'verified'" class="btn-ghost btn-sm" @click="setStatus(mention, 'verified')">确认</button>
              <button v-if="mention.match_status !== 'uncertain'" class="btn-ghost btn-sm" @click="setStatus(mention, 'uncertain')">存疑</button>
              <button v-if="mention.match_status !== 'rejected'" class="btn-ghost btn-sm" @click="setStatus(mention, 'rejected')">排除</button>
              <button class="btn-ghost btn-sm ml-auto text-coral" @click="removeMention(mention)"><Trash2 :size="11" /> 删除</button>
            </div>
          </div>
        </div>
        <div class="mt-3 rounded-xl border border-line bg-paper2 px-3.5 py-2.5 text-[10px] leading-5 text-faint">
          评分权重 10 分：已确认证据越多/越严重，口碑分越低；无证据时保持中性分但明确标注“数据不足”。当前半衰期 {{ data?.half_life_days ?? 180 }} 天。
        </div>
      </section>
    </div>
  </div>
</template>
