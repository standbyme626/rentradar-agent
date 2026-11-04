<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { Check, Circle, ListChecks, Loader2, Sparkles, X } from 'lucide-vue-next'
import type { ChatMessage, PlanStatus } from '@/api/contracts'

const props = defineProps<{
  messages: ChatMessage[]
  loading: boolean
}>()

const scroller = ref<HTMLElement | null>(null)

watch(
  () => [props.messages.length, props.loading],
  async () => {
    await nextTick()
    scroller.value?.scrollTo({ top: scroller.value.scrollHeight, behavior: 'smooth' })
  },
)

function statusClass(status: PlanStatus) {
  if (status === 'done') return 'bg-forest text-white'
  if (status === 'now') return 'border border-forest text-forest'
  if (status === 'failed') return 'bg-coral-soft text-coral'
  return 'bg-sand text-faint'
}
</script>

<template>
  <div ref="scroller" class="min-h-0 flex-1 overflow-y-auto px-5 py-6">
    <div class="flex flex-col gap-5">
      <template v-for="message in messages" :key="message.id">
        <div v-if="message.role === 'user'" class="flex justify-end">
          <div class="max-w-[88%] rounded-2xl rounded-br-md bg-ink px-3.5 py-2 text-[13px] leading-7 text-paper">
            {{ message.text }}
          </div>
        </div>

        <div v-else class="flex gap-2.5">
          <div class="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-forest text-[11px] font-semibold text-white">
            R
          </div>
          <div class="min-w-0 flex-1">
            <div
              v-if="message.kind === 'text'"
              class="rounded-2xl border border-line bg-paper px-3.5 py-2.5 text-[13px] leading-7 text-ink"
            >
              {{ message.text }}
            </div>

            <div
              v-else-if="message.kind === 'plan'"
              class="rounded-2xl border border-line bg-paper px-3.5 py-3"
            >
              <div class="flex items-center gap-2 text-[12px] font-semibold text-ink">
                <ListChecks :size="14" />
                计划与工具
              </div>
              <div class="mt-2 space-y-1.5">
                <div
                  v-for="step in message.steps"
                  :key="step.id"
                  class="flex items-start gap-2 text-[11.5px] leading-5"
                >
                  <span
                    class="mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full"
                    :class="statusClass(step.status)"
                  >
                    <Check v-if="step.status === 'done'" :size="10" />
                    <Loader2 v-else-if="step.status === 'now'" :size="10" class="animate-spin" />
                    <Circle v-else-if="step.status === 'pending'" :size="7" />
                    <X v-else :size="10" />
                  </span>
                  <span>
                    <b class="font-semibold text-ink">{{ step.label }}</b>
                    <span class="text-muted"> · {{ step.desc }}</span>
                  </span>
                </div>
              </div>
              <div class="mt-2 border-t border-dashed border-line pt-2 text-[10.5px] text-faint">
                只对候选调用外部接口 · 缓存优先
              </div>
            </div>

            <div
              v-else
              class="rounded-2xl border border-forest/20 bg-forest-soft/60 px-3.5 py-3"
            >
              <div class="flex items-center gap-2 text-[12px] font-semibold text-forest">
                <Sparkles :size="14" />
                AI 视觉分析
                <span class="tag-amber">演示</span>
              </div>
              <div class="mt-2 grid grid-cols-2 gap-2 text-[11px]">
                <div class="rounded-lg border border-line bg-paper px-2.5 py-2">
                  <div class="text-[9.5px] text-muted">实拍概率</div>
                  <div class="text-[13px] font-semibold text-ink">82%</div>
                </div>
                <div class="rounded-lg border border-line bg-paper px-2.5 py-2">
                  <div class="text-[9.5px] text-muted">装修</div>
                  <div class="text-[13px] font-semibold text-ink">精装</div>
                </div>
                <div class="rounded-lg border border-line bg-paper px-2.5 py-2">
                  <div class="text-[9.5px] text-muted">朝向 / 采光</div>
                  <div class="text-[13px] font-semibold text-ink">南向 · 良好</div>
                </div>
                <div class="rounded-lg border border-line bg-paper px-2.5 py-2">
                  <div class="text-[9.5px] text-muted">可见问题</div>
                  <div class="text-[13px] font-semibold text-amber">1 处水渍</div>
                </div>
              </div>
              <p class="mt-2 text-[10.5px] leading-5 text-muted">{{ message.text }}</p>
              <p class="mt-1 text-[10px] leading-5 text-faint">
                示例图片分析卡片；实际封面分析/视觉标签在房源详情抽屉中展示，以真实证据为准。
              </p>
            </div>
          </div>
        </div>
      </template>

      <div v-if="loading" class="flex gap-2.5">
        <div class="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-forest text-[11px] font-semibold text-white">
          R
        </div>
        <div class="flex items-center gap-1 rounded-2xl border border-line bg-paper px-3.5 py-3">
          <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-forest [animation-delay:-0.2s]" />
          <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-forest [animation-delay:-0.1s]" />
          <span class="h-1.5 w-1.5 animate-bounce rounded-full bg-forest" />
        </div>
      </div>
    </div>
  </div>
</template>
