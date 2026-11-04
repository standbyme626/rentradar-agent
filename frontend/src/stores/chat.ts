import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type {
  AgentEvent,
  ChatMessage,
  ChatSession,
  Conditions,
  SavedMonitor,
} from '@/api/contracts'
import type { Inspection, Listing, ListingDetail } from '@/api/types'
import { agentApi } from '@/api/services/agent'
import { listingApi } from '@/api/services/listings'
import { conditionsFor } from '@/lib/conditions'
import { stateLabel } from '@/lib/watchlist'
import { useToast } from '@/composables/useToast'

const HISTORY_KEY = 'rentradar.history'
const MONITORS_KEY = 'rentradar.monitors'

function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function persist(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // storage can be unavailable in private mode; the session still works in memory
  }
}

export const useChatStore = defineStore('chat', () => {
  const { toast } = useToast()

  const phase = ref<'landing' | 'chat'>('landing')
  const messages = ref<ChatMessage[]>([])
  const cards = ref<Listing[]>([])
  const conditions = ref<Conditions>(conditionsFor(''))
  const activeTab = ref<'recs' | 'compare' | 'map'>('recs')
  const detail = ref<ListingDetail | null>(null)
  const detailLoading = ref(false)
  const sheetOpen = ref(false)
  const loading = ref(false)
  const amapUsed = ref(0)
  const amapMax = ref(15)
  const mobileResults = ref(false)
  const compareIds = ref<Set<number>>(new Set())
  const sessionId = ref<string | null>(null)
  const history = ref<ChatSession[]>(load<ChatSession[]>(HISTORY_KEY, []))
  const monitors = ref<SavedMonitor[]>(load<SavedMonitor[]>(MONITORS_KEY, []))
  const historyOpen = ref(false)
  const monitorsOpen = ref(false)
  const lastError = ref<string | null>(null)

  let seq = 0
  let runId = 0
  let activePrompt = ''
  let streamingMessageId: number | null = null

  const hasCards = computed(() => cards.value.length > 0)
  const amapLabel = computed(() => `${amapUsed.value} / ${amapMax.value}`)
  const amapPercent = computed(() =>
  Math.min(100, Math.round((amapUsed.value / amapMax.value) * 100)),
)
  const compareCards = computed(() => cards.value.filter((item) => compareIds.value.has(item.id)))
  const comparison = computed(() => (compareCards.value.length ? compareCards.value : cards.value))

  function persistHistory() {
    persist(HISTORY_KEY, history.value)
  }

  function persistMonitors() {
    persist(MONITORS_KEY, monitors.value)
  }

  function upsertSession(session: ChatSession) {
    const next = [...history.value]
    const index = next.findIndex((item) => item.id === session.id)
    if (index >= 0) next[index] = session
    else next.unshift(session)
    history.value = next.slice(0, 30)
    persistHistory()
  }

  async function hydrate() {
    try {
      const [sessions, saved] = await Promise.all([agentApi.listSessions(), agentApi.listMonitors()])
      const byId = new Map<string, ChatSession>()
      for (const item of [...history.value, ...sessions]) byId.set(item.id, item)
      history.value = [...byId.values()]
        .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
        .slice(0, 30)
      persistHistory()
      const monitorById = new Map<string, SavedMonitor>()
      for (const item of [...monitors.value, ...saved]) monitorById.set(item.id, item)
      monitors.value = [...monitorById.values()]
      persistMonitors()
    } catch {
      // history is optional; failures should not block the chat
    }
  }
  void hydrate()

  function add(message: Omit<ChatMessage, 'id'>) {
    seq += 1
    messages.value.push({ ...message, id: seq })
  }

  function reset() {
    runId += 1
    streamingMessageId = null
    phase.value = 'landing'
    messages.value = []
    cards.value = []
    conditions.value = conditionsFor('')
    activeTab.value = 'recs'
    detail.value = null
    detailLoading.value = false
    sheetOpen.value = false
    loading.value = false
    amapUsed.value = 0
    mobileResults.value = false
    compareIds.value = new Set()
    sessionId.value = null
    historyOpen.value = false
    monitorsOpen.value = false
    lastError.value = null
    activePrompt = ''
  }

  function handleEvent(event: AgentEvent, promptForHistory: string) {
    switch (event.type) {
      case 'session':
        sessionId.value = event.sessionId
        upsertSession({
          id: event.sessionId,
          title: event.title,
          prompt: promptForHistory,
          updatedAt: new Date().toISOString(),
        })
        break
      case 'plan':
        add({ role: 'agent', kind: 'plan', steps: event.steps.map((step) => ({ ...step })) })
        break
      case 'step': {
        const plan = [...messages.value].reverse().find((message) => message.kind === 'plan')
        const step = plan?.steps?.find((item) => item.id === event.id)
        if (step) {
          step.status = event.status
          if (event.desc) step.desc = event.desc
        }
        break
      }
      case 'delta': {
        if (!event.text) break
        if (streamingMessageId == null) {
          seq += 1
          streamingMessageId = seq
          messages.value.push({
            id: seq,
            role: 'agent',
            kind: 'text',
            text: event.text,
            streaming: true,
          })
        } else {
          const streamed = messages.value.find((item) => item.id === streamingMessageId)
          if (streamed) streamed.text = `${streamed.text || ''}${event.text}`
        }
        break
      }
      case 'message': {
        if (streamingMessageId != null) {
          const streamed = messages.value.find((item) => item.id === streamingMessageId)
          if (streamed) {
            streamed.text = event.text
            streamed.streaming = false
          }
          streamingMessageId = null
        } else {
          add({ role: 'agent', kind: 'text', text: event.text })
        }
        break
      }
      case 'conditions':
        conditions.value = { ...event.conditions }
        break
      case 'cards':
        cards.value = event.cards
        activeTab.value = 'recs'
        break
      case 'budget':
        amapUsed.value = event.amap
        if (event.cap) amapMax.value = event.cap
        break
      case 'tab':
        activeTab.value = event.tab
        break
      case 'ai':
        add({ role: 'agent', kind: 'ai', text: event.text })
        break
      case 'toast':
        toast(event.message)
        break
      case 'done': {
        if (streamingMessageId != null) {
          const streamed = messages.value.find((item) => item.id === streamingMessageId)
          if (streamed) streamed.streaming = false
          streamingMessageId = null
        }
        loading.value = false
        if (sessionId.value) {
          const session = history.value.find((item) => item.id === sessionId.value)
          if (session) {
            session.updatedAt = new Date().toISOString()
            persistHistory()
          }
        }
        break
      }
      case 'error':
        lastError.value = event.message
        loading.value = false
        add({ role: 'agent', kind: 'text', text: `分析失败：${event.message}` })
        toast('分析失败，请稍后重试')
        break
    }
  }

  async function run(request: { sessionId?: string; message: string }, promptForHistory: string) {
    const current = ++runId
    loading.value = true
    lastError.value = null
    try {
      for await (const event of agentApi.stream(request)) {
        if (current !== runId) return
        handleEvent(event, promptForHistory)
      }
    } catch (error) {
      if (current !== runId) return
      loading.value = false
      lastError.value = error instanceof Error ? error.message : '分析失败'
      add({ role: 'agent', kind: 'text', text: `分析失败：${lastError.value}` })
      toast('分析失败，请稍后重试')
    } finally {
      if (current === runId) loading.value = false
    }
  }

  function setCompany(company: string) {
    conditions.value = { ...conditions.value, company }
  }

  function start(prompt: string) {
    const text = prompt.trim()
    if (!text) return
    phase.value = 'chat'
    messages.value = []
    cards.value = []
    conditions.value = conditionsFor(text)
    activeTab.value = 'recs'
    detail.value = null
    loading.value = true
    amapUsed.value = 0
    mobileResults.value = false
    compareIds.value = new Set()
    sessionId.value = null
    historyOpen.value = false
    monitorsOpen.value = false
    lastError.value = null
    activePrompt = text
    add({ role: 'user', kind: 'text', text })
    void run({ message: text }, text)
  }

  function send(text: string) {
    const content = text.trim()
    if (!content || loading.value) return
    add({ role: 'user', kind: 'text', text: content })
    void run({ sessionId: sessionId.value ?? undefined, message: content }, activePrompt || content)
  }

  function toggleCompare(listing: Listing) {
    const next = new Set(compareIds.value)
    if (next.has(listing.id)) next.delete(listing.id)
    else next.add(listing.id)
    compareIds.value = next
  }

  async function loadDetail(id: number) {
    detailLoading.value = true
    try {
      const full = await listingApi.detail(id)
      if (detail.value?.id === id) detail.value = full
      return full
    } catch {
      toast('详情加载失败，请稍后重试')
      return null
    } finally {
      detailLoading.value = false
    }
  }

  function openDetail(listing: Listing) {
    detail.value = {
      ...listing,
      source_code: '',
      city_code: '',
      source_listing_id: '',
      orientation: null,
      floor: null,
      snapshots: [],
      events: [],
      delivery_probes: [],
      watch_state: null,
      watch_note: null,
      watch_updated_at: null,
      inspection: { items: {}, note: null, photos: [], updated_at: null },
      commute_stats: null,
    }
    void loadDetail(listing.id)
  }

  function openDetailById(id: number) {
    detail.value = {
      id,
      title: '',
      community_name: '',
      district: null,
      layout: null,
      area: null,
      rent: null,
      score: null,
      score_reasons: {},
      image_url: null,
      tags: [],
      agent_type: null,
      status: 'active',
      url: '',
      source_code: '',
      city_code: '',
      source_listing_id: '',
      orientation: null,
      floor: null,
      snapshots: [],
      events: [],
      delivery_probes: [],
      watch_state: null,
      watch_note: null,
      watch_updated_at: null,
      inspection: { items: {}, note: null, photos: [], updated_at: null },
      commute_stats: null,
    }
    void loadDetail(id)
  }

  function closeDetail() {
    detail.value = null
    detailLoading.value = false
  }

  async function refreshDetail() {
    if (detail.value) await loadDetail(detail.value.id)
  }

  async function setDetailState(state: string, note?: string | null) {
    if (!detail.value) return
    const id = detail.value.id
    try {
      await listingApi.setState(id, state, note ?? detail.value.watch_note)
      await loadDetail(id)
      toast(`已更新为「${stateLabel(state)}」`)
    } catch {
      toast('看房状态更新失败')
    }
  }

  async function saveDetailInspection(payload: Pick<Inspection, 'items' | 'note' | 'photos'>) {
    if (!detail.value) return false
    try {
      const saved = await listingApi.saveInspection(detail.value.id, payload)
      detail.value.inspection = saved
      toast('看房记录已保存')
      return true
    } catch {
      toast('看房记录保存失败')
      return false
    }
  }

  function openSheet() {
    sheetOpen.value = true
  }

  function closeSheet() {
    sheetOpen.value = false
  }

  function openHistory() {
    historyOpen.value = true
  }

  function closeHistory() {
    historyOpen.value = false
  }

  function openMonitors() {
    monitorsOpen.value = true
  }

  function closeMonitors() {
    monitorsOpen.value = false
  }

  function rerun(session: ChatSession) {
    closeHistory()
    start(session.prompt)
  }

  async function saveMonitor(name?: string) {
    if (!cards.value.length) {
      toast('先完成一次分析再保存监控')
      return
    }
    try {
      const monitor = await agentApi.saveMonitor({
        name: name || `${conditions.value.line} · ${conditions.value.budget}`,
        conditions: { ...conditions.value },
      })
      monitors.value = [monitor, ...monitors.value]
      persistMonitors()
      toast('已保存监控条件')
    } catch {
      toast('保存监控失败，请稍后重试')
    }
  }

  function saveListingMonitor(listing: Listing) {
    return saveMonitor(`关注 ${listing.community_name}`)
  }

  async function removeMonitor(id: string) {
    monitors.value = monitors.value.filter((item) => item.id !== id)
    persistMonitors()
    try {
      await agentApi.removeMonitor(id)
    } catch {
      // local cache removal still applies when the backend has no such monitor
    }
    toast('已删除监控')
  }

  return {
    phase,
    messages,
    cards,
    conditions,
    activeTab,
    detail,
    detailLoading,
    sheetOpen,
    loading,
    amapUsed,
    amapMax,
    amapLabel,
    amapPercent,
    mobileResults,
    compareIds,
    compareCards,
    comparison,
    sessionId,
    history,
    monitors,
    historyOpen,
    monitorsOpen,
    lastError,
    hasCards,
    setCompany,
    start,
    send,
    reset,
    toggleCompare,
    openDetail,
    openDetailById,
    closeDetail,
    refreshDetail,
    setDetailState,
    saveDetailInspection,
    openSheet,
    closeSheet,
    openHistory,
    closeHistory,
    openMonitors,
    closeMonitors,
    rerun,
    saveMonitor,
    saveListingMonitor,
    removeMonitor,
  }
})
