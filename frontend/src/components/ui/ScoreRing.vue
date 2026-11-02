<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    score?: number | null
    size?: number
  }>(),
  { score: null, size: 52 },
)

const pct = computed(() => Math.max(0, Math.min(100, props.score ?? 0)))
const inner = computed(() => Math.max(24, props.size - 10))
const fontSize = computed(() => Math.max(11, Math.round(props.size / 4.2)))
const ringStyle = computed(() => ({
  width: `${props.size}px`,
  height: `${props.size}px`,
  background: `conic-gradient(#1f5d4a ${pct.value}%, #e8eef6 0)`,
}))
const innerStyle = computed(() => ({ width: `${inner.value}px`, height: `${inner.value}px` }))
</script>

<template>
  <div class="grid shrink-0 place-items-center rounded-full" :style="ringStyle">
    <div class="grid place-items-center rounded-full bg-paper" :style="innerStyle">
      <span class="font-bold text-forest" :style="{ fontSize: `${fontSize}px` }">
        {{ score ?? '—' }}
      </span>
    </div>
  </div>
</template>
