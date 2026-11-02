<script setup lang="ts">
import { computed, ref } from 'vue'
import { adminApi } from '@/api/services/admin'
import { useLazyData } from '@/composables/useLazyData'
import { useToast } from '@/composables/useToast'
import AppSheet from '@/components/ui/AppSheet.vue'
import { tasks as tasksSnapshot } from './adminData'

const { toast } = useToast()
const helpOpen = ref(false)
const busy = ref(false)
const { data: items, loading, error, reload } = useLazyData(() => adminApi.tasks(), tasksSnapshot)
const task1 = computed(() => items.value.find((item) => item.id === 1) ?? items.value[0])
const task2 = computed(() => items.value.find((item) => item.id === 2) ?? items.value[1])
const filtersText = computed(() => (task1.value ? JSON.stringify(task1.value.filters) : '{}'))
const fastText = computed(() => `每 ${task1.value?.schedule?.fast_minutes ?? 30} 分钟 · 1 页`)
const slowText = computed(() => `每 ${task1.value?.schedule?.slow_minutes ?? 360} 分钟 · 30 页`)
const transport = computed(() => String(task1.value?.filters?.transport ?? 'cdp'))

async function runNow() {
  if (!task1.value || busy.value) return
  busy.value = true
  try {
    const result = await adminApi.runTask(task1.value.id)
    toast(`已入队任务 #${result.job_id}`)
  } catch {
    toast('运行失败，请稍后重试')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div>
    <h2 class="text-[20px] font-bold tracking-tight">采集任务</h2>
    <p class="mt-1 text-[12.5px] text-muted">当前采集运行中（贝壳 App API）；CDP 仅作兜底。</p>
    <div v-if="loading" class="mt-3 rounded-xl border border-line bg-paper2 px-3.5 py-2 text-[10.5px] text-muted">任务加载中…</div>
    <div v-else-if="error" class="mt-3 rounded-xl border border-coral/25 bg-coral-soft px-3.5 py-2 text-[10.5px] text-coral">
      {{ error }}
      <button class="ml-2 underline" @click="reload">重试</button>
    </div>

    <div class="mt-4 grid gap-4 xl:grid-cols-2">
      <section class="card p-4">
        <h3 class="panel-title">
          任务 1 · 贝壳 5 号线
          <span class="hint"><span :class="task1?.enabled ? 'tag-green' : 'tag-coral'">{{ task1?.enabled ? '运行中' : '已暂停' }}</span></span>
        </h3>
        <div class="mt-3 space-y-3">
          <div><label class="label">名称</label><input class="input" :value="task1?.name ?? ''" readonly /></div>
          <div><label class="label">过滤</label><input class="input" :value="filtersText" readonly /></div>
          <div class="grid gap-3 sm:grid-cols-2">
            <div><label class="label">快扫</label><input class="input" :value="fastText" readonly /></div>
            <div><label class="label">慢扫</label><input class="input" :value="slowText" readonly /></div>
          </div>
        </div>
        <div class="mt-3 flex flex-wrap gap-1.5">
          <span :class="task1?.enabled ? 'tag-green' : 'tag-coral'">{{ task1?.enabled ? 'enabled=true' : 'enabled=false' }}</span>
          <span class="tag-neutral">transport={{ transport }}</span>
          <span class="tag-neutral">scope=line:li110460696</span>
        </div>
        <div class="mt-3 flex flex-wrap gap-2">
          <button class="btn-primary" :disabled="busy || !task1" @click="runNow">
            {{ busy ? '提交中…' : '立即运行' }}
          </button>
          <button class="btn" @click="helpOpen = true">CDP 兜底说明</button>
        </div>
      </section>

      <section class="card p-4">
        <h3 class="panel-title">任务 2 · 链家 <span class="hint"><span class="tag-neutral">未启用</span></span></h3>
        <div class="mt-3 space-y-3">
          <div><label class="label">名称</label><input class="input" :value="task2?.name ?? ''" readonly /></div>
          <div>
            <label class="label">说明</label>
            <textarea class="input h-24" readonly>链家 robots 全站 Disallow，不自动抓；仅保留手动链接。当前采集以贝壳 App API 为准。</textarea>
          </div>
        </div>
        <div class="mt-3 flex flex-wrap gap-1.5"><span class="tag-neutral">robots 禁止</span><span class="tag-neutral">手动模式</span></div>
      </section>
    </div>

    <section class="card mt-4 p-4">
      <h3 class="panel-title">采集器行为 <span class="hint">当前主通道</span></h3>
      <div class="mt-3 grid gap-4 sm:grid-cols-3">
        <div><div class="text-[10px] text-faint">通道</div><div class="mt-0.5 text-[13px] font-semibold">贝壳 App API</div><div class="text-[10px] text-muted">免登录、免签名；CDP 兜底</div></div>
        <div><div class="text-[10px] text-faint">翻页</div><div class="mt-0.5 text-[13px] font-semibold">feed_query_id 链式</div><div class="text-[10px] text-muted">30 页/轮，按 house_code 去重</div></div>
        <div><div class="text-[10px] text-faint">验证码</div><div class="mt-0.5 text-[13px] font-semibold">CDP 检测即停</div><div class="text-[10px] text-muted">自动 enabled=false，不反复撞</div></div>
      </div>
    </section>

    <AppSheet :open="helpOpen" title="CDP 兜底说明" @close="helpOpen = false">
      <div class="space-y-3 text-[12px] leading-6 text-muted">
        <div class="rounded-xl border border-line bg-paper2 px-3.5 py-2.5">
          默认走贝壳 App API。只有 API 不可用时才切 CDP；CDP 需要受控 Chrome 的登录态。
        </div>
        <ol class="list-decimal space-y-1.5 pl-5">
          <li>打开受控 Windows Chrome（`C:\Chrome-debug`）。</li>
          <li>刷新贝壳 5 号线页面，手动完成人机验证。</li>
          <li>确认页面能正常显示房源列表。</li>
          <li>手动运行 `python -m app.cli crawl --task-id 1 --pages 1 --transport cdp`。</li>
        </ol>
        <div class="rounded-xl border border-amber/25 bg-amber-soft px-3.5 py-2.5 text-[10.5px] leading-5 text-amber">
          CDP 检测到验证页会立即停止，并把任务置为 enabled=false。不要在验证码未通过时连续重试。
        </div>
      </div>
      <template #footer>
        <button class="btn" @click="helpOpen = false">关闭</button>
      </template>
    </AppSheet>
  </div>
</template>
