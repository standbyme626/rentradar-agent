<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    value: string | number
    sub?: string
    tone?: 'default' | 'green' | 'amber' | 'coral'
  }>(),
  { sub: '', tone: 'default' },
)

const toneClass: Record<string, string> = {
  default: 'bg-forest/50',
  green: 'bg-forest',
  amber: 'bg-amber',
  coral: 'bg-coral',
}
</script>

<template>
  <div class="relative overflow-hidden rounded-xl border border-line bg-paper px-4 py-3.5">
    <span class="absolute inset-y-0 left-0 w-[3px]" :class="toneClass[tone]" />
    <div class="text-[10.5px] text-muted">{{ label }}</div>
    <div class="mt-0.5 text-[22px] font-bold tracking-tight text-ink">{{ value }}</div>
    <div v-if="sub" class="text-[10px] text-faint">{{ sub }}</div>
  </div>
</template>
