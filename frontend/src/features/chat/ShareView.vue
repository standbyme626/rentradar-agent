<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { fetchPublicDashboard } from '@/api/services/public'
import type { PublicDashboard } from '@/api/types'

const route = useRoute()
const loading = ref(true)
const error = ref('')
const data = ref<PublicDashboard | null>(null)

const token = computed(() => String(route.params.token ?? ''))
const generated = computed(() =>
  data.value
    ? new Date(data.value.generated_at).toLocaleString('zh-CN', {
        hour12: false,
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
    : '—',
)
const bandRows = computed(() => {
  if (!data.value) return []
  const total = Object.values(data.value.price_bands).reduce((sum, value) => sum + value, 0)
  return Object.entries(data.value.price_bands).map(([label, value]) => ({
    label,
    value,
    pct: total ? Math.round((value / total) * 100) : 0,
  }))
})

let meta: HTMLMetaElement | null = null
onMounted(async () => {
  meta = document.createElement('meta')
  meta.name = 'robots'
  meta.content = 'noindex, nofollow, noarchive'
  document.head.appendChild(meta)
  try {
    data.value = await fetchPublicDashboard(token.value)
  } catch (exc) {
    error.value = String(exc).includes('429')
      ? '访问太频繁，请稍后再试。'
      : '链接无效、已撤销或已过期。'
  } finally {
    loading.value = false
  }
})
onBeforeUnmount(() => {
  meta?.remove()
})
</script>

<template>
  <div class="min-h-screen bg-canvas px-4 py-8 text-ink">
    <div class="mx-auto max-w-5xl">
      <header class="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div class="text-[10px] font-semibold uppercase tracking-[0.16em] text-faint">RentRadar · read-only</div>
          <h1 class="mt-1 text-[24px] font-bold tracking-tight">深圳租房只读看板</h1>
          <p class="mt-1 text-[12px] text-muted">仅聚合数据；不含房源标题、图片、地址或联系方式。链接可随时撤销。</p>
        </div>
        <div class="rounded-xl border border-line bg-paper px-3.5 py-2 text-right text-[10.5px] text-muted">
          <div>生成时间</div>
          <div class="font-semibold text-ink">{{ generated }}</div>
        </div>
      </header>

      <div v-if="loading" class="mt-8 card p-6 text-[12px] text-muted">加载中…</div>
      <div v-else-if="error" class="mt-8 card p-6">
        <div class="text-[14px] font-semibold text-coral">{{ error }}</div>
        <p class="mt-2 text-[11px] text-muted">此页面不提供登录入口，请向分享者获取新链接。</p>
      </div>
      <template v-else-if="data">
        <div class="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div class="card p-4">
            <div class="text-[10px] text-faint">在库活跃房源</div>
            <div class="mt-1 text-[26px] font-bold">{{ data.totals.active_listings.toLocaleString('zh-CN') }}</div>
            <div class="text-[10px] text-muted">已评分 {{ data.totals.scored_listings }} · {{ Math.round(data.totals.scored_ratio * 100) }}%</div>
          </div>
          <div class="card p-4">
            <div class="text-[10px] text-faint">覆盖小区</div>
            <div class="mt-1 text-[26px] font-bold">{{ data.totals.communities }}</div>
            <div class="text-[10px] text-muted">{{ data.totals.districts }} 个行政区</div>
          </div>
          <div class="card p-4">
            <div class="text-[10px] text-faint">5 号线分片</div>
            <div class="mt-1 text-[26px] font-bold">{{ data.line5.complete }}<span class="text-[12px] font-normal"> / {{ data.line5.shards }}</span></div>
            <div class="text-[10px] text-muted">库内 {{ data.line5.listings }} 套 · 已扫描 {{ data.line5.scanned }}</div>
          </div>
          <div class="card p-4">
            <div class="text-[10px] text-faint">数据来源</div>
            <div class="mt-1 text-[14px] font-semibold">{{ data.source.name }}</div>
            <a class="text-[10px] text-forest underline" :href="data.source.url" target="_blank" rel="noopener noreferrer">回源查看</a>
          </div>
        </div>

        <div class="mt-4 grid gap-4 xl:grid-cols-2">
          <section class="card p-4">
            <h2 class="panel-title">区域分布 <span class="hint">中位租金 / 平均分</span></h2>
            <div class="mt-3 overflow-x-auto">
              <table class="w-full text-left text-[11.5px]">
                <thead class="border-b border-line text-[9.5px] uppercase tracking-wide text-faint">
                  <tr><th class="px-2 py-2">区域</th><th class="px-2 py-2">房源</th><th class="px-2 py-2">中位租金</th><th class="px-2 py-2">平均分</th></tr>
                </thead>
                <tbody>
                  <tr v-for="item in data.districts" :key="item.name" class="border-b border-line last:border-0">
                    <td class="px-2 py-2 font-semibold">{{ item.name }}</td>
                    <td class="px-2 py-2">{{ item.listings }}</td>
                    <td class="px-2 py-2">¥{{ item.median_rent?.toLocaleString('zh-CN') ?? '—' }}</td>
                    <td class="px-2 py-2">{{ item.avg_score ?? '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section class="card p-4">
            <h2 class="panel-title">价格带 <span class="hint">按在库租金</span></h2>
            <div class="mt-4 space-y-3">
              <div v-for="row in bandRows" :key="row.label">
                <div class="flex justify-between text-[10.5px] text-muted"><span>{{ row.label }}</span><span>{{ row.value }} 套 · {{ row.pct }}%</span></div>
                <div class="mt-1 h-2 overflow-hidden rounded-full bg-sand">
                  <div class="h-full rounded-full bg-forest" :style="{ width: `${row.pct}%` }" />
                </div>
              </div>
            </div>
          </section>
        </div>

        <div class="mt-4 rounded-xl border border-line bg-paper2 px-3.5 py-3 text-[10.5px] leading-5 text-muted">
          {{ data.data_note }} 页面响应带 <code class="mono">X-Robots-Tag: noindex</code>，且按来源 IP 限流。
        </div>
      </template>
    </div>
  </div>
</template>
