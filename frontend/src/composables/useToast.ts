import { ref } from 'vue'

export interface ToastItem {
  id: number
  message: string
}

const items = ref<ToastItem[]>([])
let seq = 0

export function useToast() {
  function toast(message: string) {
    const id = ++seq
    items.value.push({ id, message })
    window.setTimeout(() => {
      items.value = items.value.filter((item) => item.id !== id)
    }, 2200)
  }
  return { items, toast }
}
