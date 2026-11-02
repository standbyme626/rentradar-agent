<script setup lang="ts">
import { computed } from 'vue'
import { ExternalLink, Sparkles } from 'lucide-vue-next'
import type { Listing } from '@/api/types'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import CoverPlaceholder from '@/components/ui/CoverPlaceholder.vue'
import Sparkline from '@/components/ui/Sparkline.vue'

const props = defineProps<{ listing: Listing | null }>()
const emit = defineEmits<{
  close: []
  compare: [listing: Listing]
  save: [listing: Listing]
}>()

const money = (value: number | null) => (value == null ? '—' : `¥${value.toLocaleString('zh-CN')}`)
const subtitle = computed(() => {
  const item = props.listing
  if (!item) return ''
  return `${item.district || '—'} · ${item.layout || '—'} · ${item.area ?? '—'}㎡ · ${money(item.rent)}/月`
})
const bars = [
  { label: '性价比', value: 35, max: 35 },
  { label: '通勤', value: 25, max: 25 },
  { label: '居住条件', value: 13, max: 15 },
  { label: '生活便利', value: 8, max: 10 },
  { label: '口碑', value: 5, max: 10 },
  { label: '新鲜度', value: 5, max: 5 },
]
const tags = computed(() => {
  const item = props.listing
  if (!item) return []
  return [...new Set([...(item.tags ?? []), ...((item.score_reasons?.condition ?? '').split(' / '))])]
    .filter(Boolean)
    .slice(0, 5)
})
</script>

<template>
  <AppDrawer
    :open="!!listing"
    :title="listing?.community_name ?? '房源详情'"
    :subtitle="subtitle"
    @close="emit('close')"
  >
    <template v-if="listing">
      <CoverPlaceholder :name="listing.community_name" :variant="0" height="140px" />
      <div class="mt-2 grid grid-cols-3 gap-2">
        <div class="grid h-20 place-items-end rounded-lg bg-forest-soft/70 p-2 text-[9.5px] text-forest">图 1 · 待抓取</div>
        <div class="grid h-20 place-items-end rounded-lg bg-sand p-2 text-[9.5px] text-muted">图 2 · 待抓取</div>
        <div class="grid h-20 place-items-end rounded-lg bg-[#e2e5ef] p-2 text-[9.5px] text-[#4c5772]">图 3 · 待抓取</div>
      </div>

      <div class="mt-3 flex flex-wrap gap-1.5">
        <span class="tag-green">评分 {{ listing.score ?? '—' }}</span>
        <span class="tag-neutral">通勤 {{ listing.commute_min ?? '—' }} 分钟</span>
        <span class="tag-neutral">{{ listing.samples ?? 1 }} 次样本</span>
        <span class="tag-amber">图片待采集</span>
        <span v-for="tag in tags" :key="tag" class="tag-neutral">{{ tag }}</span>
      </div>

      <h4 class="mt-5 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">评分拆解</h4>
      <div class="mt-2 space-y-2">
        <div v-for="bar in bars" :key="bar.label">
          <div class="flex justify-between text-[11px] text-muted">
            <span>{{ bar.label }}</span>
            <span>{{ bar.value }} / {{ bar.max }}</span>
          </div>
          <div class="mt-1 h-1.5 overflow-hidden rounded-full bg-sand">
            <div class="h-full rounded-full bg-forest" :style="{ width: `${(bar.value / bar.max) * 100}%` }" />
          </div>
        </div>
      </div>

      <h4 class="mt-5 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">为什么推荐</h4>
      <div class="mt-2 rounded-xl border border-line bg-paper2 px-3.5 py-3 text-[11.5px] leading-6 text-muted">
        {{ listing.score_reasons?.price || '价格待核实' }}<br />
        {{ listing.score_reasons?.commute || '通勤待核实' }}<br />
        {{ listing.score_reasons?.condition || '条件待核实' }}
      </div>

      <h4 class="mt-5 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">通勤路线（演示）</h4>
      <div class="mt-2 rounded-xl border border-line bg-paper2 px-3.5 py-3 text-[11.5px] leading-6 text-muted">
        深圳会展中心 → {{ listing.community_name }} · 公共交通 {{ listing.commute_min ?? '—' }} 分钟 · 单次采样 · 换乘/步行明细待接入
      </div>

      <h4 class="mt-5 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">价格走势</h4>
      <Sparkline :points="[listing.rent ?? 0, listing.rent ?? 0, (listing.rent ?? 0) - 30, listing.rent ?? 0, listing.rent ?? 0]" />
      <p class="text-[10px] text-faint">近 30 天 1 个价格点；历史仍在积累。</p>

      <h4 class="mt-5 flex items-center gap-2 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">
        <Sparkles :size="12" /> 图片 / AI（设计占位）
      </h4>
      <div class="mt-2 rounded-xl border border-forest/20 bg-forest-soft/60 px-3.5 py-3 text-[11px] leading-6 text-muted">
        真实版本：候选详情页抓 3–6 张图 → pHash 去重 → Qwen-VL 标签（实拍/装修/采光/可见问题/图文一致）→ 置信度 + 原图证据。当前未接入。
      </div>
    </template>

    <template #footer>
      <a
        v-if="listing?.url"
        :href="listing.url"
        target="_blank"
        rel="noopener"
        class="btn flex-1"
      >
        <ExternalLink :size="13" /> 打开原文
      </a>
      <button v-if="listing" class="btn flex-1" @click="emit('compare', listing)">加入对比</button>
      <button v-if="listing" class="btn-primary flex-1" @click="emit('save', listing)">保存监控</button>
    </template>
  </AppDrawer>
</template>
