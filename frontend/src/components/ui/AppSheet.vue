<script setup lang="ts">
import { onBeforeUnmount, watch } from 'vue'
import { X } from 'lucide-vue-next'

const props = defineProps<{
  open: boolean
  title: string
}>()
const emit = defineEmits<{ close: [] }>()

function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close')
}

watch(
  () => props.open,
  (open) => {
    document.body.style.overflow = open ? 'hidden' : ''
    if (open) window.addEventListener('keydown', onKey)
    else window.removeEventListener('keydown', onKey)
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  document.body.style.overflow = ''
  window.removeEventListener('keydown', onKey)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="fixed inset-0 z-[90] bg-ink/35 backdrop-blur-[1px]" @click="emit('close')" />
    </Transition>
    <Transition name="sheet">
      <div
        v-if="open"
        class="fixed inset-x-0 bottom-0 z-[101] max-h-[92vh] overflow-auto rounded-t-3xl border border-line bg-paper p-5 shadow-2xl sm:inset-x-auto sm:bottom-auto sm:left-1/2 sm:top-1/2 sm:w-[560px] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-3xl"
      >
        <header class="mb-4 flex items-center gap-3">
          <h3 class="flex-1 text-[15px] font-semibold">{{ title }}</h3>
          <button class="btn-ghost btn-sm" @click="emit('close')">
            <X :size="15" />
          </button>
        </header>
        <slot />
        <footer v-if="$slots.footer" class="mt-5 flex justify-end gap-2">
          <slot name="footer" />
        </footer>
      </div>
    </Transition>
  </Teleport>
</template>
