<script setup lang="ts">
export interface TabItem {
  key: string
  label: string
  count?: number | string
}

defineProps<{
  tabs: TabItem[]
  modelValue: string
}>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
</script>

<template>
  <div class="flex items-center gap-0.5 overflow-x-auto border-b border-line">
    <button
      v-for="tab in tabs"
      :key="tab.key"
      class="relative -mb-px whitespace-nowrap border-b-2 px-3.5 py-2.5 text-[12px] transition"
      :class="
        modelValue === tab.key
          ? 'border-forest font-semibold text-forest'
          : 'border-transparent text-muted hover:text-ink'
      "
      @click="emit('update:modelValue', tab.key)"
    >
      {{ tab.label }}
      <span
        v-if="tab.count !== undefined"
        class="ml-1 rounded-full bg-sand px-1.5 py-0.5 text-[9px] text-muted"
      >
        {{ tab.count }}
      </span>
    </button>
  </div>
</template>
