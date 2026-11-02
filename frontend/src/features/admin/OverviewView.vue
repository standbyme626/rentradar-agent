<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { CheckCircle2, Bot, Image, Route } from 'lucide-vue-next'
import AdminKpi from './AdminKpi.vue'
import { adminApi } from '@/api/services/admin'
import { mockOverview } from '@/api/mock/admin'
import { useLazyData } from '@/composables/useLazyData'
import { formatTime } from './adminData'

const { data: overview, loading, error, reload } = useLazyData(() => adminApi.overview(), mockOverview)
const stats = computed(() => overview.value.stats)
const runs = computed(() => overview.value.runs)
const funnel = computed(() => overview.value.funnel)
const quality = computed(() => overview.value.quality)
const nextSteps = computed(() => overview.value.nextSteps)
const noGeo = computed(() => stats.value.communities - stats.value.geocoded)
const geoCoverage = computed(() =>
  stats.value.communities
    ? Math.round((stats.value.geocoded / stats.value.communities) * 100)
    : 0,
)
const scoredCommute = computed(
  () => stats.value.scored_commute ?? stats.value.scored - stats.value.listings_no_commute,
)

const toneDot = (tone: string) =>
  tone === 'green' ? 'bg-forest' : tone === 'amber' ? 'bg-amber' : 'bg-coral'
const toneBadge = (tone: string) =>
  tone === 'green' ? 'tag-green' : tone === 'amber' ? 'tag-amber' : 'tag-coral'
</script>

<template>
  <div>
    <h2 class="text-[20px] font-bold tracking-tight">今天先做这三件事</h2>
    <p class="mt-1 text-[12.5px] text-muted">管理端不堆指标：先看阻塞、数据缺口和下一步成本。</p>
    <div v-if="loading" class="mt-3 rounded-xl border border-line bg-paper2 px-3.5 py-2 text-[10.5px] text-muted">数据加载中…</div>
    <div v-else-if="error" class="mt-3 rounded-xl border border-coral/25 bg-coral-soft px-3.5 py-2 text-[10.5px] text-coral">
      数据加载失败：{{ error }}
      <button class="ml-2 underline" @click="reload">重试</button>
    </div>

    <div class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <div class="action-card border-forest/30">
        <div class="grid h-8 w-8 place-items-center rounded-lg bg-forest-soft text-forest"><CheckCircle2 :size="16" /></div>
        <b>采集运行中 · 贝壳 App API</b>
        <p>任务 1 已切 API 通道，快扫/慢扫正常；CDP 仅作兜底。</p>
        <RouterLink to="/admin/providers" class="btn btn-sm">看数据源</RouterLink>
      </div>
      <div class="action-card border-amber/30">
        <div class="grid h-8 w-8 place-items-center rounded-lg bg-amber-soft text-amber"><Route :size="16" /></div>
        <b>{{ noGeo }} 个小区缺坐标</b>
        <p>导致 {{ stats.listings_no_geo }} 套房源没有通勤分，评分里通勤只能拿中性分。</p>
        <RouterLink to="/admin/quality" class="btn btn-sm">去补数据</RouterLink>
      </div>
      <div class="action-card">
        <div class="grid h-8 w-8 place-items-center rounded-lg bg-forest-soft text-forest"><Image :size="16" /></div>
        <b>图片 / AI 未接入</b>
        <p>当前只有列表封面 URL；没有详情图、pHash、视觉标签，也没有假房源信号。</p>
        <RouterLink to="/admin/images" class="btn btn-sm">看计划管线</RouterLink>
      </div>
      <div class="action-card">
        <div class="grid h-8 w-8 place-items-center rounded-lg bg-forest-soft text-forest"><Bot :size="16" /></div>
        <b>Agent 已接入 · LLM + 规则兜底</b>
        <p>会话、计划、条件与卡片已跑通；LLM 意图解析与回答已接；工具运行时和图片分析仍在后续。</p>
        <RouterLink to="/admin/agent" class="btn btn-sm">看真实会话</RouterLink>
      </div>
    </div>

    <div class="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
      <AdminKpi label="房源" :value="stats.listings" :sub="`5 号线 ${stats.line5} 套`" />
      <AdminKpi label="已评分" :value="stats.scored" :sub="`中位 ${stats.median_score} 分`" tone="green" />
      <AdminKpi label="≥75 分" :value="stats.ge75" :sub="`最高 ${stats.max_score}`" />
      <AdminKpi label="有坐标 / 小区" :value="`${stats.geocoded} / ${stats.communities}`" :sub="`覆盖 ${geoCoverage}%`" />
      <AdminKpi label="有通勤 / 已评分" :value="`${scoredCommute} / ${stats.scored}`" :sub="`缺口 ${stats.listings_no_commute} 套`" tone="amber" />
      <AdminKpi label="高德额度" value="API 管理" sub="调用与额度见数据源页" tone="amber" />
    </div>

    <div class="mt-4 grid gap-4 xl:grid-cols-2">
      <section class="card p-4">
        <h3 class="panel-title">候选漏斗 <span class="hint">从 {{ stats.line5 }} 套到 {{ scoredCommute }} 套有通勤</span></h3>
        <div class="mt-3 flex overflow-x-auto">
          <div
            v-for="(step, index) in funnel"
            :key="index"
            class="min-w-[108px] flex-1 border border-line bg-paper2 px-3 py-2.5"
            :class="[
              index === 0 ? 'rounded-l-xl' : '',
              index === funnel.length - 1 ? 'rounded-r-xl' : '',
              index > 0 ? 'border-l-0' : '',
            ]"
          >
            <div class="text-[18px] font-bold leading-6">{{ step.value }}</div>
            <div class="text-[9.5px] text-muted">{{ step.label }}</div>
            <div v-if="step.drop" class="mt-0.5 text-[9px] text-coral">{{ step.drop }}</div>
          </div>
        </div>
        <div class="mt-3 rounded-xl border border-forest/15 bg-forest-soft/60 px-3.5 py-2.5 text-[11px] leading-6 text-forest">
          通勤缺口主要来自“小区无坐标”：有坐标的已评分房源优先补通勤，比盲目扩采样更划算。
        </div>
      </section>

      <section class="card p-4">
        <h3 class="panel-title">数据质量 <span class="hint">当前最值得修的</span></h3>
        <div class="mt-2 divide-y divide-line text-[11.5px]">
          <div v-for="item in quality" :key="item.label" class="flex items-center gap-3 py-2.5">
            <span class="h-1.5 w-1.5 rounded-full" :class="toneDot(item.tone)" />
            <span class="w-20 font-semibold">{{ item.label }}</span>
            <span class="flex-1 text-muted">{{ item.desc }}</span>
            <span :class="toneBadge(item.tone)">{{ item.badge }}</span>
          </div>
        </div>
      </section>
    </div>

    <div class="mt-4 grid gap-4 xl:grid-cols-2">
      <section class="card p-4">
        <h3 class="panel-title">
          最近运行
          <RouterLink to="/admin/logs" class="hint hover:text-forest">全部日志</RouterLink>
        </h3>
        <div class="mt-2 overflow-x-auto">
          <table class="w-full text-left text-[12px]">
            <thead class="border-b border-line text-[10px] uppercase tracking-wide text-faint">
              <tr>
                <th class="py-2 pr-3 font-semibold">Run</th>
                <th class="py-2 pr-3 font-semibold">状态</th>
                <th class="py-2 pr-3 font-semibold">抓取 / 新增</th>
                <th class="py-2 pr-3 font-semibold">评分</th>
                <th class="py-2 font-semibold">时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="run in runs.slice(0, 6)" :key="run.id" class="border-b border-line last:border-0">
                <td class="mono py-2.5 pr-3">#{{ run.id }}</td>
                <td class="py-2.5 pr-3">
                  <span :class="run.status === 'done' ? 'tag-green' : 'tag-coral'">
                    {{ run.status === 'done' ? '完成' : '失败' }}
                  </span>
                </td>
                <td class="py-2.5 pr-3">
                  {{ run.stats.fetched ?? 0 }} / <b class="text-forest">{{ run.stats.new ?? 0 }}</b>
                </td>
                <td class="py-2.5 pr-3">{{ run.stats.scored ?? 0 }}</td>
                <td class="mono py-2.5 text-faint">{{ formatTime(run.started_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="card p-4">
        <h3 class="panel-title">下一步建议 <span class="hint">按成本排序</span></h3>
        <div class="mt-2 space-y-3">
          <div v-for="(item, index) in nextSteps" :key="item.title" class="flex gap-3">
            <span
              class="grid h-6 w-6 shrink-0 place-items-center rounded-full text-[10px] font-bold"
              :class="index === 0 ? 'bg-coral-soft text-coral' : 'bg-sand text-muted'"
            >
              {{ index + 1 }}
            </span>
            <div>
              <div class="text-[12px] font-semibold text-ink">{{ item.title }}</div>
              <div class="mt-0.5 text-[10.5px] leading-5 text-muted">{{ item.desc }}</div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.action-card {
  @apply flex flex-col rounded-2xl border border-line bg-paper p-4 shadow-card;
}
.action-card b {
  @apply mt-2 text-[13px] font-semibold text-ink;
}
.action-card p {
  @apply mt-1 flex-1 text-[11px] leading-5 text-muted;
}
.action-card a {
  @apply mt-3 self-start;
}
</style>
