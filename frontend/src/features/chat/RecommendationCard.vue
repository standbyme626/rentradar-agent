<script setup lang="ts">
import { computed } from 'vue'
import type { Listing } from '@/api/types'
import CoverPlaceholder from '@/components/ui/CoverPlaceholder.vue'
import ScoreRing from '@/components/ui/ScoreRing.vue'

const props = withDefaults(
  defineProps<{
    listing: Listing
    index: number
    selected?: boolean
  }>(),
  { selected: false },
)
const emit = defineEmits<{
  open: [listing: Listing]
  compare: [listing: Listing]
}>()

const money = (value: number | null) => (value == null ? '—' : `¥${value.toLocaleString('zh-CN')}`)
const name = computed(() => props.listing.community_name || '房源')
const reasons = computed(() => props.listing.score_reasons ?? {})
const tags = computed(() => {
  const condition = (reasons.value.condition ?? '').split(' / ')
  return [...new Set([...(props.listing.tags ?? []), ...condition])].filter(Boolean).slice(0, 4)
})
const commuteType = computed(() =>
  (reasons.value.commute ?? '').includes('地铁') ? '地铁+步行' : '公共交通',
)
const tagClass = (tag: string) => {
  if (tag.includes('精装')) return 'tag-green'
  if (tag.includes('新上')) return 'tag-amber'
  return 'tag-neutral'
}
</script>

<template>
  <article
    class="group cursor-pointer overflow-hidden rounded-2xl border border-line bg-paper shadow-card transition hover:-translate-y-0.5 hover:border-line2 hover:shadow-lift"
    @click="emit('open', listing)"
  >
    <div class="relative">
      <CoverPlaceholder :name="name" :variant="index" height="168px" />
      <div class="absolute right-3 top-3 rounded-2xl bg-paper/90 p-1 shadow-sm">
        <ScoreRing :score="listing.score" :size="50" />
      </div>
    </div>
    <div class="p-4">
      <h3 class="truncate text-[15.5px] font-semibold leading-6 text-ink">{{ name }}</h3>
      <p class="mt-0.5 truncate text-[11px] text-muted">
        {{ listing.district || '—' }} · {{ listing.layout || '—' }} · {{ listing.area ?? '—' }}㎡
      </p>

      <div class="mt-2 text-[22px] font-bold tracking-tight text-ink">
        {{ money(listing.rent) }}<span class="text-[11px] font-normal text-muted"> /月</span>
      </div>
      <div class="mt-0.5 flex flex-wrap gap-x-2.5 gap-y-1 text-[11.5px] text-muted">
        <span>通勤 <b class="font-semibold text-ink">{{ listing.commute_min ?? '—' }} 分钟</b></span>
        <span>{{ commuteType }}</span>
        <span>{{ listing.samples ?? 1 }} 次样本</span>
      </div>

      <div class="mt-2 flex flex-wrap gap-1">
        <span v-for="tag in tags" :key="tag" :class="tagClass(tag)">{{ tag }}</span>
      </div>

      <div class="mt-3 border-t border-dashed border-line pt-2.5 text-[11.5px] leading-6 text-muted">
        <b class="font-semibold text-ink">为什么推荐</b><br />
        {{ reasons.price || '价格待核实' }}
      </div>

      <div class="mt-3 flex gap-2">
        <button class="btn-dark flex-1 py-1.5 text-[11.5px]" @click.stop="emit('open', listing)">
          看详情
        </button>
        <button
          class="btn flex-1 py-1.5 text-[11.5px]"
          :class="selected ? 'border-forest bg-forest-soft text-forest' : ''"
          @click.stop="emit('compare', listing)"
        >
          {{ selected ? '已加入对比' : '加入对比' }}
        </button>
      </div>
    </div>
  </article>
</template>
