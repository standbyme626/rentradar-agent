<script setup lang="ts">
import { useToast } from '@/composables/useToast'

const { items } = useToast()
</script>

<template>
  <Teleport to="body">
    <div class="pointer-events-none fixed inset-x-0 bottom-6 z-[200] flex flex-col items-center gap-2">
      <TransitionGroup name="fade">
        <div
          v-for="item in items"
          :key="item.id"
          class="rounded-xl bg-ink px-4 py-2.5 text-[12px] text-paper shadow-lift"
        >
          {{ item.message }}
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>
