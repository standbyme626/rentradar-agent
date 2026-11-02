<script setup lang="ts">
import type { Listing } from '@/api/types'

defineProps<{ cards: Listing[] }>()
const emit = defineEmits<{ open: [listing: Listing] }>()

const money = (value: number | null) => (value == null ? '—' : `¥${value.toLocaleString('zh-CN')}`)
</script>

<template>
  <div v-if="cards.length" class="overflow-hidden rounded-2xl border border-line bg-paper">
    <table class="w-full border-collapse text-left text-[12px]">
      <thead>
        <tr class="bg-paper2 text-[10px] uppercase tracking-wide text-faint">
          <th class="px-4 py-3 font-semibold">房源</th>
          <th class="px-4 py-3 font-semibold">月租</th>
          <th class="px-4 py-3 font-semibold">通勤</th>
          <th class="px-4 py-3 font-semibold">面积</th>
          <th class="px-4 py-3 font-semibold">评分</th>
          <th class="px-4 py-3 font-semibold">取舍</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="item in cards.slice(0, 4)"
          :key="item.id"
          class="cursor-pointer border-t border-line transition hover:bg-paper2"
          @click="emit('open', item)"
        >
          <td class="px-4 py-3">
            <div class="font-semibold text-ink">{{ item.community_name }}</div>
            <div class="mt-0.5 text-[10.5px] text-muted">{{ item.district }} · {{ item.layout }}</div>
          </td>
          <td class="px-4 py-3 font-semibold">{{ money(item.rent) }}</td>
          <td class="px-4 py-3 font-semibold text-forest">{{ item.commute_min ?? '—' }} 分钟</td>
          <td class="px-4 py-3">{{ item.area ?? '—' }}㎡</td>
          <td class="px-4 py-3">
            <span class="tag-green">{{ item.score ?? '—' }}</span>
          </td>
          <td class="px-4 py-3 text-muted">
            {{ (item.rent ?? 0) <= 3000 ? '预算优先' : '通勤/条件均衡' }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
  <div v-else class="rounded-2xl border border-dashed border-line2 bg-paper2 px-6 py-14 text-center text-[12px] text-faint">
    还没有候选，先发一句需求。
  </div>
</template>
