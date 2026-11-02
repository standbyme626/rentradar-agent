<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    points: number[]
    color?: string
    height?: number
  }>(),
  { color: '#1f5d4a', height: 64 },
)

const coords = computed(() => {
  const values = props.points.length > 1 ? props.points : [0, 0]
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  return values.map((value, index) => {
    const x = (index / (values.length - 1)) * 360
    const y = 52 - ((value - min) / span) * 38
    return [Math.round(x * 10) / 10, Math.round(y * 10) / 10]
  })
})
const line = computed(() => coords.value.map(([x, y]) => `${x},${y}`).join(' '))
const area = computed(() => `0,64 ${line.value} 360,64`)
</script>

<template>
  <svg :height="height" viewBox="0 0 360 64" preserveAspectRatio="none" class="w-full">
    <polygon :points="area" :fill="`${color}12`" />
    <polyline :points="line" fill="none" :stroke="color" stroke-width="2" stroke-linecap="round" />
  </svg>
</template>
