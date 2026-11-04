<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { Maximize2, Minimize2, Minus, Plus, SlidersHorizontal } from 'lucide-vue-next'
import type { MapCommunity, MapData, TransitCatalog } from '@/api/types'
import { mapApi } from '@/api/services/maps'
import { useChatStore } from '@/stores/chat'

const store = useChatStore()
const container = ref<HTMLElement | null>(null)
const data = ref<MapData | null>(null)
const transit = ref<TransitCatalog | null>(null)
const showTransit = ref(true)
const status = ref<'loading' | 'ready' | 'error'>('loading')
const message = ref('')
const width = ref(820)
const height = ref(560)
const expanded = ref(false)
const center = ref<[number, number]>([114.06, 22.55])
const zoom = ref(11)
const commuteFilter = ref(0)
const colorMode = ref<'rent' | 'score'>('rent')
const activeId = ref<number | null>(null)
const tileFailed = ref(false)
let dragging = false
let dragX = 0
let dragY = 0
let dragCenter: [number, number] = [0, 0]

const TILE = 256
const WORLD = computed(() => TILE * 2 ** zoom.value)
const visible = computed(() =>
  (data.value?.communities ?? []).filter(
    (item) => !commuteFilter.value || (item.commute_p50 != null && item.commute_p50 <= commuteFilter.value),
  ),
)
const active = computed(() => visible.value.find((item) => item.id === activeId.value) ?? null)

const transitLines = computed(() => {
  if (!transit.value || !showTransit.value) return []
  return transit.value.lines.map((line) => ({
    ...line,
    color: line.color.startsWith('#') ? line.color : `#${line.color}`,
    points: line.stations.map((station) => {
      const point = project(station.lng, station.lat)
      return {
        ...station,
        x: point.x - centerPx.value.x + width.value / 2,
        y: point.y - centerPx.value.y + height.value / 2,
      }
    }),
  }))
})

function project(lng: number, lat: number, world = WORLD.value) {
  const sin = Math.sin((lat * Math.PI) / 180)
  return {
    x: ((lng + 180) / 360) * world,
    y: (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * world,
  }
}

function unproject(x: number, y: number, world = WORLD.value): [number, number] {
  const lng = (x / world) * 360 - 180
  const n = Math.PI - (2 * Math.PI * y) / world
  const lat = (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)))
  return [lng, lat]
}

const centerPx = computed(() => project(center.value[0], center.value[1]))
const markers = computed(() =>
  visible.value
    .map((item) => {
      const point = project(item.lng, item.lat)
      return {
        item,
        left: point.x - centerPx.value.x + width.value / 2,
        top: point.y - centerPx.value.y + height.value / 2,
      }
    })
    .filter((marker) => marker.left > -80 && marker.left < width.value + 80 && marker.top > -40 && marker.top < height.value + 40),
)
const tiles = computed(() => {
  if (!data.value?.tiles.enabled || tileFailed.value) return []
  const n = 2 ** zoom.value
  const left = centerPx.value.x - width.value / 2
  const top = centerPx.value.y - height.value / 2
  const x0 = Math.floor(left / TILE)
  const x1 = Math.floor((left + width.value) / TILE)
  const y0 = Math.max(0, Math.floor(top / TILE))
  const y1 = Math.min(n - 1, Math.floor((top + height.value) / TILE))
  const result: Array<{ key: string; url: string; left: number; top: number }> = []
  for (let x = x0; x <= x1; x += 1) {
    for (let y = y0; y <= y1; y += 1) {
      const wrapped = ((x % n) + n) % n
      result.push({
        key: `${x}-${y}`,
        url: `/api/maps/tiles/vec/${zoom.value}/${wrapped}/${y}`,
        left: x * TILE - left,
        top: y * TILE - top,
      })
    }
  }
  return result
})
const labelTiles = computed(() => {
  if (!data.value?.tiles.enabled || tileFailed.value) return []
  const n = 2 ** zoom.value
  const left = centerPx.value.x - width.value / 2
  const top = centerPx.value.y - height.value / 2
  const x0 = Math.floor(left / TILE)
  const x1 = Math.floor((left + width.value) / TILE)
  const y0 = Math.max(0, Math.floor(top / TILE))
  const y1 = Math.min(n - 1, Math.floor((top + height.value) / TILE))
  const result: Array<{ key: string; url: string; left: number; top: number }> = []
  for (let x = x0; x <= x1; x += 1) {
    for (let y = y0; y <= y1; y += 1) {
      const wrapped = ((x % n) + n) % n
      result.push({
        key: `${x}-${y}`,
        url: `/api/maps/tiles/cva/${zoom.value}/${wrapped}/${y}`,
        left: x * TILE - left,
        top: y * TILE - top,
      })
    }
  }
  return result
})
const rentMax = computed(() => Math.max(1, ...visible.value.map((item) => item.median_rent ?? 0)))

function money(value: number | null | undefined) {
  return value == null ? '—' : `¥${value.toLocaleString('zh-CN')}`
}

function markerTone(item: MapCommunity) {
  if (colorMode.value === 'score') {
    const score = item.avg_score ?? 0
    return score >= 82 ? 'bg-forest text-white' : score >= 74 ? 'bg-amber text-white' : 'bg-sand text-ink'
  }
  const ratio = (item.median_rent ?? 0) / rentMax.value
  return ratio > 0.72 ? 'bg-coral text-white' : ratio > 0.45 ? 'bg-amber text-ink' : 'bg-forest text-white'
}

function markerLabel(item: MapCommunity) {
  if (colorMode.value === 'score') return `${item.avg_score ?? '—'}分`
  return item.median_rent ? `¥${item.median_rent}` : '—'
}

function setZoom(next: number) {
  const clamped = Math.max(9, Math.min(15, next))
  if (clamped === zoom.value) return
  zoom.value = clamped
  tileFailed.value = false
}

function onPointerDown(event: PointerEvent) {
  if ((event.target as HTMLElement).closest('button')) return
  dragging = true
  dragX = event.clientX
  dragY = event.clientY
  dragCenter = [...center.value]
  ;(event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId)
}

function onPointerMove(event: PointerEvent) {
  if (!dragging) return
  const dx = event.clientX - dragX
  const dy = event.clientY - dragY
  const start = project(dragCenter[0], dragCenter[1])
  center.value = unproject(start.x - dx, start.y - dy)
}

function onPointerUp() {
  dragging = false
}

function onTileError() {
  tileFailed.value = true
}

async function toggleExpand() {
  expanded.value = !expanded.value
  await nextTick()
  measure()
  fit()
}

function fit() {
  const items = data.value?.communities ?? []
  if (!items.length) return
  const lngs = items.map((item) => item.lng)
  const lats = items.map((item) => item.lat)
  const p1 = project(Math.min(...lngs), Math.max(...lats), TILE)
  const p2 = project(Math.max(...lngs), Math.min(...lats), TILE)
  const dx = Math.max(1, p2.x - p1.x)
  const dy = Math.max(1, p2.y - p1.y)
  const fitZoom = Math.floor(Math.log2(Math.min((width.value * 0.82) / dx, (height.value * 0.78) / dy)))
  zoom.value = Math.max(9, Math.min(14, fitZoom))
  center.value = data.value?.center ?? center.value
}

function measure() {
  if (container.value) width.value = Math.max(320, container.value.clientWidth)
  const viewport = window.innerHeight || 900
  if (expanded.value) {
    height.value = Math.max(520, viewport - 120)
  } else {
    const ratio = window.innerWidth < 840 ? 0.64 : 0.7
    height.value = Math.round(Math.min(820, Math.max(500, viewport * ratio)))
  }
}

onMounted(async () => {
  measure()
  window.addEventListener('resize', measure)
  try {
    data.value = await mapApi.communities()
    center.value = data.value.center
    fit()
    status.value = 'ready'
  } catch {
    status.value = 'error'
    message.value = '地图数据加载失败；请确认已登录且后端 /api/maps/communities 可用。'
  }
  try {
    transit.value = await mapApi.stations()
  } catch {
    transit.value = null
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', measure)
})
</script>

<template>
  <div
    :class="
      expanded
        ? 'fixed inset-2 z-[70] flex flex-col overflow-hidden rounded-2xl border border-line bg-paper shadow-2xl'
        : 'overflow-hidden rounded-2xl border border-line bg-paper2'
    "
  >
    <div
      class="relative select-none overflow-hidden"
      :style="{ height: `${height}px`, background: '#eef3ee' }"
    >
      <div
        ref="container"
        class="absolute inset-0 cursor-grab active:cursor-grabbing"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @pointerleave="onPointerUp"
      >
        <img
          v-for="tile in tiles"
          :key="`v-${tile.key}`"
          :src="tile.url"
          class="pointer-events-none absolute h-64 w-64"
          :style="{ left: `${tile.left}px`, top: `${tile.top}px` }"
          alt=""
          draggable="false"
          @error="onTileError"
        />
        <img
          v-for="tile in labelTiles"
          :key="`l-${tile.key}`"
          :src="tile.url"
          class="pointer-events-none absolute h-64 w-64"
          :style="{ left: `${tile.left}px`, top: `${tile.top}px` }"
          alt=""
          draggable="false"
          @error="onTileError"
        />
        <div
          v-if="!tiles.length"
          class="pointer-events-none absolute inset-0"
          style="background-image: linear-gradient(rgba(31, 93, 74, 0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(31, 93, 74, 0.05) 1px, transparent 1px); background-size: 32px 32px"
        />

        <svg
          v-if="transitLines.length"
          class="pointer-events-none absolute inset-0 z-[5]"
          :width="width"
          :height="height"
        >
          <g v-for="line in transitLines" :key="line.id">
            <polyline
              :points="line.points.map((point) => `${point.x},${point.y}`).join(' ')"
              fill="none"
              :stroke="line.color"
              stroke-width="3"
              stroke-linejoin="round"
              opacity="0.55"
            />
            <circle
              v-for="station in line.points"
              :key="`${line.id}-${station.sid}-${station.x}`"
              :cx="station.x"
              :cy="station.y"
              r="2.6"
              :fill="line.color"
              stroke="#fff"
              stroke-width="0.8"
            >
              <title>{{ line.name }} · {{ station.name }}</title>
            </circle>
          </g>
        </svg>

        <button
          v-for="marker in markers"
          :key="marker.item.id"
          class="absolute z-10 -translate-x-1/2 -translate-y-1/2 whitespace-nowrap rounded-full border border-white/70 px-2 py-1 text-[10px] font-semibold shadow-sm transition hover:scale-105"
          :class="markerTone(marker.item)"
          :style="{ left: `${marker.left}px`, top: `${marker.top}px` }"
          :title="`${marker.item.name} · ${marker.item.listings} 套 · 通勤 ${marker.item.commute_p50 ?? '—'} 分钟`"
          @click="activeId = marker.item.id"
        >
          {{ markerLabel(marker.item) }}
        </button>
      </div>

      <div v-if="status === 'loading'" class="absolute inset-0 grid place-items-center bg-paper2/80 text-[12px] text-muted">
        正在加载真实小区坐标…
      </div>
      <div v-else-if="status === 'error'" class="absolute inset-0 grid place-items-center bg-paper2/90 px-6 text-center text-[11.5px] leading-5 text-coral">
        {{ message }}
      </div>

      <div class="absolute left-3 top-3 z-20 flex flex-wrap items-center gap-1.5">
        <select v-model.number="commuteFilter" class="rounded-lg border border-line bg-paper/95 px-2 py-1.5 text-[10.5px] text-ink shadow-sm">
          <option :value="0">全部通勤</option>
          <option :value="30">≤ 30 分钟</option>
          <option :value="45">≤ 45 分钟</option>
          <option :value="60">≤ 60 分钟</option>
        </select>
        <select v-model="colorMode" class="rounded-lg border border-line bg-paper/95 px-2 py-1.5 text-[10.5px] text-ink shadow-sm">
          <option value="rent">按租金</option>
          <option value="score">按评分</option>
        </select>
        <button
          class="rounded-lg border px-2 py-1.5 text-[10.5px] shadow-sm"
          :class="showTransit ? 'border-forest bg-forest-soft text-forest' : 'border-line bg-paper/95 text-muted'"
          @click="showTransit = !showTransit"
        >
          {{ showTransit ? '地铁线路开' : '地铁线路关' }}
        </button>
        <span class="rounded-full bg-paper/95 px-2 py-1 text-[10px] text-muted shadow-sm">
          {{ visible.length }} 个小区 · {{ visible.reduce((sum, item) => sum + item.listings, 0) }} 套 · 地铁 {{ transit?.station_count ?? 0 }} 站
        </span>
      </div>

      <div class="absolute bottom-3 right-3 z-20 flex flex-col overflow-hidden rounded-lg border border-line bg-paper/95 shadow-sm">
        <button class="grid h-8 w-8 place-items-center text-muted hover:bg-paper2" title="放大" @click="setZoom(zoom + 1)"><Plus :size="14" /></button>
        <button class="grid h-8 w-8 place-items-center border-y border-line text-muted hover:bg-paper2" title="缩小" @click="setZoom(zoom - 1)"><Minus :size="14" /></button>
        <button class="grid h-8 w-8 place-items-center text-muted hover:bg-paper2" title="重置视野" @click="fit"><SlidersHorizontal :size="13" /></button>
      </div>

      <div v-if="active" class="absolute bottom-3 left-3 z-20 w-[260px] rounded-xl border border-line bg-paper/95 p-3 shadow-md">
        <div class="flex items-start gap-2">
          <div class="min-w-0 flex-1">
            <div class="truncate text-[12px] font-bold">{{ active.name }}</div>
            <div class="text-[9.5px] text-faint">{{ active.district || '—' }} · {{ active.listings }} 套在库</div>
          </div>
          <button class="text-faint hover:text-ink" @click="activeId = null">×</button>
        </div>
        <div class="mt-2 grid grid-cols-3 gap-1 text-center">
          <div class="rounded-lg bg-paper2 px-1 py-1.5">
            <div class="text-[9px] text-faint">中位租金</div>
            <div class="mono text-[10.5px] font-semibold">{{ money(active.median_rent) }}</div>
          </div>
          <div class="rounded-lg bg-paper2 px-1 py-1.5">
            <div class="text-[9px] text-faint">评分</div>
            <div class="mono text-[10.5px] font-semibold">{{ active.avg_score ?? '—' }}</div>
          </div>
          <div class="rounded-lg bg-paper2 px-1 py-1.5">
            <div class="text-[9px] text-faint">通勤 p50</div>
            <div class="mono text-[10.5px] font-semibold">{{ active.commute_p50 ?? '—' }}min</div>
          </div>
        </div>
        <div class="mt-1.5 truncate text-[9.5px] text-muted">代表房源：{{ active.sample_listing.title || '—' }}</div>
        <button class="btn btn-sm mt-2 w-full" @click="store.openDetailById(active.sample_listing.id)">
          打开房源详情
        </button>
      </div>

      <div class="absolute right-3 top-3 z-20 flex items-center gap-1.5">
        <span class="rounded-full bg-paper/95 px-2 py-1 text-[9px] text-faint shadow-sm">
          {{ data?.tiles.attribution || '© 天地图' }}
          <span v-if="tileFailed" class="text-amber"> · 瓦片不可用，已回退坐标视图</span>
        </span>
        <button
          class="grid h-7 w-7 place-items-center rounded-lg border border-line bg-paper/95 text-muted shadow-sm hover:bg-paper2"
          :title="expanded ? '退出全屏' : '全屏查看地图'"
          @click="toggleExpand"
        >
          <Minimize2 v-if="expanded" :size="13" />
          <Maximize2 v-else :size="13" />
        </button>
      </div>
    </div>
    <div class="flex flex-wrap items-center gap-2 border-t border-line px-3 py-2 text-[9.5px] text-faint">
      <span>天地图 WMTS · 服务端缓存 {{ data?.tiles.cache_days ?? 30 }} 天 · 地铁线网 SZMC</span>
      <span>·</span>
      <span>坐标统一 WGS-84（由贝壳 GCJ-02 转换）</span>
      <span v-if="data && !data.tiles.enabled" class="text-amber">· 未配置 TIANDITU_API_KEY，当前为纯坐标视图</span>
      <span class="ml-auto">拖拽平移 · 滚轮请用 +/−</span>
    </div>
  </div>
</template>
