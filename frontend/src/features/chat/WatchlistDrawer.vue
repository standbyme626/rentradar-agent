<script setup lang="ts">
import { computed, ref } from 'vue'
import { Download, Eye, PhoneCall, XCircle } from 'lucide-vue-next'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { CHECKLIST_KEYS, checkedCount, stateClass, stateLabel, WATCH_STATES } from '@/lib/watchlist'
import { useWatchlistStore } from '@/stores/watchlist'

const emit = defineEmits<{ 'open-detail': [id: number] }>()
const store = useWatchlistStore()
const filter = ref('all')

const filters = computed(() => [
  { key: 'all', label: '全部', count: store.entries.length },
  ...WATCH_STATES.filter((item) => (store.counts[item.key] ?? 0) > 0).map((item) => ({
    key: item.key,
    label: item.label,
    count: store.counts[item.key] ?? 0,
  })),
])

const filtered = computed(() =>
  filter.value === 'all'
    ? store.entries
    : store.entries.filter((item) => item.state === filter.value),
)

const ageLabel = (value: string | null) => {
  if (!value) return '—'
  return new Date(value).toLocaleString('zh-CN', {
    hour12: false,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <AppDrawer
    :open="store.open"
    title="看房清单"
    :subtitle="`${store.active.length} 套在跟 · ${store.counts.viewed ?? 0} 套已看 · ${store.counts.rejected ?? 0} 套已淘汰`"
    @close="store.closeLedger()"
  >
    <div class="flex flex-wrap items-center gap-1.5">
      <button
        v-for="item in filters"
        :key="item.key"
        class="rounded-full border px-2.5 py-1 text-[10.5px] transition"
        :class="filter === item.key ? 'border-forest bg-forest-soft font-semibold text-forest' : 'border-line2 bg-paper text-muted'"
        @click="filter = item.key"
      >
        {{ item.label }} {{ item.count }}
      </button>
      <button class="btn ml-auto btn-sm" :disabled="!store.entries.length" @click="store.exportCsv()">
        <Download :size="12" /> 导出 CSV
      </button>
    </div>

    <div v-if="store.loading" class="mt-4 rounded-xl border border-line bg-paper2 px-3.5 py-3 text-[11px] text-muted">
      正在读取看房清单…
    </div>
    <div v-else-if="store.error" class="mt-4 rounded-xl border border-coral/25 bg-coral-soft px-3.5 py-3 text-[11px] text-coral">
      {{ store.error }}
      <button class="ml-2 underline" @click="store.load()">重试</button>
    </div>
    <div v-else-if="!filtered.length" class="mt-4 rounded-xl border border-dashed border-line2 bg-paper2 px-5 py-12 text-center text-[12px] text-faint">
      还没有加入清单的房源。在房源详情里选一个状态，就会出现在这里。
    </div>
    <div v-else class="mt-3 space-y-2">
      <article
        v-for="entry in filtered"
        :key="entry.listing.id"
        class="rounded-xl border border-line bg-paper2 px-3.5 py-3"
      >
        <div class="flex items-start gap-2">
          <button class="min-w-0 flex-1 text-left" @click="emit('open-detail', entry.listing.id)">
            <div class="truncate text-[12.5px] font-semibold text-ink">
              {{ entry.listing.community_name || '房源' }} · {{ entry.listing.layout || '—' }}
            </div>
            <div class="mt-0.5 text-[10.5px] text-muted">
              ¥{{ entry.listing.rent ?? '—' }}/月 · 评分 {{ entry.listing.score ?? '—' }} · 检查
              {{ checkedCount(entry.inspection.items) }}/{{ CHECKLIST_KEYS.length }}
            </div>
          </button>
          <span :class="stateClass(entry.state)">{{ stateLabel(entry.state) }}</span>
          <button class="btn-ghost btn-sm" title="查看详情" @click="emit('open-detail', entry.listing.id)">
            <Eye :size="13" />
          </button>
        </div>
        <p v-if="entry.note" class="mt-1 line-clamp-2 text-[10.5px] leading-5 text-muted">{{ entry.note }}</p>
        <p v-if="entry.inspection.note" class="mt-0.5 line-clamp-2 text-[10.5px] leading-5 text-faint">
          看房记录：{{ entry.inspection.note }}
        </p>
        <div class="mt-1 flex items-center gap-2">
          <span class="text-[9.5px] text-faint">更新 {{ ageLabel(entry.updated_at) }}</span>
          <div class="ml-auto flex flex-wrap gap-1">
            <button class="tag-neutral" @click="store.setState(entry, 'contacted')">
              <PhoneCall :size="10" class="mr-0.5 inline" /> 已联系
            </button>
            <button class="tag-neutral" @click="store.setState(entry, 'viewed')">
              <Eye :size="10" class="mr-0.5 inline" /> 已看房
            </button>
            <button class="tag-coral" @click="store.setState(entry, 'rejected')">
              <XCircle :size="10" class="mr-0.5 inline" /> 淘汰
            </button>
          </div>
        </div>
      </article>
    </div>
    <p class="mt-3 text-[10px] leading-5 text-faint">
      CSV 含状态/备注/检查项/照片数；照片暂用链接记录，文件上传未接入。
    </p>
  </AppDrawer>
</template>
