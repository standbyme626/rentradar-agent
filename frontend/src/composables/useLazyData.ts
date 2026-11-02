import { onMounted, ref } from 'vue'
import type { Ref } from 'vue'

export function useLazyData<T>(loader: () => Promise<T>, initial: T) {
  const data = ref(initial) as Ref<T>
  const loading = ref(true)
  const error = ref('')

  async function reload() {
    loading.value = true
    error.value = ''
    try {
      data.value = await loader()
    } catch (reason) {
      error.value = reason instanceof Error ? reason.message : '加载失败'
    } finally {
      loading.value = false
    }
  }

  onMounted(reload)
  return { data, loading, error, reload }
}
