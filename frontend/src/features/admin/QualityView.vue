<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Community } from '@/api/types'
import { adminApi } from '@/api/services/admin'
import { useLazyData } from '@/composables/useLazyData'
import { emptyQuality } from './adminData'
import AdminKpi from './AdminKpi.vue'
import { useToast } from '@/composables/useToast'

const { toast } = useToast()
const busyId = ref<number | null>(null)
const { data: qualityData, loading, error, reload } = useLazyData(
  () => adminApi.quality(),
  emptyQuality,
)
const stats = computed(() => qualityData.value.stats)
const geoPriority = computed(() => qualityData.value.geoPriority)
const poiCapped = computed(() => qualityData.value.poiCapped)
const noGeo = computed(() => stats.value.communities - stats.value.geocoded)

async function enqueueGeocode(item: Community) {
  if (busyId.value) return
  busyId.value = item.id
  try {
    const job = await adminApi.enqueueGeocode([item.id])
    toast(`已加入补数据队列 ${job.id}：${item.name}（约 ${job.calls} 次）`)
  } catch {
    toast('加入队列失败，请稍后重试')
  } finally {
    busyId.value = null
  }
}
</script>

<template>
  <div>
    <h2 class="text-[20px] font-bold tracking-tight">数据质量</h2>
    <p class="mt-1 text-[12.5px] text-muted">不是所有缺口都值得补。先补“房源多、影响评分大”的小区。</p>
    <div v-if="loading" class="mt-3 rounded-xl border border-line bg-paper2 px-3.5 py-2 text-[10.5px] text-muted">质量数据加载中…</div>
    <div v-else-if="error" class="mt-3 rounded-xl border border-coral/25 bg-coral-soft px-3.5 py-2 text-[10.5px] text-coral">
      {{ error }}
      <button class="ml-2 underline" @click="reload">重试</button>
    </div>

    <div class="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-3">
      <AdminKpi label="缺坐标小区" :value="noGeo" :sub="`影响 ${stats.listings_no_geo} 套房源通勤`" tone="coral" />
      <AdminKpi label="POI 封顶小区" :value="stats.poi_capped" sub="餐饮 count ≥ 600" tone="amber" />
      <AdminKpi label="详情图覆盖" value="不可用" sub="列表只有封面；分析见图片页" tone="amber" />
    </div>

    <div class="mt-4 grid gap-4 xl:grid-cols-2">
      <section class="card p-4">
        <h3 class="panel-title">优先补坐标 <span class="hint">按房源数排序</span></h3>
        <div class="mt-2 overflow-x-auto">
          <table class="w-full text-left text-[12px]">
            <thead class="border-b border-line bg-paper2 text-[10px] uppercase tracking-wide text-faint">
              <tr>
                <th class="px-3 py-2.5 font-semibold">小区</th>
                <th class="px-3 py-2.5 font-semibold">房源</th>
                <th class="px-3 py-2.5 font-semibold">区域</th>
                <th class="px-3 py-2.5 font-semibold">建议动作</th>
                <th class="px-3 py-2.5 font-semibold">预计调用</th>
                <th class="px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in geoPriority" :key="item.id" class="border-b border-line last:border-0">
                <td class="px-3 py-2.5">
                  <div class="font-semibold">{{ item.name }}</div>
                  <div class="text-[10px] text-faint">{{ item.district || '无区域' }}</div>
                </td>
                <td class="px-3 py-2.5">{{ item.listings }}</td>
                <td class="px-3 py-2.5 text-muted">{{ item.district || '—' }}</td>
                <td class="px-3 py-2.5"><span class="tag-amber">补坐标 + POI</span></td>
                <td class="mono px-3 py-2.5">约 5–6 次</td>
                <td class="px-3 py-2.5">
                  <button class="btn-ghost btn-sm" :disabled="busyId === item.id" @click="enqueueGeocode(item)">
                    {{ busyId === item.id ? '加入中…' : '加入' }}
                  </button>
                </td>
              </tr>
              <tr v-if="!geoPriority.length">
                <td colspan="6" class="px-4 py-8 text-center text-faint">暂无缺坐标小区</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="mt-3 text-[10.5px] leading-5 text-faint">
          补 1 个小区 ≈ 1–2 次地理编码 + 3 次 POI + 1 次通勤 ≈ 5–6 次。补前 5 个约 25–30 次。
        </p>
      </section>

      <section class="card p-4">
        <h3 class="panel-title">POI 封顶 <span class="hint">POI 返回上限</span></h3>
        <div class="mt-2 rounded-xl border border-amber/25 bg-amber-soft px-3.5 py-2.5 text-[10.5px] leading-5 text-amber">
          {{ stats.poi_capped }} 个小区的餐饮 count 达到 600 上限，当前便利分只能区分“密集 / 不密集”，无法区分 600 与 1200。后续改按品类细分统计或换网格口径。
        </div>
        <div class="mt-3 overflow-x-auto">
          <table class="w-full text-left text-[12px]">
            <thead class="border-b border-line bg-paper2 text-[10px] uppercase tracking-wide text-faint">
              <tr>
                <th class="px-3 py-2.5 font-semibold">小区</th>
                <th class="px-3 py-2.5 font-semibold">餐饮</th>
                <th class="px-3 py-2.5 font-semibold">日常</th>
                <th class="px-3 py-2.5 font-semibold">夜宵</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in poiCapped" :key="item.id" class="border-b border-line last:border-0">
                <td class="px-3 py-2.5 font-semibold">{{ item.name }}</td>
                <td class="mono px-3 py-2.5">{{ item.dining_count }}</td>
                <td class="mono px-3 py-2.5">{{ item.daily_count ?? '—' }}</td>
                <td class="mono px-3 py-2.5">{{ item.nightlife_count ?? '—' }}</td>
              </tr>
              <tr v-if="!poiCapped.length">
                <td colspan="4" class="px-4 py-8 text-center text-faint">暂无封顶小区</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </div>
</template>
