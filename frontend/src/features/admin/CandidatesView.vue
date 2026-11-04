<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { CheckSquare, Square } from 'lucide-vue-next'
import type { Candidate } from '@/api/types'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { useToast } from '@/composables/useToast'
import { adminApi } from '@/api/services/admin'
import { useLazyData } from '@/composables/useLazyData'
import { money } from './adminData'

const { toast } = useToast()
const busy = ref(false)
const { data: items, loading, error, reload } = useLazyData(
  () => adminApi.candidates(),
  [],
)
const q = ref('')
const status = ref('all')
const district = ref('')
const selected = ref<Set<number>>(new Set())
const active = ref<Candidate | null>(null)

const districts = computed(() => [
  ...new Set(items.value.map((item) => item.district).filter((value): value is string => Boolean(value))),
])

const filtered = computed(() =>
  items.value.filter((item) => {
    if (q.value && !`${item.title}${item.community_name}`.includes(q.value)) return false
    if (district.value && item.district !== district.value) return false
    if (status.value === 'commute' && !item.has_commute) return false
    if (status.value === 'nocommute' && item.has_commute) return false
    if (status.value === 'high' && (item.score ?? 0) < 75) return false
    return true
  }),
)

const allChecked = computed(
  () => filtered.value.length > 0 && filtered.value.every((item) => selected.value.has(item.id)),
)
const missingCommute = computed(
  () => [...selected.value].filter((id) => !items.value.find((item) => item.id === id)?.has_commute).length,
)
const estCalls = computed(() => selected.value.size + missingCommute.value)

function toggle(id: number, checked: boolean) {
  const next = new Set(selected.value)
  if (checked) next.add(id)
  else next.delete(id)
  selected.value = next
}

function onCheck(id: number, event: Event) {
  toggle(id, (event.target as HTMLInputElement).checked)
}

function toggleAll(event: Event) {
  const checked = (event.target as HTMLInputElement).checked
  const next = new Set(selected.value)
  filtered.value.forEach((item) => {
    if (checked) next.add(item.id)
    else next.delete(item.id)
  })
  selected.value = next
}

async function runSelected() {
  if (!selected.value.size) return
  busy.value = true
  try {
    const job = await adminApi.enqueueAnalysis([...selected.value])
    toast(`已提交任务 ${job.id}：${job.calls} 套候选 · 本地重评分（外部调用后续接入）`)
  } catch {
    toast('提交失败，请稍后重试')
  } finally {
    busy.value = false
  }
}

function exportCandidates() {
  const rows = filtered.value
  if (!rows.length) return
  const header = ['id', 'community', 'district', 'layout', 'area', 'rent', 'score', 'commute_min', 'has_geo', 'has_commute', 'url']
  const data = rows.map((item) =>
    [
      item.id,
      `"${(item.community_name || '').replace(/"/g, '""')}"`,
      item.district || '',
      item.layout || '',
      item.area ?? '',
      item.rent ?? '',
      item.score ?? '',
      item.commute_min ?? '',
      item.has_geo,
      item.has_commute,
      `"${item.url || ''}"`,
    ].join(','),
  )
  const blob = new Blob([`\ufeff${[header.join(','), ...data].join('\n')}`], {
    type: 'text/csv;charset=utf-8;',
  })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = 'rentradar-candidates.csv'
  link.click()
  URL.revokeObjectURL(link.href)
  toast(`已导出 ${rows.length} 条候选`)
}
</script>

<template>
  <div>
    <h2 class="text-[20px] font-bold tracking-tight">候选工作台</h2>
    <p class="mt-1 text-[12.5px] text-muted">
      先选人，再花钱：勾选候选后先做本地重评分；通勤、详情和 AI 按预算逐步接入。
    </p>

    <div class="mt-4 flex flex-wrap items-center gap-2">
      <input v-model="q" type="search" class="input w-[200px]" placeholder="搜索小区 / 标题" />
      <select v-model="status" class="input w-[130px]">
        <option value="all">全部候选</option>
        <option value="commute">已有通勤</option>
        <option value="nocommute">缺通勤</option>
        <option value="high">≥75 分</option>
      </select>
      <select v-model="district" class="input w-[130px]">
        <option value="">全部区域</option>
        <option v-for="item in districts" :key="item" :value="item">{{ item }}</option>
      </select>
      <span class="ml-auto text-[11px] text-faint">{{ filtered.length }} 条候选</span>
      <button class="btn btn-sm" @click="exportCandidates">导出 CSV</button>
    </div>

    <div class="mt-3 overflow-x-auto rounded-2xl border border-line bg-paper shadow-card">
      <table class="w-full text-left text-[12px]">
        <thead class="border-b border-line bg-paper2 text-[10px] uppercase tracking-wide text-faint">
          <tr>
            <th class="w-10 px-3 py-2.5">
              <input
                type="checkbox"
                class="accent-forest"
                :checked="allChecked"
                @change="toggleAll"
              />
            </th>
            <th class="px-3 py-2.5 font-semibold">房源</th>
            <th class="px-3 py-2.5 font-semibold">区域</th>
            <th class="px-3 py-2.5 font-semibold">月租</th>
            <th class="px-3 py-2.5 font-semibold">评分</th>
            <th class="px-3 py-2.5 font-semibold">通勤</th>
            <th class="px-3 py-2.5 font-semibold">数据完整度</th>
            <th class="px-3 py-2.5 font-semibold">状态</th>
            <th class="px-3 py-2.5" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in filtered"
            :key="item.id"
            class="border-b border-line transition last:border-0 hover:bg-paper2"
          >
            <td class="px-3 py-2.5">
              <input
                type="checkbox"
                class="accent-forest"
                :checked="selected.has(item.id)"
                @change="onCheck(item.id, $event)"
              />
            </td>
            <td class="px-3 py-2.5">
              <div class="font-semibold text-ink">{{ item.community_name || '—' }}</div>
              <div class="mono mt-0.5 text-[10px] text-faint">{{ (item.title || '').slice(0, 28) }}</div>
            </td>
            <td class="px-3 py-2.5 text-muted">{{ item.district || '—' }}</td>
            <td class="px-3 py-2.5 font-semibold">{{ money(item.rent) }}</td>
            <td class="px-3 py-2.5">
              <span :class="(item.score ?? 0) >= 85 ? 'tag-green' : (item.score ?? 0) >= 75 ? 'tag-neutral' : 'tag-amber'">
                {{ item.score ?? '—' }}
              </span>
            </td>
            <td class="px-3 py-2.5">
              <template v-if="item.has_commute">
                {{ item.commute_min }} 分钟
                <div class="text-[10px] text-faint">{{ item.samples }} 次样本</div>
              </template>
              <span v-else class="tag-coral">缺通勤</span>
            </td>
            <td class="px-3 py-2.5">
              <div class="flex flex-wrap gap-1">
                <span :class="item.has_geo ? 'tag-green' : 'tag-coral'">坐标</span>
                <span :class="item.dining_count != null ? 'tag-green' : 'tag-coral'">POI</span>
                <span class="tag-coral">图片</span>
                <span class="tag-coral">AI</span>
              </div>
            </td>
            <td class="px-3 py-2.5">
              <span :class="item.status === 'active' ? 'tag-green' : 'tag-amber'">
                {{ item.status === 'active' ? '在架' : '待核实' }}
              </span>
            </td>
            <td class="px-3 py-2.5">
              <button class="btn-ghost btn-sm" @click="active = item">详情</button>
            </td>
          </tr>
          <tr v-if="loading">
            <td colspan="9" class="px-4 py-10 text-center text-[12px] text-faint">候选加载中…</td>
          </tr>
          <tr v-else-if="error">
            <td colspan="9" class="px-4 py-10 text-center text-[12px] text-coral">
              {{ error }}
              <button class="ml-2 underline" @click="reload">重试</button>
            </td>
          </tr>
          <tr v-else-if="!filtered.length">
            <td colspan="9" class="px-4 py-10 text-center text-[12px] text-faint">没有匹配候选</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="sticky bottom-3 z-20 mt-3 flex flex-wrap items-center gap-3 rounded-2xl bg-sidebar px-4 py-2.5 text-[#edf5ef] shadow-lift">
      <template v-if="selected.size">
        <CheckSquare :size="15" class="text-[#a9bdb1]" />
        <span class="text-[13px] font-semibold">已选 {{ selected.size }} 套</span>
        <span class="text-[10.5px] text-[#a9bdb1]">
          预计 {{ estCalls }}–{{ selected.size * 3 }} 次调用 · 高德 {{ missingCommute }} 次 · 详情 {{ selected.size }} 套 · AI {{ selected.size }} 次
        </span>
      </template>
      <template v-else>
        <Square :size="15" class="text-[#7f9489]" />
        <span class="text-[12px] text-[#a9bdb1]">未选择候选 · 勾选后显示预计调用次数</span>
      </template>
      <div class="ml-auto flex gap-2">
        <RouterLink to="/admin/commute" class="rounded-lg bg-[#edf5ef]/10 px-3 py-1.5 text-[11px] text-[#edf5ef]">去预算器</RouterLink>
        <button
          class="rounded-lg bg-forest px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-40"
          :disabled="!selected.size || busy"
          @click="runSelected"
        >
          {{ busy ? '提交中…' : '运行选中' }}
        </button>
      </div>
    </div>

    <AppDrawer
      :open="!!active"
      :title="active?.community_name ?? '候选详情'"
      :subtitle="active ? `${active.district || ''} · ${active.layout || ''} · ${active.area ?? '—'}㎡ · ${money(active.rent)}/月` : ''"
      @close="active = null"
    >
      <template v-if="active">
        <div class="flex flex-wrap gap-1.5">
          <span :class="active.has_geo ? 'tag-green' : 'tag-coral'">坐标</span>
          <span :class="active.dining_count != null ? 'tag-green' : 'tag-coral'">POI</span>
          <span :class="active.has_commute ? 'tag-green' : 'tag-coral'">通勤 {{ active.samples }} 次</span>
          <span class="tag-coral">详情图 0</span>
          <span class="tag-coral">AI 0</span>
        </div>
        <h4 class="mt-4 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">评分理由</h4>
        <div class="mt-2 rounded-xl border border-line bg-paper2 px-3.5 py-3 text-[11.5px] leading-6 text-muted">
          <template v-for="(value, key) in active.score_reasons" :key="key">
            <div v-if="key !== 'risk'">
              <b class="text-ink">{{ key }}</b>：{{ Array.isArray(value) ? value.join('、') : value }}
            </div>
          </template>
        </div>
        <h4 class="mt-4 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">按需分析成本</h4>
        <div class="mt-2 rounded-xl border border-line bg-paper2 px-3.5 py-3 text-[11.5px] leading-6 text-muted">
          {{ active.has_commute ? '通勤已有缓存，复用 0 次' : '通勤缺样本，需 1 次高德' }}；详情抓取 1 套（3–6 图）；AI 1 次（魔搭免费）。
        </div>
        <h4 class="mt-4 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">原始链接</h4>
        <div class="mono mt-2 break-all rounded-xl border border-line bg-paper2 px-3.5 py-3 text-[10px] text-faint">
          {{ active.url || '—' }}
        </div>
      </template>
      <template #footer>
        <button class="btn flex-1" @click="active = null">关闭</button>
        <button class="btn-primary flex-1" @click="toast('已加入候选池（演示）')">加入候选</button>
        <button class="btn-primary flex-1" @click="toast('已触发按需分析（演示）')">按需分析</button>
      </template>
    </AppDrawer>
  </div>
</template>
