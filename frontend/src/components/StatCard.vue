<script setup lang="ts">
defineProps<{
  label: string
  value: number | string
  hint?: string
  tone?: 'default' | 'emerald' | 'sky' | 'amber'
}>()

const toneClass: Record<string, string> = {
  default: 'text-slate-900',
  emerald: 'text-emerald-600',
  sky: 'text-sky-600',
  amber: 'text-amber-600',
}
</script>

<template>
  <div class="card p-4">
    <div class="flex items-start justify-between">
      <div class="text-xs font-medium uppercase tracking-wide text-slate-500">{{ label }}</div>
      <span class="h-2 w-2 rounded-full bg-slate-200" :class="tone === 'emerald' ? 'bg-emerald-400' : tone === 'sky' ? 'bg-sky-400' : tone === 'amber' ? 'bg-amber-400' : ''" />
    </div>
    <div class="mt-3 text-3xl font-semibold" :class="toneClass[tone ?? 'default']">{{ value }}</div>
    <div v-if="hint" class="mt-1 text-xs text-slate-400">{{ hint }}</div>
  </div>
</template>
