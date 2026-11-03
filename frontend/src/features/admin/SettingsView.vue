<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { AdminSettings, AuditLogEntry } from '@/api/contracts'
import { adminApi } from '@/api/services/admin'
import { providersApi } from '@/api/services/providers'
import { useToast } from '@/composables/useToast'
import { authApi } from '@/api/services/auth'
import { useAuthStore } from '@/stores/auth'

const { toast } = useToast()
const router = useRouter()
const auth = useAuthStore()
const loading = ref(true)
const saving = ref(false)
const audit = ref<AuditLogEntry[]>([])
const amapUsed = ref(0)
const amapLimit = ref(5000)
const changing = ref(false)
const passwordForm = reactive({ oldPassword: '', newPassword: '', confirm: '' })
const form = reactive<AdminSettings>({
  amapMonthlyCap: 5000,
  sessionAmapCap: 15,
  batchCap: 10,
  aiDailyCap: 500,
  notifyBatchCap: 10,
  notifyScoreMin: 75,
  priceDropPct: 8,
  quietStart: '23:00',
  quietEnd: '08:00',
  feishu: true,
  digest: true,
  quiet: true,
  pauseAlert: true,
  monitorPush: true,
  alertPush: true,
  alertQueueBacklog: 100,
  alertQueuedMinutes: 30,
  alertDiskPct: 85,
  alertBackupHours: 26,
  alertCooldownMinutes: 30,
  alertIntervalMinutes: 10,
})

const usagePercent = computed(() =>
  Math.min(100, Math.round((amapUsed.value / Math.max(1, amapLimit.value)) * 100)),
)

function formatTime(value: string) {
  return new Date(value).toLocaleString('zh-CN', {
    hour12: false,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(async () => {
  try {
    const [settings, logs, providers] = await Promise.all([
      adminApi.settings(),
      adminApi.auditLogs(20),
      providersApi.list('maps'),
    ])
    Object.assign(form, settings)
    audit.value = logs
    const amap = providers.find((item) => item.code === 'amap')
    if (amap) {
      amapUsed.value = amap.quota.used
      amapLimit.value = amap.quota.limit || form.amapMonthlyCap
    }
  } catch {
    toast('设置加载失败，使用默认值')
  } finally {
    loading.value = false
  }
})

async function save() {
  if (saving.value) return
  saving.value = true
  try {
    Object.assign(form, await adminApi.updateSettings({ ...form }))
    const providers = await providersApi.list('maps')
    const amap = providers.find((item) => item.code === 'amap')
    if (amap) {
      amapUsed.value = amap.quota.used
      amapLimit.value = amap.quota.limit || form.amapMonthlyCap
    }
    audit.value = await adminApi.auditLogs(20)
    toast('设置已保存，运行时已生效')
  } catch {
    toast('保存失败，请稍后重试')
  } finally {
    saving.value = false
  }
}

function toggle(
  key: 'feishu' | 'digest' | 'quiet' | 'pauseAlert' | 'monitorPush' | 'alertPush',
) {
  form[key] = !form[key]
}

async function changePassword() {
  if (changing.value) return
  if (passwordForm.newPassword.length < 8) {
    toast('新密码至少 8 位')
    return
  }
  if (passwordForm.newPassword !== passwordForm.confirm) {
    toast('两次输入的新密码不一致')
    return
  }
  changing.value = true
  try {
    await authApi.changePassword(passwordForm.oldPassword, passwordForm.newPassword)
    toast('密码已修改，请重新登录')
    auth.clear()
    await router.replace('/login')
  } catch {
    toast('修改失败，请检查原密码')
  } finally {
    changing.value = false
  }
}

const switches: Array<{
  key: 'feishu' | 'digest' | 'quiet' | 'pauseAlert' | 'monitorPush' | 'alertPush'
  label: string
}> = [
  { key: 'feishu', label: '飞书通知' },
  { key: 'monitorPush', label: '监控命中推送' },
  { key: 'digest', label: '09:00 日报' },
  { key: 'quiet', label: '夜间静默' },
  { key: 'pauseAlert', label: '采集暂停告警' },
  { key: 'alertPush', label: '运维告警推送' },
]
</script>

<template>
  <div>
    <h2 class="text-[20px] font-bold tracking-tight">设置</h2>
    <p class="mt-1 text-[12.5px] text-muted">
      预算、通知和监控推送已是运行时硬约束；保存后立即生效。
    </p>

    <div class="mt-4 grid gap-4 xl:grid-cols-2">
      <section class="card p-4">
        <h3 class="panel-title">预算 <span class="hint">{{ loading ? '加载中…' : '运行时生效' }}</span></h3>
        <div class="mt-3 space-y-3">
          <div>
            <label class="label">高德月上限</label>
            <input v-model.number="form.amapMonthlyCap" type="number" min="0" class="input" />
          </div>
          <div>
            <label class="label">单会话上限（AMAP）</label>
            <input v-model.number="form.sessionAmapCap" type="number" min="1" class="input" />
          </div>
          <div>
            <label class="label">单次批量上限（小区）</label>
            <input v-model.number="form.batchCap" type="number" min="1" class="input" />
          </div>
          <div>
            <label class="label">AI 每日上限（次）</label>
            <input v-model.number="form.aiDailyCap" type="number" min="0" class="input" />
          </div>
          <div>
            <label class="label">本月已用（Provider 实测）</label>
            <input class="input" :value="`${amapUsed} / ${amapLimit} 次`" readonly />
          </div>
        </div>
        <div class="mt-3 h-1.5 overflow-hidden rounded-full bg-sand">
          <div
            class="h-full rounded-full"
            :class="usagePercent >= 90 ? 'bg-coral' : usagePercent >= 70 ? 'bg-amber' : 'bg-forest'"
            :style="{ width: `${usagePercent}%` }"
          />
        </div>
        <div class="mt-2 rounded-xl border border-forest/15 bg-forest-soft/60 px-3.5 py-2.5 text-[10.5px] leading-5 text-forest">
          高德、贝壳和 LLM 调用都会写入 Provider 用量与调用日志；额度不足时直接拦截，不会先打再记账。
        </div>
        <button class="btn-primary mt-3" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </section>

      <section class="card p-4">
        <h3 class="panel-title">通知与静默</h3>
        <div class="mt-3 grid grid-cols-2 gap-3">
          <div>
            <label class="label">每轮通知上限</label>
            <input v-model.number="form.notifyBatchCap" type="number" min="1" max="100" class="input" />
          </div>
          <div>
            <label class="label">新房最低分</label>
            <input v-model.number="form.notifyScoreMin" type="number" min="0" max="100" class="input" />
          </div>
          <div>
            <label class="label">降价阈值 %</label>
            <input v-model.number="form.priceDropPct" type="number" min="0" max="100" class="input" />
          </div>
          <div>
            <label class="label">监控推送</label>
            <div class="input flex items-center text-[11px] text-muted">
              {{ form.monitorPush ? '启用' : '停用' }}
            </div>
          </div>
          <div>
            <label class="label">静默开始</label>
            <input v-model="form.quietStart" class="input" placeholder="23:00" />
          </div>
          <div>
            <label class="label">静默结束</label>
            <input v-model="form.quietEnd" class="input" placeholder="08:00" />
          </div>
        </div>
        <div class="mt-2 divide-y divide-line text-[11.5px]">
          <div v-for="item in switches" :key="item.key" class="flex items-center py-3">
            <span>{{ item.label }}</span>
            <button
              class="ml-auto h-5 w-8 rounded-full p-0.5 transition"
              :class="form[item.key] ? 'bg-forest' : 'bg-line2'"
              :aria-pressed="form[item.key]"
              @click="toggle(item.key)"
            >
              <span
                class="block h-4 w-4 rounded-full bg-white transition"
                :class="form[item.key] ? 'translate-x-3' : 'translate-x-0'"
              />
            </button>
          </div>
        </div>
        <button class="btn-primary mt-3" :disabled="saving" @click="save">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </section>
    </div>

    <section class="card mt-4 p-4">
      <h3 class="panel-title">运维告警 <span class="hint">scheduler 每 {{ form.alertIntervalMinutes }} 分钟检查</span></h3>
      <p class="mt-1 text-[11px] text-muted">
        队列积压、源连续失败、Provider 熔断、磁盘占用、备份失败/过期会推飞到「运维」页并可推送飞书；同一告警在冷却窗口内不重复推送。
      </p>
      <div class="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <div>
          <label class="label">队列积压阈值（个）</label>
          <input v-model.number="form.alertQueueBacklog" type="number" min="1" class="input" />
        </div>
        <div>
          <label class="label">排队超时阈值（分钟）</label>
          <input v-model.number="form.alertQueuedMinutes" type="number" min="1" class="input" />
        </div>
        <div>
          <label class="label">磁盘使用率阈值（%）</label>
          <input v-model.number="form.alertDiskPct" type="number" min="50" max="100" class="input" />
        </div>
        <div>
          <label class="label">备份过期阈值（小时）</label>
          <input v-model.number="form.alertBackupHours" type="number" min="1" max="168" class="input" />
        </div>
        <div>
          <label class="label">告警冷却（分钟）</label>
          <input v-model.number="form.alertCooldownMinutes" type="number" min="5" class="input" />
        </div>
        <div>
          <label class="label">检查间隔（分钟）</label>
          <input v-model.number="form.alertIntervalMinutes" type="number" min="5" class="input" />
        </div>
      </div>
      <button class="btn-primary mt-3" :disabled="saving" @click="save">
        {{ saving ? '保存中…' : '保存' }}
      </button>
    </section>

    <section class="card mt-4 p-4">
      <h3 class="panel-title">账号安全 <span class="hint">{{ auth.displayName }}</span></h3>
      <p class="mt-1 text-[11px] text-muted">修改密码会撤销该账号的所有登录会话，需要重新登录。</p>
      <div class="mt-3 grid gap-3 sm:grid-cols-3">
        <div>
          <label class="label">原密码</label>
          <input v-model="passwordForm.oldPassword" type="password" class="input" autocomplete="current-password" />
        </div>
        <div>
          <label class="label">新密码</label>
          <input v-model="passwordForm.newPassword" type="password" class="input" autocomplete="new-password" />
        </div>
        <div>
          <label class="label">确认新密码</label>
          <input v-model="passwordForm.confirm" type="password" class="input" autocomplete="new-password" />
        </div>
      </div>
      <button class="btn mt-3" :disabled="changing" @click="changePassword">
        {{ changing ? '修改中…' : '修改密码' }}
      </button>
    </section>

    <section class="card mt-4 p-4">
      <h3 class="panel-title flex items-center justify-between">
        <span>审计日志 <span class="hint">最近 20 条</span></span>
        <span class="text-[10px] font-normal text-faint">登录、设置、Provider、任务、监控</span>
      </h3>
      <div class="mt-3 overflow-x-auto">
        <table class="w-full text-left text-[11.5px]">
          <thead class="border-b border-line text-[9.5px] uppercase tracking-wide text-faint">
            <tr>
              <th class="px-2 py-2 font-semibold">时间</th>
              <th class="px-2 py-2 font-semibold">用户</th>
              <th class="px-2 py-2 font-semibold">动作</th>
              <th class="px-2 py-2 font-semibold">对象</th>
              <th class="px-2 py-2 font-semibold">IP</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in audit" :key="item.id" class="border-b border-line last:border-0">
              <td class="px-2 py-2 text-muted">{{ formatTime(item.createdAt) }}</td>
              <td class="px-2 py-2">{{ item.username || '—' }}</td>
              <td class="mono px-2 py-2">{{ item.action }}</td>
              <td class="px-2 py-2 text-muted">{{ item.target || '—' }}</td>
              <td class="mono px-2 py-2 text-faint">{{ item.ip || '—' }}</td>
            </tr>
            <tr v-if="!audit.length">
              <td colspan="5" class="px-2 py-8 text-center text-[11px] text-faint">暂无审计记录</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
