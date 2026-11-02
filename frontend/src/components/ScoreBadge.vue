<script setup lang="ts">
defineProps<{ score: number | null }>()
</script>

<template>
  <span
    class="inline-flex min-w-12 items-center justify-center rounded-lg px-2 py-1 text-sm font-semibold"
    :class="
      score == null
        ? 'bg-slate-100 text-slate-400'
        : score >= 85
          ? 'bg-emerald-50 text-emerald-700'
          : score >= 70
            ? 'bg-sky-50 text-sky-700'
            : 'bg-amber-50 text-amber-700'
    "
  >
    {{ score ?? '—' }}
  </span>
</template>
