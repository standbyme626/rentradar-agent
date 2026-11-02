<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    name: string
    variant?: number
    label?: string
    height?: string
  }>(),
  { variant: 0, label: '封面 · 待抓图', height: '168px' },
)

const palettes = [
  ['#dcebe1', '#a9c6b6'],
  ['#f3e2d4', '#e4bfa6'],
  ['#e2e5ef', '#b9c2d8'],
  ['#efe6cf', '#d9c79e'],
]
const colors = computed(() => palettes[Math.abs(props.variant) % palettes.length])
const style = computed(() => ({
  height: props.height,
  background: `linear-gradient(135deg, ${colors.value[0]}, ${colors.value[1]})`,
}))
</script>

<template>
  <div class="relative overflow-hidden rounded-xl" :style="style">
    <div
      class="absolute inset-0"
      style="background: repeating-linear-gradient(90deg, transparent 0 22px, rgba(255, 255, 255, 0.18) 22px 23px)"
    />
    <span class="absolute left-2.5 top-2.5 rounded-full bg-ink/40 px-2 py-0.5 text-[9px] text-white">
      {{ label }}
    </span>
    <span class="absolute bottom-2 left-3 text-[44px] font-bold leading-none text-white/90">
      {{ name.slice(0, 1) }}
    </span>
  </div>
</template>
