<script setup lang="ts">
import { computed, ref } from 'vue'
import { adminApi } from '@/api/services/admin'
import { mockCoverage } from '@/api/mock/admin'
import { useLazyData } from '@/composables/useLazyData'
import AdminKpi from './AdminKpi.vue'
import { useToast } from '@/composables/useToast'

const { toast } = useToast()
const { data: coverage, loading, error, reload } = useLazyData(
  () => adminApi.coverage(),
  mockCoverage,
)
const stats = computed(() => coverage.value.stats)
const communities = computed(() => coverage.value.communities)
const priority = computed(() => coverage.value.priority)
const busy = ref(false)
const geoBusy = ref(false)
const count = ref(10)
const buckets = ref(['07:30', '08:00', '08:30', '09:00'])
const modes = ref(['公交/地铁'])

const bucketOptions = ['07:30', '08:00', '08:30', '09:00']
const modeOptions = ['公交/地铁', '驾车', '步行接驳', '骑行接驳']

const calls = computed(() => (Number(count.value) || 0) * buckets.value.length * modes.value.length)
const unsupportedModes = computed(() => modes.value.filter((item) => item !== '公交/地铁'))
const over = computed(() => !buckets.value.length || !modes.value.includes('公交/地铁'))
const multiBucket = computed(() => stats.value.commute_multi_bucket ?? 0)

const noGeo = computed(() => stats.value.communities - stats.value.geocoded)

function toggleBucket(value: string) {
  buckets.value = buckets.value.includes(value)
    ? buckets.value.filter((item) => item !== value)
    : [...buckets.value, value]
}

function toggleMode(value: string) {
  modes.value = modes.value.includes(value)
    ? modes.value.filter((item) => item !== value)
    : [...modes.value, value]
}

async function startSampling() {
  if (over.value || !calls.value || busy.value) return
  busy.value = true
  try {
    const job = await adminApi.startSampling({
      origin: '深圳会展中心',
      count: Number(count.value) || 0,
      buckets: [...buckets.value],
      modes: [...modes.value],
    })
    toast(`已加入采样队列 ${job.id}：${job.calls} 次`)
  } catch {
    toast('采样任务提交失败，请稍后重试')
  } finally {
    busy.value = false
  }
}

async function generateGeocodePlan() {
  if (!priority.value.length || geoBusy.value) return
  geoBusy.value = true
  try {
    const job = await adminApi.enqueueGeocode(priority.value.map((item) => item.id))
    toast(`已生成补坐标任务 ${job.id}：${priority.value.length} 个小区 · 约 ${job.calls} 次`)
  } catch {
    toast('补坐标任务提交失败，请稍后重试')
  } finally {
    geoBusy.value = false
  }
}
</script>

<template>
  <div>
    <h2 class="text-[20px] font-bold tracking-tight">通勤与预算</h2>
    <p class="mt-1 text-[12.5px] text-muted">通勤走深圳地铁官方（零额度）；4 个时段用于记录采样口径，SZMC 为时刻表最短耗时，同 OD 不同时段结果相同。</p>
    <div v-if="loading" class="mt-3 rounded-xl border border-line bg-paper2 px-3.5 py-2 text-[10.5px] text-muted">覆盖数据加载中…</div>
    <div v-else-if="error" class="mt-3 rounded-xl border border-coral/25 bg-coral-soft px-3.5 py-2 text-[10.5px] text-coral">
      {{ error }}
      <button class="ml-2 underline" @click="reload">重试</button>
    </div>

    <div class="mt-4 grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
      <section class="card p-4">
        <h3 class="panel-title">采样预算器 <span class="hint">SZMC 零额度</span></h3>
        <div class="mt-3 space-y-3">
          <div>
            <label class="label">方向</label>
            <input class="input" value="小区 → 公司（目的地址在设置里配置）" readonly />
          </div>
          <div>
            <label class="label">候选小区数</label>
            <input v-model.number="count" type="number" min="1" max="200" class="input" />
          </div>
          <div>
            <label class="label">时段</label>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="option in bucketOptions"
                :key="option"
                class="rounded-full border px-3 py-1.5 text-[11px] transition"
                :class="
                  buckets.includes(option)
                    ? 'border-forest bg-forest-soft font-semibold text-forest'
                    : 'border-line2 bg-paper text-muted'
                "
                @click="toggleBucket(option)"
              >
                {{ option }}
              </button>
            </div>
          </div>
          <div>
            <label class="label">方式</label>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="option in modeOptions"
                :key="option"
                class="rounded-full border px-3 py-1.5 text-[11px] transition"
                :class="
                  modes.includes(option)
                    ? 'border-forest bg-forest-soft font-semibold text-forest'
                    : 'border-line2 bg-paper text-muted'
                "
                @click="toggleMode(option)"
              >
                {{ option }}
              </button>
            </div>
          </div>
        </div>

        <div class="mt-3 rounded-xl border border-line bg-paper2 px-3.5 py-3">
          <div class="flex items-end justify-between">
            <span class="text-[11.5px] text-muted">预计调用</span>
            <span class="text-[26px] font-bold leading-7" :class="over ? 'text-coral' : 'text-forest'">{{ calls }}</span>
          </div>
          <div class="mt-1 flex justify-between text-[11px] text-muted">
            <span>SZMC 额度消耗</span><b class="text-ink">0</b>
          </div>
          <div class="mt-0.5 flex justify-between text-[11px] text-muted">
            <span>缓存命中（7 天/时段）</span><b class="text-ink">按分片跳过</b>
          </div>
        </div>

        <div
          class="mt-3 rounded-xl border px-3.5 py-2.5 text-[10.5px] leading-5"
          :class="over ? 'border-coral/30 bg-coral-soft text-coral' : 'border-amber/25 bg-amber-soft text-amber'"
        >
          <template v-if="over">至少选择一个时段和「公交/地铁」；其他方式暂未接入。</template>
          <template v-else>
            按 {{ count }} 个小区 × {{ buckets.length }} 时段 = {{ calls }} 次地铁查询（零额度）。SZMC 无出发时间参数，结果不会随时段变化。
          </template>
        </div>
        <p v-if="unsupportedModes.length" class="mt-1 text-[10px] text-coral">
          未接入的方式已忽略：{{ unsupportedModes.join(' / ') }}。
        </p>

        <div class="mt-3 flex flex-wrap gap-2">
          <button class="btn-primary" :disabled="over || !calls || busy" @click="startSampling">
            {{ busy ? '提交中…' : '开始采样' }}
          </button>
          <button class="btn" :disabled="geoBusy || !priority.length" @click="generateGeocodePlan">
            {{ geoBusy ? '生成中…' : '先生成补坐标计划' }}
          </button>
        </div>
      </section>

      <section class="card p-4">
        <h3 class="panel-title">当前覆盖 <span class="hint">{{ stats.communities }} 个小区</span></h3>
        <div class="mt-3 space-y-3">
          <div>
            <div class="flex justify-between text-[11px] text-muted"><span>有坐标</span><b class="text-ink">{{ stats.geocoded }} / {{ stats.communities }}</b></div>
            <div class="mt-1 h-1.5 overflow-hidden rounded-full bg-sand"><div class="h-full rounded-full bg-forest" :style="{ width: `${(stats.geocoded / stats.communities) * 100}%` }" /></div>
          </div>
          <div>
            <div class="flex justify-between text-[11px] text-muted"><span>有通勤样本</span><b class="text-ink">{{ stats.commute_communities }} / {{ stats.communities }}</b></div>
            <div class="mt-1 h-1.5 overflow-hidden rounded-full bg-sand"><div class="h-full rounded-full bg-forest" :style="{ width: `${(stats.commute_communities / stats.communities) * 100}%` }" /></div>
          </div>
          <div>
            <div class="flex justify-between text-[11px] text-muted">
              <span>p50 / p90 多时段（≥3 时段）</span>
              <b class="text-ink">{{ multiBucket }} / {{ stats.communities }}</b>
            </div>
            <div class="mt-1 h-1.5 overflow-hidden rounded-full bg-sand">
              <div class="h-full rounded-full bg-forest" :style="{ width: `${(multiBucket / Math.max(1, stats.communities)) * 100}%` }" />
            </div>
          </div>
          <div>
            <div class="flex justify-between text-[11px] text-muted"><span>POI 封顶（餐饮 600）</span><b class="text-ink">{{ stats.poi_capped }} 个小区</b></div>
            <div class="mt-1 h-1.5 overflow-hidden rounded-full bg-sand"><div class="h-full rounded-full bg-amber" :style="{ width: `${(stats.poi_capped / stats.communities) * 100}%` }" /></div>
          </div>
        </div>

        <div class="mt-3 rounded-xl border border-forest/15 bg-forest-soft/60 px-3.5 py-2.5 text-[10.5px] leading-5 text-forest">
          当前 {{ stats.commute_samples }} 条通勤样本，共 {{ stats.commute_p50_communities ?? stats.commute_communities }} 个小区有 p50；SZMC 为时刻表估算，p90 仅反映样本分布，不代表实时拥堵。
        </div>

        <h3 class="panel-title mt-4">优先补的小区 <span class="hint">按房源数</span></h3>
        <div class="mt-1 divide-y divide-line">
          <div v-for="(item, index) in priority" :key="item.id" class="flex items-center gap-2.5 py-2 text-[11px]">
            <span class="mono w-4 text-faint">{{ index + 1 }}</span>
            <span class="flex-1"><b class="text-ink">{{ item.name }}</b> · {{ item.listings }} 套</span>
            <span class="tag-amber">约 5 次</span>
          </div>
        </div>
      </section>
    </div>

    <div class="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
      <AdminKpi label="小区" :value="stats.communities" sub="5 号线任务下" />
      <AdminKpi label="有坐标" :value="stats.geocoded" sub="地理编码永久缓存" tone="green" />
      <AdminKpi label="有通勤样本" :value="stats.commute_communities" sub="p50 / p90 已接入" tone="amber" />
      <AdminKpi label="无坐标" :value="noGeo" sub="不参与通勤评分" tone="coral" />
    </div>

    <section class="card mt-4 p-4">
      <h3 class="panel-title">小区通勤覆盖 <span class="hint">前 20 个小区</span></h3>
      <div class="mt-2 overflow-x-auto">
        <table class="w-full text-left text-[12px]">
          <thead class="border-b border-line bg-paper2 text-[10px] uppercase tracking-wide text-faint">
            <tr>
              <th class="px-3 py-2.5 font-semibold">小区</th>
              <th class="px-3 py-2.5 font-semibold">区域</th>
              <th class="px-3 py-2.5 font-semibold">房源</th>
              <th class="px-3 py-2.5 font-semibold">坐标</th>
              <th class="px-3 py-2.5 font-semibold">通勤 p50 / p90</th>
              <th class="px-3 py-2.5 font-semibold">时段 / 样本</th>
              <th class="px-3 py-2.5 font-semibold">POI 餐饮/日常/夜宵</th>
              <th class="px-3 py-2.5 font-semibold">状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in communities" :key="item.id" class="border-b border-line last:border-0">
              <td class="px-3 py-2.5 font-semibold">{{ item.name }}</td>
              <td class="px-3 py-2.5 text-muted">{{ item.district || '—' }}</td>
              <td class="px-3 py-2.5">{{ item.listings }}</td>
              <td class="px-3 py-2.5"><span :class="item.lng != null ? 'tag-green' : 'tag-coral'">{{ item.lng != null ? '有' : '无' }}</span></td>
              <td class="px-3 py-2.5">
                <template v-if="item.commute_p50 != null">
                  {{ item.commute_p50 }} / {{ item.commute_p90 ?? '—' }} 分钟
                  <span v-if="item.commute_static" class="ml-1 text-[9px] text-faint">时刻表</span>
                </template>
                <template v-else>{{ item.commute_min != null ? `${item.commute_min} 分钟` : '—' }}</template>
              </td>
              <td class="px-3 py-2.5">{{ item.commute_buckets ?? 0 }} / {{ item.samples }}</td>
              <td class="mono px-3 py-2.5 text-muted">{{ item.dining_count ?? '—' }} / {{ item.daily_count ?? '—' }} / {{ item.nightlife_count ?? '—' }}</td>
              <td class="px-3 py-2.5">
                <span v-if="item.lng != null && item.samples" class="tag-green">已富化</span>
                <span v-else-if="item.lng != null" class="tag-amber">缺通勤</span>
                <span v-else class="tag-neutral">缺坐标</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="mt-3 text-[10.5px] leading-5 text-faint">
        每次通勤 = 1 次深圳地铁官方查询（零额度）；地理编码/POI 仍按缓存和额度控制。只对 Top 候选跑，不做全量。SZMC 只覆盖 3km 内有地铁站的小区，无站时明确「无地铁样本」。
      </p>
    </section>
  </div>
</template>
