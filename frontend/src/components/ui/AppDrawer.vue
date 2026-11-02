<script setup lang="ts">
import { onBeforeUnmount, watch } from 'vue'
import { X } from 'lucide-vue-next'

const props = defineProps<{
  open: boolean
  title: string
  subtitle?: string
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
      <div
        v-if="open"
        class="fixed inset-0 z-[90] bg-ink/35 backdrop-blur-[1px]"
        @click="emit('close')"
      />
    </Transition>
    <Transition name="slide">
      <aside
        v-if="open"
        class="fixed right-0 top-0 z-[100] flex h-full w-full max-w-[540px] flex-col border-l border-line bg-paper shadow-2xl"
      >
        <header class="flex items-start gap-3 border-b border-line px-5 py-4">
          <div class="min-w-0 flex-1">
            <h3 class="text-[15px] font-semibold leading-6 text-ink">{{ title }}</h3>
            <p v-if="subtitle" class="mt-0.5 text-[11px] text-muted">{{ subtitle }}</p>
          </div>
          <button class="btn-ghost btn-sm" @click="emit('close')">
            <X :size="15" />
          </button>
        </header>
        <div class="min-h-0 flex-1 overflow-auto px-5 pb-24 pt-4">
          <slot />
        </div>
        <footer
          v-if="$slots.footer"
          class="absolute inset-x-0 bottom-0 flex gap-2 border-t border-line bg-paper px-5 py-3"
        >
          <slot name="footer" />
        </footer>
      </aside>
    </Transition>
  </Teleport>
</template>
