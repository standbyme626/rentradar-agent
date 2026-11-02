<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import type { DeliveryProbe, InspectionData, ListingDetail } from '@/api/types'
import ScoreBadge from '@/components/ScoreBadge.vue'
import {
  eventClass,
  eventLabels,
  formatDateTime,
  formatRent,
  notifyLabel,
  reasonLabels,
  statusClass,
  statusLabels,
} from '@/lib/format'

const route = useRoute()
const router = useRouter()
const detail = ref<ListingDetail | null>(null)
const loading = ref(true)
const error = ref('')
const message = ref('')
const watchState = ref('new')

const stateOptions = [
  { value: 'new', label: '未处理' },
  { value: 'seen', label: '已看' },
  { value: 'contacted', label: '已联系' },
  { value: 'viewed', label: '已看房' },
  { value: 'rejected', label: '已淘汰' },
]

const mealLabels: Record<string, string> = {
  lunch: '午餐',
  dinner: '晚餐',
  late_night: '夜宵',
  other: '非餐点',
}

function probeTitle(probe: DeliveryProbe): string {
  const period = mealLabels[probe.meal_period ?? ''] ?? probe.meal_period ?? '实测'
  return `${period} · ${probe.platform}`
}

function probeEta(probe: DeliveryProbe): string {
  if (probe.eta_min_low == null) return '—'
  if (probe.eta_min_high == null || probe.eta_min_low === probe.eta_min_high) {
    return `${probe.eta_min_low} 分钟`
  }
  return `${probe.eta_min_low}-${probe.eta_min_high} 分钟`
}

const checklist = [
  { key: 'soundproofing', label: '隔音' },
  { key: 'leak', label: '漏水' },
  { key: 'water', label: '水压' },
  { key: 'power', label: '电 / 电费' },
  { key: 'network', label: '宽带 / 信号' },
  { key: 'delivery', label: '外卖可送上门' },
  { key: 'property', label: '物业' },
  { key: 'elevator', label: '电梯' },
]
const inspection = reactive<InspectionData>({ items: {}, note: '', photos: [] })
const inspectionMessage = ref('')

async function loadInspection() {
  try {
    const data = await api<InspectionData>(`/api/listings/${route.params.id}/inspection`)
    inspection.items = { ...data.items }
    inspection.note = data.note ?? ''
    inspection.photos = data.photos ?? []
  } catch {
    for (const item of checklist) inspection.items[item.key] = false
  }
}

async function saveInspection() {
  inspectionMessage.value = ''
  try {
    await api(`/api/listings/${route.params.id}/inspection`, {
      method: 'PUT',
      body: JSON.stringify({
        items: inspection.items,
        note: inspection.note,
        photos: inspection.photos,
      }),
    })
    inspectionMessage.value = '看房清单已保存'
  } catch (err) {
    inspectionMessage.value = err instanceof Error ? err.message : String(err)
  }
}

const maxRent = computed(() =>
  detail.value?.snapshots.length ? Math.max(...detail.value.snapshots.map((item) => item.rent)) : 1,
)

const reasonEntries = computed(() => {
  if (!detail.value) return []
  return Object.entries(detail.value.score_reasons).map(([key, value]) => ({
    key,
    label: reasonLabels[key] ?? key,
    text: Array.isArray(value) ? (value.length ? value.join('、') : '无') : value == null ? '—' : String(value),
  }))
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    detail.value = await api<ListingDetail>(`/api/listings/${route.params.id}`)
    watchState.value = detail.value.watch_state ?? 'new'
    await loadInspection()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

async function saveState() {
  message.value = ''
  try {
    await api(`/api/listings/${route.params.id}/state`, {
      method: 'PATCH',
      body: JSON.stringify({ state: watchState.value }),
    })
    message.value = '台账状态已保存'
  } catch (err) {
    message.value = err instanceof Error ? err.message : String(err)
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-5">
    <button class="btn-ghost" @click="router.back()">← 返回列表</button>

    <div v-if="error" class="card border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
      加载失败：{{ error }}
    </div>
    <div v-else-if="loading" class="card h-48 animate-pulse bg-slate-50" />

    <template v-else-if="detail">
      <section class="card p-5">
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div class="flex items-center gap-2">
              <span class="badge" :class="statusClass(detail.status)">{{ statusLabels[detail.status] ?? detail.status }}</span>
              <span class="text-xs text-slate-400">{{ detail.city_code }} · {{ detail.source_code }}</span>
            </div>
            <h2 class="mt-2 text-xl font-semibold text-slate-900">{{ detail.title }}</h2>
            <div class="mt-1 text-sm text-slate-500">
              {{ detail.community_name }} · {{ detail.district }} · {{ detail.layout }} · {{ detail.area }}㎡ ·
              {{ detail.orientation }} · {{ detail.floor }}
            </div>
            <div class="mt-3 flex flex-wrap gap-1">
              <span v-for="tag in detail.tags" :key="tag" class="badge bg-slate-100 text-slate-600">{{ tag }}</span>
            </div>
          </div>
          <div class="text-right">
            <div class="text-3xl font-semibold text-slate-900">{{ formatRent(detail.rent) }}</div>
            <div class="mt-2 flex items-center justify-end gap-2 text-xs text-slate-400">
              评分 <ScoreBadge :score="detail.score" />
            </div>
            <a :href="detail.url" target="_blank" rel="noreferrer" class="mt-3 inline-block text-sm text-emerald-600 hover:underline">
              打开原始房源 →
            </a>
          </div>
        </div>
      </section>

      <div class="grid gap-5 lg:grid-cols-3">
        <section class="card p-5 lg:col-span-2">
          <h3 class="text-sm font-semibold text-slate-900">评分理由</h3>
          <div class="mt-4 grid gap-3 sm:grid-cols-2">
            <div v-for="item in reasonEntries" :key="item.key" class="rounded-xl border border-slate-100 p-3">
              <div class="text-xs font-medium uppercase tracking-wide text-slate-400">{{ item.label }}</div>
              <div class="mt-1 text-sm leading-6 text-slate-700">{{ item.text }}</div>
            </div>
          </div>
        </section>

        <section class="card p-5">
          <h3 class="text-sm font-semibold text-slate-900">台账</h3>
          <p class="mt-1 text-xs text-slate-400">记录看房进度，避免重复沟通</p>
          <select v-model="watchState" class="input mt-4 w-full">
            <option v-for="option in stateOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
          </select>
          <button class="btn-primary mt-3 w-full" @click="saveState">保存状态</button>
          <div v-if="message" class="mt-2 text-xs text-emerald-600">{{ message }}</div>
          <div class="mt-5 border-t border-slate-100 pt-4 text-xs text-slate-400">
            <div>首次发现：{{ formatDateTime(detail.first_seen_at) }}</div>
            <div class="mt-1">最近出现：{{ formatDateTime(detail.last_seen_at) }}</div>
            <div class="mt-1">房源编号：{{ detail.source_listing_id }}</div>
          </div>
        </section>
      </div>

      <section class="card p-5">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 class="text-sm font-semibold text-slate-900">看房清单</h3>
            <p class="mt-1 text-xs text-slate-400">现场逐项确认，勾选代表通过</p>
          </div>
          <button class="btn-primary" @click="saveInspection">保存清单</button>
        </div>
        <div class="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <label
            v-for="item in checklist"
            :key="item.key"
            class="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-100 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
          >
            <input
              v-model="inspection.items[item.key]"
              type="checkbox"
              class="h-4 w-4 rounded border-slate-300 text-emerald-600"
            />
            {{ item.label }}
          </label>
        </div>
        <textarea
          v-model="inspection.note"
          class="input mt-3 w-full"
          rows="3"
          placeholder="补充：隔音实测、漏水痕迹、水压、电费单价、宽带运营商、外卖柜位置、物业响应…"
        />
        <div v-if="inspectionMessage" class="mt-2 text-xs text-emerald-600">{{ inspectionMessage }}</div>
      </section>

      <section class="card p-5">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 class="text-sm font-semibold text-slate-900">外卖实测</h3>
            <p class="mt-1 text-xs text-slate-400">美团真机探针 · 虚拟定位到小区坐标</p>
          </div>
          <span class="badge bg-slate-100 text-slate-500">{{ detail.delivery_probes.length }} 条</span>
        </div>
        <div v-if="detail.delivery_probes.length === 0" class="mt-4 rounded-xl border border-dashed border-slate-200 p-4 text-sm text-slate-400">
          暂无实测样本。先让 iPhone 美团停在外卖首页，再运行 probe。
        </div>
        <div v-else class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div v-for="probe in detail.delivery_probes" :key="probe.id" class="rounded-xl border border-slate-100 p-3">
            <div class="flex items-center justify-between">
              <div class="text-xs font-medium text-slate-600">{{ probeTitle(probe) }}</div>
              <div class="text-xs text-slate-400">{{ formatDateTime(probe.probe_at) }}</div>
            </div>
            <div class="mt-2 text-lg font-semibold text-slate-900">{{ probeEta(probe) }}</div>
            <div class="mt-1 text-xs text-slate-500">
              配送费 {{ probe.fee == null ? '—' : `¥${probe.fee.toFixed(2)}` }} · 商家 {{ probe.merchant_count ?? '—' }} 家
            </div>
            <div class="mt-1 text-xs text-slate-400">{{ probe.address_label ?? '地址未采集' }}</div>
          </div>
        </div>
      </section>

      <div class="grid gap-5 lg:grid-cols-2">
        <section class="card p-5">
          <h3 class="text-sm font-semibold text-slate-900">价格历史</h3>
          <div v-if="detail.snapshots.length === 0" class="mt-6 text-sm text-slate-400">暂无快照</div>
          <div v-else class="mt-4 space-y-3">
            <div v-for="snapshot in [...detail.snapshots].reverse()" :key="snapshot.seen_at" class="flex items-center gap-3">
              <div class="w-20 text-xs text-slate-400">{{ formatDateTime(snapshot.seen_at) }}</div>
              <div class="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                <div
                  class="h-full rounded-full bg-emerald-400"
                  :style="{ width: `${Math.max(6, (snapshot.rent / maxRent) * 100)}%` }"
                />
              </div>
              <div class="w-16 text-right text-xs font-medium text-slate-600">{{ formatRent(snapshot.rent) }}</div>
            </div>
          </div>
        </section>

        <section class="card p-5">
          <h3 class="text-sm font-semibold text-slate-900">事件</h3>
          <div v-if="detail.events.length === 0" class="mt-6 text-sm text-slate-400">暂无事件</div>
          <div v-else class="mt-4 divide-y divide-slate-100">
            <div v-for="event in detail.events" :key="event.id" class="flex items-center gap-3 py-3">
              <span class="badge" :class="eventClass(event.type)">{{ eventLabels[event.type] ?? event.type }}</span>
              <div class="flex-1 text-xs text-slate-400">{{ formatDateTime(event.created_at) }}</div>
              <span class="text-xs text-slate-400">{{ notifyLabel(event.payload, event.notified) }}</span>
            </div>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>
