<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ExternalLink, Image as ImageIcon, Loader2, Sparkles } from 'lucide-vue-next'
import type { Inspection, ListingDetail, ScoreReasons } from '@/api/types'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import CoverPlaceholder from '@/components/ui/CoverPlaceholder.vue'
import Sparkline from '@/components/ui/Sparkline.vue'
import {
  CHECKLIST_KEYS,
  CHECKLIST_LABELS,
  WATCH_STATES,
  checkedCount,
  stateClass,
  stateLabel,
} from '@/lib/watchlist'

const props = defineProps<{ listing: ListingDetail | null; loading: boolean }>()
const emit = defineEmits<{
  close: []
  compare: [listing: ListingDetail]
  save: [listing: ListingDetail]
  state: [state: string, note: string | null]
  inspection: [payload: Pick<Inspection, 'items' | 'note' | 'photos'>]
  refresh: []
}>()

const inspectionItems = ref<Record<string, boolean>>({})
const inspectionNote = ref('')
const photos = ref<string[]>([])
const newPhoto = ref('')
const watchNote = ref('')

watch(
  () => props.listing,
  (item) => {
    inspectionItems.value = { ...(item?.inspection?.items ?? {}) }
    inspectionNote.value = item?.inspection?.note ?? ''
    photos.value = [...(item?.inspection?.photos ?? [])]
    watchNote.value = item?.watch_note ?? ''
  },
  { immediate: true },
)

const money = (value: number | null) =>
  value == null ? '—' : `¥${value.toLocaleString('zh-CN')}`
const subtitle = computed(() => {
  const item = props.listing
  if (!item) return ''
  return `${item.district || '—'} · ${item.layout || '—'} · ${item.area ?? '—'}㎡ · ${money(item.rent)}/月`
})
const reasons = computed<ScoreReasons>(() => props.listing?.score_reasons ?? {})
const componentRows = computed(() => {
  const components = (reasons.value.components ?? {}) as Record<string, number>
  if (!Object.keys(components).length) return []
  return [
    { key: 'price', label: '性价比', max: 35 },
    { key: 'commute', label: '通勤', max: 25 },
    { key: 'condition', label: '居住条件', max: 15 },
    { key: 'convenience', label: '生活便利', max: 10 },
    { key: 'reputation', label: '口碑', max: 10 },
    { key: 'freshness', label: '新鲜度', max: 5 },
  ].map((item) => ({ ...item, value: Number(components[item.key] ?? 0) }))
})
const reasonLines = computed(() => {
  const keys = ['price', 'commute', 'condition', 'convenience', 'reputation', 'freshness'] as const
  return keys.flatMap((key) => {
    const text = reasons.value[key]
    return typeof text === 'string' && text ? [{ key, text }] : []
  })
})
const snapshots = computed(() => props.listing?.snapshots ?? [])
const pricePoints = computed(() => snapshots.value.map((item) => item.rent))
const priceText = computed(() => {
  if (!snapshots.value.length) return '暂无价格快照'
  const latest = snapshots.value[snapshots.value.length - 1]
  if (snapshots.value.length < 2) {
    return `已有 1 个价格点（${money(latest.rent)}），7 天后可看走势`
  }
  return `${snapshots.value.length} 个价格点 · 最新 ${money(latest.rent)} · ${new Date(latest.seen_at).toLocaleDateString('zh-CN')}`
})
const commute = computed(() => props.listing?.commute_stats ?? null)
const probes = computed(() => (props.listing?.delivery_probes ?? []).slice(0, 3))
const reputation = computed(() => props.listing?.reputation ?? null)
const reputationMentions = computed(() => reputation.value?.mentions ?? [])
const imageAnalysis = computed(() => props.listing?.image_analysis ?? null)
const fakeSignals = computed(() =>
  (imageAnalysis.value?.signals ?? []).filter((item) => !['low_resolution', 'dark_cover', 'cover_missing', 'cover_unavailable'].includes(item.code)),
)
const qualitySignals = computed(() =>
  (imageAnalysis.value?.signals ?? []).filter((item) => ['low_resolution', 'dark_cover', 'cover_missing', 'cover_unavailable'].includes(item.code)),
)

function verdictLabel(value: string | undefined) {
  if (value === 'suspicious') return '可疑（≥2 信号）'
  if (value === 'watch') return '观察（1 个信号）'
  if (value === 'clear') return '未见异常'
  return '未分析'
}
const watchState = computed(() => props.listing?.watch_state ?? null)
const inspectionDone = computed(() => checkedCount(inspectionItems.value))

function toggleItem(key: string) {
  inspectionItems.value = { ...inspectionItems.value, [key]: !inspectionItems.value[key] }
}

function addPhoto() {
  const value = newPhoto.value.trim()
  if (!value || photos.value.includes(value)) return
  photos.value = [...photos.value, value]
  newPhoto.value = ''
}

function removePhoto(index: number) {
  photos.value = photos.value.filter((_, itemIndex) => itemIndex !== index)
}

function saveInspection() {
  emit('inspection', {
    items: { ...inspectionItems.value },
    note: inspectionNote.value.trim() || null,
    photos: [...photos.value],
  })
}

function saveWatchNote() {
  emit('state', watchState.value ?? 'new', watchNote.value.trim() || null)
}
</script>

<template>
  <AppDrawer
    :open="!!listing"
    :title="listing?.community_name || '房源详情'"
    :subtitle="subtitle"
    @close="emit('close')"
  >
    <template v-if="listing">
      <div
        v-if="loading"
        class="mb-3 flex items-center gap-2 rounded-xl border border-line bg-paper2 px-3 py-2 text-[11px] text-muted"
      >
        <Loader2 :size="13" class="animate-spin" /> 正在加载真实详情…
      </div>

      <CoverPlaceholder :name="listing.community_name" :variant="0" height="150px" />
      <p class="mt-1.5 text-[10px] text-faint">列表只提供封面图；详情图/AI 尚未接入，不用占位图冒充实拍。</p>

      <div class="mt-3 flex flex-wrap gap-1.5">
        <span class="tag-green">评分 {{ listing.score ?? '—' }}</span>
        <span :class="stateClass(watchState)">{{ stateLabel(watchState) }}</span>
        <span class="tag-neutral">
          通勤 {{ commute?.p50_min != null ? `${commute.p50_min} 分钟` : '—' }}
        </span>
        <span class="tag-neutral">{{ commute?.samples ?? 0 }} 个样本</span>
        <span v-if="commute?.multi_bucket" class="tag-green">{{ commute.bucket_count }} 个时段</span>
        <span v-else class="tag-amber">时段样本不足</span>
      </div>

      <h4 class="mt-5 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">评分拆解</h4>
      <div v-if="componentRows.length" class="mt-2 space-y-2">
        <div v-for="row in componentRows" :key="row.key">
          <div class="flex justify-between text-[11px] text-muted">
            <span>{{ row.label }}</span>
            <span>{{ row.value.toFixed(1) }} / {{ row.max }}</span>
          </div>
          <div class="mt-1 h-1.5 overflow-hidden rounded-full bg-sand">
            <div class="h-full rounded-full bg-forest" :style="{ width: `${Math.min(100, (row.value / row.max) * 100)}%` }" />
          </div>
        </div>
      </div>
      <p v-else class="mt-2 rounded-xl border border-dashed border-line2 bg-paper2 px-3.5 py-3 text-[11px] leading-5 text-muted">
        该房源还没有分值拆解（旧评分结果）。重新评分后会显示真实分项，不展示写死演示值。
      </p>

      <h4 class="mt-5 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">为什么推荐</h4>
      <div class="mt-2 rounded-xl border border-line bg-paper2 px-3.5 py-3 text-[11.5px] leading-6 text-muted">
        <template v-if="reasonLines.length">
          <div v-for="line in reasonLines" :key="line.key">{{ line.text }}</div>
        </template>
        <span v-else>暂无评分理由。</span>
      </div>

      <h4 class="mt-5 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">通勤（小区 → 公司）</h4>
      <div v-if="commute" class="mt-2 rounded-xl border border-line bg-paper2 px-3.5 py-3 text-[11.5px] leading-6 text-muted">
        <div class="flex items-baseline gap-3">
          <span class="text-[20px] font-bold text-ink">{{ commute.p50_min ?? '—' }}<small class="text-[10px] font-normal"> 分钟 p50</small></span>
          <span class="text-[13px] font-semibold text-ink">p90 {{ commute.p90_min ?? '—' }} 分钟</span>
        </div>
        <div class="mt-1">
          目的地址：{{ commute.destination || '未设置公司地址' }}
          <span v-if="commute.example" class="tag-amber ml-1">示例地址，请修改</span>
        </div>
        <div class="mt-0.5">
          {{ commute.samples }} 个样本 · 时段 {{ commute.buckets.join(' / ') || '—' }} ·
          {{ commute.provider === 'szmc' ? '深圳地铁官方' : commute.provider || '未知来源' }}
          <template v-if="commute.static"> · 时刻表估算（非实时，时段间无波动）</template>
        </div>
        <div v-if="commute.walk_min != null || commute.transfers != null" class="mt-0.5 text-[10.5px] text-faint">
          步行约 {{ commute.walk_min ?? '—' }} 分钟 · 换乘 {{ commute.transfers ?? '—' }} 次
        </div>
        <div v-if="!commute.multi_bucket" class="mt-1 text-[10.5px] text-amber">
          时段样本少于 3 个，p90 仅作参考。
        </div>
      </div>
      <p v-else class="mt-2 rounded-xl border border-dashed border-line2 bg-paper2 px-3.5 py-3 text-[11px] text-muted">
        暂无通勤样本；3km 内无地铁站时不会生成估算。
      </p>

      <h4 class="mt-5 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">价格走势</h4>
      <div v-if="pricePoints.length" class="mt-2">
        <Sparkline :points="pricePoints" />
        <p class="text-[10px] text-faint">{{ priceText }}</p>
      </div>
      <p v-else class="rounded-xl border border-dashed border-line2 bg-paper2 px-3.5 py-3 text-[11px] text-muted">
        {{ priceText }}
      </p>

      <h4 class="mt-5 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">外卖实测</h4>
      <div v-if="probes.length" class="mt-2 space-y-1.5">
        <div v-for="probe in probes" :key="probe.id" class="rounded-xl border border-line bg-paper2 px-3 py-2 text-[11px] text-muted">
          <b class="text-ink">{{ probe.platform }}</b> · {{ probe.meal_period || '未标时段' }} ·
          {{ probe.eta_min_low }}–{{ probe.eta_min_high }} 分钟 ·
          {{ probe.merchant_count ?? '—' }} 家店 · 置信度 {{ probe.confidence ?? '—' }}
        </div>
      </div>
      <p v-else class="rounded-xl border border-dashed border-line2 bg-paper2 px-3.5 py-3 text-[11px] text-muted">
        暂无外卖实测；不把估算写成实测。
      </p>

      <h4 class="mt-5 flex items-center gap-2 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">
        <ImageIcon :size="12" /> 封面分析
      </h4>
      <div v-if="imageAnalysis" class="mt-2 rounded-xl border border-line bg-paper2 px-3.5 py-3 text-[11px] leading-5 text-muted">
        <div class="flex flex-wrap items-center gap-1.5">
          <span
            class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
            :class="imageAnalysis.verdict === 'suspicious' ? 'tag-coral' : imageAnalysis.verdict === 'watch' ? 'tag-amber' : 'tag-green'"
          >{{ verdictLabel(imageAnalysis.verdict) }}</span>
          <span class="tag-neutral">置信度 {{ imageAnalysis.confidence != null ? `${Math.round(imageAnalysis.confidence * 100)}%` : '—' }}</span>
          <span class="tag-neutral">dHash 已算</span>
          <span v-if="imageAnalysis.needs_vision" class="tag-amber">视觉标签未授权</span>
        </div>
        <div v-if="fakeSignals.length" class="mt-2 flex flex-wrap gap-1">
          <span v-for="signal in fakeSignals" :key="signal.code" class="rounded border border-coral/30 bg-coral-soft px-1.5 py-0.5 text-[9.5px] text-coral" :title="JSON.stringify(signal.evidence)">
            {{ signal.label }} · {{ Math.round(signal.confidence * 100) }}%
          </span>
        </div>
        <div v-else class="mt-2 text-[10.5px] text-faint">未命中重复封面 / 低价 / 中介话术信号；这不等于图片真实。</div>
        <div v-if="qualitySignals.length" class="mt-1 text-[10px] text-faint">
          质量提示：{{ qualitySignals.map((item) => item.label).join('、') }}
        </div>
        <div v-if="imageAnalysis.quality?.width" class="mt-1 text-[10px] text-faint">
          封面 {{ imageAnalysis.quality.width }}×{{ imageAnalysis.quality.height }} · 亮度 {{ imageAnalysis.quality.brightness }}
        </div>
      </div>
      <p v-else class="mt-2 rounded-xl border border-dashed border-line2 bg-paper2 px-3.5 py-3 text-[11px] text-muted">
        暂无封面分析。管理端「图片 / AI」页对候选运行后，这里才展示证据，不用设计值占位。
      </p>

      <h4 class="mt-5 flex items-center gap-2 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">
        <Sparkles :size="12" /> 口碑证据
      </h4>
      <div v-if="reputation" class="mt-2 rounded-xl border border-line bg-paper2 px-3.5 py-3 text-[11px] leading-5 text-muted">
        <div class="flex flex-wrap items-center gap-1.5">
          <span
            class="rounded-full px-2 py-0.5 text-[10px] font-semibold"
            :class="reputation.status === 'high' ? 'tag-coral' : reputation.status === 'watch' ? 'tag-amber' : reputation.status === 'low' ? 'tag-green' : 'tag-neutral'"
          >{{ reputation.label }}</span>
          <span class="tag-neutral">{{ reputation.count }} 条已确认</span>
          <span v-if="reputation.uncertain" class="tag-amber">{{ reputation.uncertain }} 条待确认（不计分）</span>
          <span v-if="reputation.sources?.length" class="tag-neutral">{{ reputation.sources.join(' / ') }}</span>
        </div>
        <div v-if="reputation.top_issue_label" class="mt-1 text-[10.5px] text-faint">主要问题：{{ reputation.top_issue_label }}</div>
        <div v-if="reputationMentions.length" class="mt-2 space-y-1.5">
          <div v-for="mention in reputationMentions.slice(0, 4)" :key="mention.id" class="rounded-lg border border-line bg-paper px-2.5 py-1.5">
            <div class="flex items-center gap-1.5 text-[9.5px] text-faint">
              <span>{{ mention.source }}</span>
              <span>· {{ mention.match_status === 'uncertain' ? '待确认' : '已确认' }}</span>
              <span>· 置信度 {{ Math.round(mention.confidence * 100) }}%</span>
              <a v-if="mention.url" :href="mention.url" target="_blank" rel="noopener noreferrer" class="ml-auto inline-flex items-center gap-0.5 text-forest">
                原文 <ExternalLink :size="9" />
              </a>
            </div>
            <div class="mt-0.5 line-clamp-2 text-[10.5px] text-muted">{{ mention.excerpt }}</div>
          </div>
        </div>
        <div v-else class="mt-1.5 text-[10.5px] text-faint">有聚合结论但未返回证据详情；管理端「口碑证据」页可查看。</div>
      </div>
      <p v-else class="mt-2 rounded-xl border border-dashed border-line2 bg-paper2 px-3.5 py-3 text-[11px] text-muted">
        口碑数据不足（中性分）；没有证据就不下结论。
      </p>

      <h4 class="mt-5 flex items-center gap-2 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">
        <Sparkles :size="12" /> 看房清单与检查
      </h4>
      <div class="mt-2 flex flex-wrap gap-1.5">
        <button
          v-for="state in WATCH_STATES"
          :key="state.key"
          class="rounded-full border px-2.5 py-1 text-[10.5px] transition"
          :class="watchState === state.key ? 'border-forest bg-forest-soft font-semibold text-forest' : 'border-line2 bg-paper text-muted'"
          @click="emit('state', state.key, watchNote || null)"
        >
          {{ state.label }}
        </button>
      </div>

      <div class="mt-2 grid grid-cols-2 gap-x-3 gap-y-1.5 rounded-xl border border-line bg-paper2 px-3.5 py-3">
        <label v-for="key in CHECKLIST_KEYS" :key="key" class="flex cursor-pointer items-center gap-2 text-[11.5px] text-muted">
          <input
            type="checkbox"
            class="h-3.5 w-3.5 accent-[#1f5d4a]"
            :checked="inspectionItems[key]"
            @change="toggleItem(key)"
          />
          {{ CHECKLIST_LABELS[key] }}
        </label>
      </div>
      <p class="mt-1 text-[10px] text-faint">已勾 {{ inspectionDone }} / {{ CHECKLIST_KEYS.length }} 项</p>

      <textarea
        v-model="inspectionNote"
        rows="2"
        class="input mt-2 resize-none"
        placeholder="看房记录：隔音、漏水、网络、物业等实际情况"
      />
      <div class="mt-1.5 flex gap-2">
        <input v-model="newPhoto" class="input min-w-0 flex-1" placeholder="照片链接（https://…）" @keydown.enter="addPhoto" />
        <button class="btn" @click="addPhoto">添加照片</button>
      </div>
      <div v-if="photos.length" class="mt-1.5 flex flex-wrap gap-1.5">
        <button
          v-for="(photo, index) in photos"
          :key="photo"
          class="max-w-full truncate rounded-lg border border-line bg-paper2 px-2 py-1 text-[10px] text-muted"
          title="点击移除"
          @click="removePhoto(index)"
        >
          图 {{ index + 1 }} · 点击移除
        </button>
      </div>
      <button class="btn-primary mt-2 w-full" :disabled="loading" @click="saveInspection">保存看房记录</button>

      <div class="mt-3 flex items-center gap-2">
        <input v-model="watchNote" class="input min-w-0 flex-1" placeholder="清单备注（预算/联系进度/看房时间）" />
        <button class="btn" :disabled="loading" @click="saveWatchNote">保存备注</button>
      </div>

      <h4 class="mt-5 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">图片 / AI</h4>
      <div class="mt-2 rounded-xl border border-forest/20 bg-forest-soft/60 px-3.5 py-3 text-[11px] leading-6 text-muted">
        真实版本：封面 pHash 去重 + 视觉标签 + 置信度 + 原文证据。当前未接入，不用演示值冒充。
      </div>
    </template>

    <template #footer>
      <a v-if="listing?.url" :href="listing.url" target="_blank" rel="noopener" class="btn flex-1">
        <ExternalLink :size="13" /> 打开原文
      </a>
      <button v-if="listing" class="btn flex-1" @click="emit('compare', listing)">加入对比</button>
      <button v-if="listing" class="btn-primary flex-1" @click="emit('save', listing)">保存监控</button>
    </template>
  </AppDrawer>
</template>
