import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { listingApi } from '@/api/services/listings'
import type { Inspection, WatchlistEntry } from '@/api/types'
import { useToast } from '@/composables/useToast'
import { stateLabel } from '@/lib/watchlist'

export const useWatchlistStore = defineStore('watchlist', () => {
  const { toast } = useToast()
  const open = ref(false)
  const entries = ref<WatchlistEntry[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const active = computed(() => entries.value.filter((item) => item.state !== 'rejected'))
  const counts = computed(() => {
    const result: Record<string, number> = { all: entries.value.length }
    for (const item of entries.value) result[item.state] = (result[item.state] ?? 0) + 1
    return result
  })

  async function load() {
    loading.value = true
    error.value = null
    try {
      entries.value = await listingApi.watchlist()
    } catch {
      error.value = '看房清单加载失败，请稍后重试'
    } finally {
      loading.value = false
    }
  }

  function openLedger() {
    open.value = true
    void load()
  }

  function closeLedger() {
    open.value = false
  }

  async function setState(entry: WatchlistEntry, state: string, note?: string | null) {
    try {
      await listingApi.setState(entry.listing.id, state, note ?? entry.note)
      await load()
      toast(`已更新为「${stateLabel(state)}」`)
    } catch {
      toast('看房状态更新失败')
    }
  }

  async function saveInspection(
    entry: WatchlistEntry,
    payload: Pick<Inspection, 'items' | 'note' | 'photos'>,
  ) {
    try {
      const saved = await listingApi.saveInspection(entry.listing.id, payload)
      entry.inspection = saved
      await load()
      toast('看房记录已保存')
      return true
    } catch {
      toast('看房记录保存失败')
      return false
    }
  }

  async function exportCsv() {
    try {
      const blob = await listingApi.exportWatchlist()
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `rentradar-watchlist-${new Date().toISOString().slice(0, 10)}.csv`
      anchor.click()
      URL.revokeObjectURL(url)
      toast('看房清单 CSV 已导出')
    } catch {
      toast('导出失败，请稍后重试')
    }
  }

  return {
    open,
    entries,
    loading,
    error,
    active,
    counts,
    load,
    openLedger,
    closeLedger,
    setState,
    saveInspection,
    exportCsv,
  }
})
