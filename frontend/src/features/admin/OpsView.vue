<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import type { AdminService } from '@/api/contracts'
import type { CityInfo, ReferenceRent, ShareLink, SourceInfo } from '@/api/types'
import { adminApi } from '@/api/services/admin'
import { useToast } from '@/composables/useToast'

const { toast } = useToast()
const loading = ref(true)
const busy = ref(false)
const status = ref<Awaited<ReturnType<AdminService['opsStatus']>> | null>(null)
const links = ref<ShareLink[]>([])
const sources = ref<SourceInfo[]>([])
const cities = ref<CityInfo[]>([])
const references = ref<ReferenceRent[]>([])
const createdToken = ref('')
const shareForm = reactive({ label: '只读看板', expiresDays: 7 })
const refForm = reactive({ city: 'sz', text: '' })

const snapshot = computed(() => status.value?.snapshot)
const alerts = computed(() => status.value?.alerts ?? [])
const disk = computed(() => snapshot.value?.disk)
const backup = computed(() => snapshot.value?.backup)
const backupStatus = computed(() => {
  const marker = backup.value?.marker as { status?: string } | undefined
  if (marker?.status === 'failed') return { tone: 'tag-coral', text: '失败' }
  if (!backup.value?.configured) return { tone: 'tag-neutral', text: '未配置目录' }
  if (backup.value?.latest_age_hours == null) return { tone: 'tag-amber', text: '无备份' }
  return { tone: 'tag-green', text: `${backup.value.latest_age_hours} 小时前` }
})

function formatTime(value?: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleString('zh-CN', {
    hour12: false,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function load() {
  loading.value = true
  try {
    const [ops, share, src, city, refs] = await Promise.all([
      adminApi.opsStatus(),
      adminApi.shareLinks(),
      adminApi.sources(),
      adminApi.cities(),
      adminApi.referenceRents(),
    ])
    status.value = ops
    links.value = share
    sources.value = src
    cities.value = city
    references.value = refs
  } catch {
    toast('运维数据加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function runCheck() {
  if (busy.value) return
  busy.value = true
  try {
    await adminApi.runOpsCheck(true)
    await load()
    toast('告警检查完成')
  } catch {
    toast('检查失败，请稍后重试')
  } finally {
    busy.value = false
  }
}

async function createLink() {
  if (busy.value) return
  busy.value = true
  try {
    const link = await adminApi.createShareLink(shareForm.label, shareForm.expiresDays)
    createdToken.value = link.token ?? ''
    shareForm.label = '只读看板'
    await load()
    toast('分享链接已创建，完整链接只显示一次')
  } catch {
    toast('创建失败')
  } finally {
    busy.value = false
  }
}

async function revoke(id: number) {
  busy.value = true
  try {
    await adminApi.revokeShareLink(id)
    await load()
    toast('链接已撤销')
  } catch {
    toast('撤销失败')
  } finally {
    busy.value = false
  }
}

async function toggleSource(item: SourceInfo) {
  try {
    await adminApi.updateSource(item.code, !item.enabled)
    await load()
    toast(`来源 ${item.code} 已${item.enabled ? '停用' : '启用'}`)
  } catch {
    toast('来源状态更新失败')
  }
}

async function toggleCity(item: CityInfo) {
  try {
    await adminApi.updateCity(item.code, !item.enabled)
    await load()
    toast(`城市 ${item.name} 已${item.enabled ? '停用' : '启用'}`)
  } catch {
    toast('城市状态更新失败')
  }
}

async function importReferences() {
  if (busy.value || !refForm.text.trim()) return
  busy.value = true
  try {
    const rows = JSON.parse(refForm.text)
    if (!Array.isArray(rows)) throw new Error('rows')
    const result = await adminApi.importReferenceRents(refForm.city, rows)
    refForm.text = ''
    await load()
    toast(`参考租金导入完成：新增 ${result.created ?? 0}，更新 ${result.updated ?? 0}`)
  } catch {
    toast('导入失败：需要 JSON 数组，字段见下方示例')
  } finally {
    busy.value = false
  }
}

async function removeReference(id: number) {
  try {
    await adminApi.deleteReferenceRent(id)
    await load()
    toast('已删除')
  } catch {
    toast('删除失败')
  }
}

const shareUrl = computed(() =>
  createdToken.value ? `${window.location.origin}/share/${createdToken.value}` : '',
)

async function copyShare() {
  if (!shareUrl.value) return
  try {
    await navigator.clipboard.writeText(shareUrl.value)
    toast('完整链接已复制')
  } catch {
    toast('复制失败，请手动选择')
  }
}
</script>

<template>
  <div>
    <div class="flex flex-wrap items-end justify-between gap-2">
      <div>
        <h2 class="text-[20px] font-bold tracking-tight">运维</h2>
        <p class="mt-1 text-[12.5px] text-muted">
          CI、告警、备份恢复与公网只读分享。此页不暴露生产凭据；公网访问仍需 TLS/反向代理/限流。
        </p>
      </div>
      <button class="btn" :disabled="busy" @click="runCheck">{{ busy ? '检查中…' : '立即检查告警' }}</button>
    </div>

    <div v-if="loading" class="mt-4 card p-4 text-[11px] text-muted">加载中…</div>
    <template v-else>
      <div class="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <div class="card p-3.5">
          <div class="text-[10px] text-faint">数据库</div>
          <div class="mt-1 text-[18px] font-bold" :class="snapshot?.db === 'ok' ? 'text-forest' : 'text-coral'">
            {{ snapshot?.db === 'ok' ? '正常' : '异常' }}
          </div>
          <div class="text-[10px] text-muted">队列 {{ snapshot?.queued_jobs ?? 0 }} · 运行 {{ snapshot?.running_jobs ?? 0 }}</div>
        </div>
        <div class="card p-3.5">
          <div class="text-[10px] text-faint">最老排队</div>
          <div class="mt-1 text-[18px] font-bold">{{ snapshot?.oldest_queued_minutes ?? 0 }}<span class="text-[11px] font-normal"> 分钟</span></div>
          <div class="text-[10px] text-muted">1 小时失败 {{ snapshot?.failed_jobs_1h ?? 0 }}</div>
        </div>
        <div class="card p-3.5">
          <div class="text-[10px] text-faint">磁盘</div>
          <div class="mt-1 text-[18px] font-bold" :class="(disk?.used_pct ?? 0) >= 85 ? 'text-coral' : 'text-forest'">
            {{ disk?.used_pct ?? '—' }}<span class="text-[11px] font-normal">%</span>
          </div>
          <div class="text-[10px] text-muted">剩余 {{ disk?.free_gb ?? '—' }} GB</div>
        </div>
        <div class="card p-3.5">
          <div class="text-[10px] text-faint">最近备份</div>
          <div class="mt-1 text-[18px] font-bold"><span :class="backupStatus.tone">{{ backupStatus.text }}</span></div>
          <div class="text-[10px] text-muted">{{ backup?.dir || '—' }}</div>
        </div>
        <div class="card p-3.5">
          <div class="text-[10px] text-faint">告警</div>
          <div class="mt-1 text-[18px] font-bold" :class="alerts.length ? 'text-coral' : 'text-forest'">
            {{ alerts.length }}
          </div>
          <div class="text-[10px] text-muted">冷却 {{ status?.settings?.alertIntervalMinutes ?? 10 }} 分钟检查</div>
        </div>
      </div>

      <section class="card mt-4 p-4">
        <h3 class="panel-title">当前告警 <span class="hint">同一告警冷却期内不重复推送</span></h3>
        <div v-if="!alerts.length" class="mt-3 rounded-xl border border-forest/15 bg-forest-soft/60 px-3.5 py-3 text-[11px] text-forest">
          没有告警。队列、源失败、Provider 熔断、磁盘和备份均在阈值内。
        </div>
        <ul v-else class="mt-3 space-y-2">
          <li v-for="alert in alerts" :key="alert.code" class="rounded-xl border border-line bg-paper2 px-3.5 py-2.5 text-[11.5px]">
            <span :class="alert.severity === 'critical' ? 'tag-coral' : 'tag-amber'">{{ alert.severity }}</span>
            <span class="mono ml-2 text-[10px] text-faint">{{ alert.code }}</span>
            <div class="mt-1 text-muted">{{ alert.message }}</div>
          </li>
        </ul>
        <div v-if="snapshot?.failing_tasks?.length" class="mt-3 text-[10.5px] text-coral">
          连续失败任务：{{ snapshot.failing_tasks.map((item) => item.name).join('、') }}
        </div>
      </section>

      <div class="mt-4 grid gap-4 xl:grid-cols-2">
        <section class="card p-4">
          <h3 class="panel-title">公网只读分享 <span class="hint">token 可撤销 · noindex · 限流</span></h3>
          <p class="mt-1 text-[11px] leading-5 text-muted">
            分享页只含聚合字段（总量、区域中位价、价格带、覆盖），不含房源标题、图片、地址或联系方式。请只在 TLS/反向代理后暴露。
          </p>
          <div class="mt-3 grid gap-3 sm:grid-cols-2">
            <div><label class="label">备注</label><input v-model="shareForm.label" class="input" maxlength="64" /></div>
            <div><label class="label">有效期（天）</label><input v-model.number="shareForm.expiresDays" type="number" min="1" max="365" class="input" /></div>
          </div>
          <button class="btn-primary mt-3" :disabled="busy" @click="createLink">创建链接</button>
          <div v-if="shareUrl" class="mt-3 rounded-xl border border-amber/25 bg-amber-soft px-3.5 py-2.5 text-[10.5px] leading-5 text-amber">
            完整链接只显示一次：<span class="mono break-all">{{ shareUrl }}</span>
            <button class="ml-1 underline" @click="copyShare">复制</button>
          </div>
          <div class="mt-3 divide-y divide-line">
            <div v-for="link in links" :key="link.id" class="flex flex-wrap items-center gap-2 py-2.5 text-[11.5px]">
              <span class="font-semibold">{{ link.label }}</span>
              <span class="mono text-[10px] text-faint">{{ link.token_prefix }}…</span>
              <span :class="link.active ? 'tag-green' : 'tag-neutral'">{{ link.active ? '有效' : '已撤销' }}</span>
              <span class="text-[10px] text-muted">用 {{ link.use_count }} 次 · 到期 {{ formatTime(link.expires_at) }}</span>
              <button v-if="link.active" class="ml-auto text-[10px] text-coral underline" @click="revoke(link.id)">撤销</button>
            </div>
            <div v-if="!links.length" class="py-3 text-[11px] text-faint">还没有分享链接。</div>
          </div>
        </section>

        <section class="card p-4">
          <h3 class="panel-title">来源与城市 <span class="hint">独立开关</span></h3>
          <div class="mt-3 space-y-2">
            <div v-for="item in sources" :key="item.code" class="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-paper2 px-3 py-2 text-[11.5px]">
              <span class="font-semibold">{{ item.name }}</span>
              <span class="mono text-[10px] text-faint">{{ item.code }}</span>
              <span v-if="item.reserved" class="tag-neutral">预留</span>
              <span :class="item.enabled ? 'tag-green' : 'tag-neutral'">{{ item.enabled ? '启用' : '停用' }}</span>
              <span class="text-[10px] text-muted">{{ item.listings }} 套 · {{ item.tasks }} 任务</span>
              <button
                class="ml-auto text-[10px] underline"
                :disabled="!item.supported"
                @click="toggleSource(item)"
              >
                {{ item.enabled ? '停用' : '启用' }}
              </button>
            </div>
          </div>
          <div class="mt-3 space-y-2">
            <div v-for="item in cities" :key="item.code" class="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-paper2 px-3 py-2 text-[11.5px]">
              <span class="font-semibold">{{ item.name }}</span>
              <span class="mono text-[10px] text-faint">{{ item.code }}</span>
              <span :class="item.enabled ? 'tag-green' : 'tag-neutral'">{{ item.enabled ? '启用' : '停用' }}</span>
              <span class="text-[10px] text-muted">{{ item.listings }} 套 · {{ item.tasks }} 任务 · {{ item.communities }} 小区</span>
              <button class="ml-auto text-[10px] underline" @click="toggleCity(item)">
                {{ item.enabled ? '停用' : '启用' }}
              </button>
            </div>
          </div>
        </section>
      </div>

      <section class="card mt-4 p-4">
        <h3 class="panel-title">参考租金 <span class="hint">住建局/手动导入 · 有参考价时优先于挂牌中位价</span></h3>
        <div class="mt-3 grid gap-3 xl:grid-cols-2">
          <div>
            <label class="label">导入 JSON（数组）</label>
            <textarea
              v-model="refForm.text"
              class="input h-32 font-mono text-[10.5px]"
              placeholder='[{"communityName":"居里十舍","layout":"2室","monthlyRent":4600,"referenceMonth":"2026-10","source":"housing_bureau","confidence":0.8}]'
            />
            <div class="mt-2 flex items-center gap-2">
              <select v-model="refForm.city" class="input w-24">
                <option v-for="city in cities" :key="city.code" :value="city.code">{{ city.name }}</option>
              </select>
              <button class="btn-primary" :disabled="busy || !refForm.text.trim()" @click="importReferences">导入</button>
            </div>
          </div>
          <div class="max-h-48 overflow-auto rounded-xl border border-line">
            <table class="w-full text-left text-[11px]">
              <thead class="sticky top-0 border-b border-line bg-paper2 text-[9.5px] uppercase tracking-wide text-faint">
                <tr><th class="px-2 py-2">小区</th><th class="px-2 py-2">户型</th><th class="px-2 py-2">参考价</th><th class="px-2 py-2">月份</th><th class="px-2 py-2"></th></tr>
              </thead>
              <tbody>
                <tr v-for="item in references" :key="item.id" class="border-b border-line last:border-0">
                  <td class="px-2 py-2">{{ item.community_name || item.district || '—' }}</td>
                  <td class="px-2 py-2">{{ item.layout }}</td>
                  <td class="px-2 py-2">¥{{ item.monthly_rent }}</td>
                  <td class="px-2 py-2 text-muted">{{ item.reference_month }}</td>
                  <td class="px-2 py-2"><button class="text-[10px] text-coral underline" @click="removeReference(item.id)">删除</button></td>
                </tr>
                <tr v-if="!references.length"><td colspan="5" class="px-2 py-6 text-center text-[10.5px] text-faint">暂无参考租金；导入后评分会优先使用。</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>
