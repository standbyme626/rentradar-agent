<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Image, Loader2, RefreshCw, ScanSearch, ShieldAlert } from 'lucide-vue-next'
import type { ImagesData } from '@/api/types'
import { adminApi } from '@/api/services/admin'
import { useToast } from '@/composables/useToast'
import AdminKpi from './AdminKpi.vue'

const { toast } = useToast()
const data = ref<ImagesData | null>(null)
const loading = ref(true)
const loadError = ref('')
const running = ref(false)

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    data.value = await adminApi.images()
  } catch {
    loadError.value = '图片队列加载失败'
  } finally {
    loading.value = false
  }
}
onMounted(load)

const stats = computed(() => data.value?.stats)
const items = computed(() => data.value?.queue.items ?? [])
const duplicates = computed(() => data.value?.duplicates ?? [])

async function runAnalysis(limit = 30) {
  if (running.value) return
  running.value = true
  try {
    const job = await adminApi.analyzeImages([], limit)
    toast(`已入队 ${job.id}：分析最多 ${limit} 套未处理候选封面，worker 处理后刷新`)
  } catch {
    toast('入队失败，请稍后重试')
  } finally {
    running.value = false
  }
}

function verdictClass(verdict: string | undefined) {
  if (verdict === 'suspicious') return 'tag-coral'
  if (verdict === 'watch') return 'tag-amber'
  if (verdict === 'clear') return 'tag-green'
  return 'tag-neutral'
}

function verdictLabel(verdict: string | undefined) {
  if (verdict === 'suspicious') return '可疑'
  if (verdict === 'watch') return '观察'
  if (verdict === 'clear') return '未命中'
  return '未分析'
}

function coverSrc(item: { listing_id: number; image_url: string | null; image: { status: string } | null }) {
  if (item.image?.status === 'downloaded') return `/api/admin/images/${item.listing_id}/file`
  return item.image_url || ''
}

function confidence(value: number | null | undefined) {
  return value == null ? '—' : `${Math.round(value * 100)}%`
}
</script>

<template>
  <div>
    <h2 class="text-[20px] font-bold tracking-tight">图片 / AI</h2>
    <p class="mt-1 text-[12.5px] text-muted">只对候选房源下载列表封面，本地计算 dHash 与确定性信号；视觉大模型未授权，不伪造标签。</p>

    <div v-if="loading" class="mt-3 rounded-xl border border-line bg-paper2 px-3.5 py-2 text-[10.5px] text-muted">图片队列加载中…</div>
    <div v-else-if="loadError" class="mt-3 rounded-xl border border-coral/25 bg-coral-soft px-3.5 py-2 text-[10.5px] text-coral">
      {{ loadError }}
      <button class="ml-2 underline" @click="load">重试</button>
    </div>

    <div class="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
      <AdminKpi label="候选房源" :value="stats?.candidates ?? 0" sub="有封面 URL" />
      <AdminKpi label="已下载" :value="stats?.downloaded ?? 0" sub="本地缓存" tone="green" />
      <AdminKpi label="已分析" :value="stats?.analyzed ?? 0" :sub="`待处理 ${stats?.pending ?? 0}`" />
      <AdminKpi label="可疑 ≥2 信号" :value="stats?.suspicious ?? 0" sub="不单独定罪" tone="coral" />
      <AdminKpi label="观察" :value="stats?.watch ?? 0" sub="单信号" tone="amber" />
      <AdminKpi label="视觉标签" :value="stats?.vision_pending ?? 0" :sub="stats?.vision_enabled ? '已授权' : '未授权 · 待人工'" tone="amber" />
    </div>

    <div class="mt-3 flex flex-wrap items-center gap-2">
      <button class="btn btn-sm" :disabled="running" @click="runAnalysis(30)">
        <Loader2 v-if="running" :size="13" class="animate-spin" />
        <ScanSearch v-else :size="13" />
        {{ running ? '入队中…' : '分析候选封面（30 套）' }}
      </button>
      <button class="btn-ghost btn-sm" :disabled="running" @click="runAnalysis(200)">批量 200 套</button>
      <button class="btn-ghost btn-sm" :disabled="loading" @click="load">
        <RefreshCw :size="13" /> 刷新队列
      </button>
      <span class="text-[10.5px] text-faint">dHash 汉明距离 ≤ {{ stats?.duplicate_distance ?? 10 }} 视为重复封面；价格/话术信号同样落证据。</span>
    </div>

    <div class="mt-4 grid gap-4 xl:grid-cols-3">
      <section class="card p-4 xl:col-span-2">
        <h3 class="panel-title">候选队列 <span class="hint">{{ items.length }} 套 · 按评分排序</span></h3>
        <div class="mt-2 overflow-x-auto">
          <table class="w-full text-left text-[11.5px]">
            <thead class="border-b border-line bg-paper2 text-[9.5px] uppercase tracking-wide text-faint">
              <tr>
                <th class="px-2 py-2.5 font-semibold">封面</th>
                <th class="px-2 py-2.5 font-semibold">房源</th>
                <th class="px-2 py-2.5 font-semibold">租金</th>
                <th class="px-2 py-2.5 font-semibold">分数</th>
                <th class="px-2 py-2.5 font-semibold">判定</th>
                <th class="px-2 py-2.5 font-semibold">信号</th>
                <th class="px-2 py-2.5 font-semibold">置信度</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in items" :key="item.listing_id" class="border-b border-line align-top last:border-0">
                <td class="px-2 py-2.5">
                  <div class="h-12 w-16 overflow-hidden rounded-lg border border-line bg-paper2">
                    <img
                      v-if="coverSrc(item)"
                      :src="coverSrc(item)"
                      :alt="item.community_name || item.title || '封面'"
                      class="h-full w-full object-cover"
                      loading="lazy"
                    />
                    <div v-else class="grid h-full place-items-center text-[9px] text-faint">无图</div>
                  </div>
                </td>
                <td class="px-2 py-2.5">
                  <div class="max-w-[210px] truncate font-semibold">{{ item.title || '—' }}</div>
                  <div class="text-[9.5px] text-faint">{{ item.community_name || '—' }} · {{ item.district || '—' }}</div>
                </td>
                <td class="mono px-2 py-2.5">{{ item.rent == null ? '—' : `¥${item.rent}` }}</td>
                <td class="mono px-2 py-2.5">{{ item.score ?? '—' }}</td>
                <td class="px-2 py-2.5">
                  <span :class="verdictClass(item.analysis?.verdict)">{{ verdictLabel(item.analysis?.verdict) }}</span>
                  <div v-if="item.image?.status === 'failed'" class="mt-1 text-[9px] text-coral">下载失败</div>
                </td>
                <td class="px-2 py-2.5">
                  <div v-if="item.analysis?.signals?.length" class="flex max-w-[240px] flex-wrap gap-1">
                    <span
                      v-for="signal in item.analysis.signals"
                      :key="signal.code"
                      class="rounded border border-line bg-paper2 px-1.5 py-0.5 text-[9px] text-muted"
                      :title="JSON.stringify(signal.evidence)"
                    >
                      {{ signal.label }}
                    </span>
                  </div>
                  <span v-else class="text-[9.5px] text-faint">—</span>
                </td>
                <td class="mono px-2 py-2.5">{{ confidence(item.analysis?.confidence) }}</td>
              </tr>
              <tr v-if="!items.length">
                <td colspan="7" class="px-4 py-10 text-center text-[11px] text-faint">
                  队列为空。点“分析候选封面”入队，worker 会按评分顺序处理有封面 URL 的候选。
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="card p-4">
        <h3 class="panel-title flex items-center gap-2"><ShieldAlert :size="15" class="text-coral" />重复封面组</h3>
        <p class="mt-1 text-[10.5px] leading-5 text-muted">dHash 只能说明“图相同/近似”，假房源仍需价格、话术等 ≥2 个信号才标记。</p>
        <div v-if="duplicates.length" class="mt-2 space-y-2">
          <div v-for="(group, index) in duplicates.slice(0, 8)" :key="index" class="rounded-xl border border-line bg-paper2 px-3 py-2.5">
            <div class="flex items-center gap-2 text-[11px] font-semibold">
              <Image :size="13" class="text-muted" /> 组 {{ index + 1 }}
              <span class="tag-coral">{{ group.size }} 套</span>
            </div>
            <div class="mt-1 space-y-0.5 text-[10px] text-muted">
              <div v-for="listing in group.listings.slice(0, 4)" :key="listing.listing_id" class="truncate">
                #{{ listing.listing_id }} · {{ listing.title || '未命名' }}
              </div>
            </div>
          </div>
        </div>
        <div v-else class="mt-3 rounded-xl border border-dashed border-line px-3 py-8 text-center text-[11px] text-faint">
          暂无重复封面。分析后自动按汉明距离分组。
        </div>
      </section>
    </div>

    <section class="card mt-4 p-4">
      <h3 class="panel-title">管线与限制</h3>
      <div class="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div class="rounded-xl border border-line bg-paper2 px-3.5 py-3">
          <div class="text-[10px] text-muted">1 · 封面</div>
          <div class="mt-0.5 text-[12px] font-semibold">列表单图 + 本地缓存</div>
          <p class="mt-1 text-[9.5px] leading-4 text-faint">详情多图不可用；下载失败显式标 failed，不重试刷屏。</p>
        </div>
        <div class="rounded-xl border border-line bg-paper2 px-3.5 py-3">
          <div class="text-[10px] text-muted">2 · 指纹</div>
          <div class="mt-0.5 text-[12px] font-semibold">64-bit dHash</div>
          <p class="mt-1 text-[9.5px] leading-4 text-faint">同图/近重图可命中；不同装修风格无法区分。</p>
        </div>
        <div class="rounded-xl border border-line bg-paper2 px-3.5 py-3">
          <div class="text-[10px] text-muted">3 · 假房源信号</div>
          <div class="mt-0.5 text-[12px] font-semibold">重复图 / 低价 / 话术</div>
          <p class="mt-1 text-[9.5px] leading-4 text-faint">≥2 个非质量信号才可疑；每条证据可追溯。</p>
        </div>
        <div class="rounded-xl border border-line bg-paper2 px-3.5 py-3">
          <div class="text-[10px] text-muted">4 · 视觉标签</div>
          <div class="mt-0.5 text-[12px] font-semibold">未授权 · 不调用</div>
          <p class="mt-1 text-[9.5px] leading-4 text-faint">需要 Qwen-VL/本地 VL 的明确授权；此前只记录“待视觉”。</p>
        </div>
      </div>
    </section>
  </div>
</template>
