<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '@/api/client'
import type { CommuteSetting, SettingsStatus } from '@/api/types'

const status = ref<SettingsStatus | null>(null)
const commute = ref<CommuteSetting | null>(null)
const address = ref('')
const message = ref('')
const saving = ref(false)
const error = ref('')

async function load() {
  try {
    const [statusData, commuteData] = await Promise.all([
      api<SettingsStatus>('/api/settings/status'),
      api<CommuteSetting>('/api/settings/commute'),
    ])
    status.value = statusData
    commute.value = commuteData
    address.value = commuteData.address ?? ''
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function recalc() {
  message.value = ''
  try {
    const result = await api<{ jobs: number[] }>('/api/settings/enrich', { method: 'POST' })
    message.value = result.jobs.length
      ? `已入队 ${result.jobs.length} 个富化任务，稍后刷新查看新评分`
      : '已有富化任务在队列中'
  } catch (err) {
    message.value = err instanceof Error ? err.message : String(err)
  }
}

async function saveCommute() {
  if (!address.value.trim()) {
    message.value = '请先填写公司地址'
    return
  }
  saving.value = true
  message.value = ''
  try {
    commute.value = await api<CommuteSetting>('/api/settings/commute', {
      method: 'PUT',
      body: JSON.stringify({ address: address.value.trim(), city: '深圳', example: false }),
    })
    message.value = '通勤起点已保存，正在重新计算'
    await recalc()
  } catch (err) {
    message.value = err instanceof Error ? err.message : String(err)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-5">
    <div v-if="error" class="card border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
      加载失败：{{ error }}
    </div>

    <div v-if="status" class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <div class="card p-5 md:col-span-2 xl:col-span-3">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div class="text-xs uppercase tracking-wide text-slate-400">通勤起点</div>
            <div class="mt-2 text-lg font-semibold text-slate-900">
              {{ commute?.configured ? commute.address : '未设置（通勤按中性分）' }}
            </div>
            <div class="mt-1 text-xs text-slate-400">
              <span v-if="commute?.example" class="badge mr-2 bg-amber-50 text-amber-700">示例起点，请修改</span>
              公共交通路径按此地址计算；修改后点“保存并计算”
            </div>
          </div>
          <button class="btn-ghost" :disabled="saving" @click="recalc">重新计算评分</button>
        </div>
        <div class="mt-4 flex flex-col gap-2 sm:flex-row">
          <input
            v-model="address"
            class="input flex-1"
            placeholder="公司地址，例如：深圳市南山区科技园..."
            @keyup.enter="saveCommute"
          />
          <button class="btn-primary" :disabled="saving" @click="saveCommute">
            {{ saving ? '保存中…' : '保存并计算' }}
          </button>
        </div>
        <div v-if="message" class="mt-2 text-xs text-emerald-600">{{ message }}</div>
      </div>

      <div class="card p-5">
        <div class="text-xs uppercase tracking-wide text-slate-400">运行环境</div>
        <div class="mt-2 text-2xl font-semibold text-slate-900">{{ status.env }}</div>
        <div class="mt-1 text-xs text-slate-400">API 鉴权：{{ status.api_auth_enabled ? '已开启' : '未开启（dev）' }}</div>
      </div>

      <div class="card p-5">
        <div class="flex items-center justify-between">
          <div class="text-xs uppercase tracking-wide text-slate-400">飞书通知</div>
          <span class="badge" :class="status.feishu_configured ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'">
            {{ status.feishu_configured ? '已配置' : '未配置' }}
          </span>
        </div>
        <div class="mt-2 text-sm text-slate-700">RentRadar 应用机器人</div>
        <div class="mt-1 text-xs text-slate-400">即时推送与 09:00 日报</div>
      </div>

      <div class="card p-5">
        <div class="flex items-center justify-between">
          <div class="text-xs uppercase tracking-wide text-slate-400">高德 Web 服务</div>
          <span class="badge" :class="status.amap_configured ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'">
            {{ status.amap_configured ? '已配置' : '未配置' }}
          </span>
        </div>
        <div class="mt-2 text-sm text-slate-700">地理编码 / 通勤 / POI</div>
        <div class="mt-1 text-xs text-slate-400">主数据源</div>
      </div>

      <div class="card p-5">
        <div class="flex items-center justify-between">
          <div class="text-xs uppercase tracking-wide text-slate-400">百度地图 AK</div>
          <span class="badge" :class="status.baidu_configured ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'">
            {{ status.baidu_configured ? '已配置' : '未配置' }}
          </span>
        </div>
        <div class="mt-2 text-sm text-slate-700">兜底与交叉校验</div>
        <div class="mt-1 text-xs text-slate-400">
          出口代理：{{ status.baidu_proxy_configured ? '已配置（tx43）' : '未配置' }}
        </div>
      </div>

      <div class="card p-5">
        <div class="text-xs uppercase tracking-wide text-slate-400">数据源</div>
        <div class="mt-2 text-sm text-slate-700">贝壳租房（主）· 链家（手动）</div>
        <div class="mt-1 text-xs text-slate-400">采集走受控 Chrome CDP，登录态不落服务器</div>
      </div>

      <div class="card p-5">
        <div class="text-xs uppercase tracking-wide text-slate-400">安全提示</div>
        <div class="mt-2 text-sm leading-6 text-slate-700">
          密钥只存在服务器 `.env`（600），前端永远拿不到原始值；公网部署前必须加鉴权。
        </div>
      </div>
    </div>

    <div class="card p-5">
      <h2 class="text-sm font-semibold text-slate-900">相关入口</h2>
      <div class="mt-3 flex flex-wrap gap-2 text-sm">
        <a class="btn-ghost" href="/docs" target="_blank">API 文档</a>
        <a class="btn-ghost" href="https://console.amap.com/dev/key/app" target="_blank" rel="noreferrer">高德控制台</a>
        <a class="btn-ghost" href="https://lbsyun.baidu.com/apiconsole/key" target="_blank" rel="noreferrer">百度控制台</a>
        <a class="btn-ghost" href="https://open.feishu.cn/app" target="_blank" rel="noreferrer">飞书开放平台</a>
      </div>
    </div>
  </div>
</template>
