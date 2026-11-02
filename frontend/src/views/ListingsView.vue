<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '@/api/client'
import type { Listing, ListingPage } from '@/api/types'
import ScoreBadge from '@/components/ScoreBadge.vue'
import { formatDateTime, formatRent, statusClass, statusLabels } from '@/lib/format'

const router = useRouter()
const filters = reactive({
  q: '',
  status: '',
  city: 'sz',
  min_rent: '',
  max_rent: '',
  score_min: '',
  scored_only: true,
  sort: 'score_desc',
})
const page = ref(1)
const pageSize = 10
const data = ref<ListingPage | null>(null)
const loading = ref(true)
const error = ref('')

const totalPages = computed(() => (data.value ? Math.max(1, Math.ceil(data.value.total / pageSize)) : 1))

function buildQuery(): string {
  const params = new URLSearchParams()
  params.set('page', String(page.value))
  params.set('page_size', String(pageSize))
  if (filters.q.trim()) params.set('q', filters.q.trim())
  if (filters.status) params.set('status', filters.status)
  if (filters.city) params.set('city', filters.city)
  if (filters.min_rent) params.set('min_rent', filters.min_rent)
  if (filters.max_rent) params.set('max_rent', filters.max_rent)
  if (filters.score_min) params.set('score_min', filters.score_min)
  if (filters.scored_only) params.set('scored_only', 'true')
  params.set('sort', filters.sort)
  return params.toString()
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api<ListingPage>(`/api/listings?${buildQuery()}`)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  filters.q = ''
  filters.status = ''
  filters.city = 'sz'
  filters.min_rent = ''
  filters.max_rent = ''
  filters.score_min = ''
  filters.scored_only = true
  filters.sort = 'score_desc'
  page.value = 1
  load()
}

function openListing(listing: Listing) {
  router.push(`/listings/${listing.id}`)
}

watch([() => filters.status, () => filters.sort, () => filters.city, () => filters.scored_only], () => {
  page.value = 1
  load()
})

watch(page, load)
onMounted(load)
</script>

<template>
  <div class="space-y-4">
    <div class="card p-4">
      <div class="grid gap-3 md:grid-cols-12">
        <div class="md:col-span-3">
          <label class="label">搜索</label>
          <input v-model="filters.q" class="input w-full" placeholder="小区 / 标题" @keyup.enter="search" />
        </div>
        <div class="md:col-span-2">
          <label class="label">状态</label>
          <select v-model="filters.status" class="input w-full">
            <option value="">全部</option>
            <option value="active">在售</option>
            <option value="relisted">重新上架</option>
            <option value="suspect">疑似</option>
            <option value="gone">已下架</option>
          </select>
        </div>
        <div class="md:col-span-2">
          <label class="label">租金下限</label>
          <input v-model="filters.min_rent" class="input w-full" inputmode="numeric" placeholder="3000" />
        </div>
        <div class="md:col-span-2">
          <label class="label">租金上限</label>
          <input v-model="filters.max_rent" class="input w-full" inputmode="numeric" placeholder="6000" />
        </div>
        <div class="md:col-span-1">
          <label class="label">评分≥</label>
          <input v-model="filters.score_min" class="input w-full" inputmode="numeric" placeholder="70" />
        </div>
        <div class="md:col-span-2">
          <label class="label">排序</label>
          <select v-model="filters.sort" class="input w-full">
            <option value="score_desc">评分从高到低</option>
            <option value="newest">最新发现</option>
            <option value="rent_asc">租金从低到高</option>
            <option value="rent_desc">租金从高到低</option>
          </select>
        </div>
      </div>
      <div class="mt-3 flex items-center justify-between">
        <div class="flex items-center gap-4">
          <div class="text-xs text-slate-400">共 {{ data?.total ?? 0 }} 套 · 第 {{ page }} / {{ totalPages }} 页</div>
          <label class="flex items-center gap-2 text-xs text-slate-500">
            <input v-model="filters.scored_only" type="checkbox" class="h-4 w-4 rounded border-slate-300 text-emerald-600" />
            只看已评分
          </label>
        </div>
        <div class="flex gap-2">
          <button class="btn-ghost" @click="reset">重置</button>
          <button class="btn-primary" @click="search">筛选</button>
        </div>
      </div>
    </div>

    <div v-if="error" class="card border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
      加载失败：{{ error }}
    </div>

    <div class="card overflow-hidden">
      <div v-if="loading" class="p-10 text-center text-sm text-slate-400">加载中…</div>
      <div v-else-if="!data || data.items.length === 0" class="p-10 text-center text-sm text-slate-400">
        没有符合条件的房源
      </div>
      <table v-else class="min-w-full text-sm">
        <thead class="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th class="px-4 py-3 text-left font-medium">房源</th>
            <th class="px-4 py-3 text-left font-medium">租金</th>
            <th class="px-4 py-3 text-left font-medium">评分</th>
            <th class="px-4 py-3 text-left font-medium">状态</th>
            <th class="px-4 py-3 text-left font-medium">标签</th>
            <th class="px-4 py-3 text-left font-medium">首次发现</th>
            <th class="px-4 py-3" />
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr
            v-for="listing in data.items"
            :key="listing.id"
            class="cursor-pointer transition hover:bg-slate-50"
            @click="openListing(listing)"
          >
            <td class="px-4 py-3">
              <div class="font-medium text-slate-800">{{ listing.title }}</div>
              <div class="mt-0.5 text-xs text-slate-400">
                {{ listing.community_name }} · {{ listing.layout }} · {{ listing.area }}㎡ · {{ listing.orientation }} · {{ listing.floor }}
              </div>
            </td>
            <td class="px-4 py-3 font-medium text-slate-800">{{ formatRent(listing.rent) }}</td>
            <td class="px-4 py-3"><ScoreBadge :score="listing.score" /></td>
            <td class="px-4 py-3">
              <span class="badge" :class="statusClass(listing.status)">{{ statusLabels[listing.status] ?? listing.status }}</span>
            </td>
            <td class="px-4 py-3">
              <div class="flex flex-wrap gap-1">
                <span v-for="tag in listing.tags.slice(0, 3)" :key="tag" class="badge bg-slate-100 text-slate-600">{{ tag }}</span>
              </div>
            </td>
            <td class="px-4 py-3 text-xs text-slate-400">{{ formatDateTime(listing.first_seen_at) }}</td>
            <td class="px-4 py-3 text-right text-xs text-emerald-600">详情 →</td>
          </tr>
        </tbody>
      </table>
      <div v-if="data && data.total > pageSize" class="flex items-center justify-between border-t border-slate-100 px-4 py-3">
        <button class="btn-ghost" :disabled="page <= 1" @click="page--">上一页</button>
        <span class="text-xs text-slate-400">{{ page }} / {{ totalPages }}</span>
        <button class="btn-ghost" :disabled="page >= totalPages" @click="page++">下一页</button>
      </div>
    </div>
  </div>
</template>
