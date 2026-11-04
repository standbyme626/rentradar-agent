<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import {
  ArrowRight,
  Bell,
  ClipboardList,
  Clock3,
  History,
  Home,
  LogOut,
  Image as ImageIcon,
  MapPin,
  MessageSquare,
  Plus,
  Trash2,
  Wallet,
  X,
} from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { useWatchlistStore } from '@/stores/watchlist'
import { agentApi } from '@/api/services/agent'
import type { Listing } from '@/api/types'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import AppTabs from '@/components/ui/AppTabs.vue'
import ChatThread from './ChatThread.vue'
import RecommendationCard from './RecommendationCard.vue'
import ComparisonTable from './ComparisonTable.vue'
import MapPanel from './MapPanel.vue'
import ConditionSheet from './ConditionSheet.vue'
import ListingDetailDrawer from './ListingDetailDrawer.vue'
import WatchlistDrawer from './WatchlistDrawer.vue'

const router = useRouter()
const store = useChatStore()
const auth = useAuthStore()
const watchlist = useWatchlistStore()
const {
  phase,
  messages,
  cards,
  conditions,
  activeTab,
  detail,
  detailLoading,
  sheetOpen,
  loading,
  mobileResults,
  compareIds,
  comparison,
  history,
  monitors,
  historyOpen,
  monitorsOpen,
} = storeToRefs(store)
const { toast } = useToast()

const prompt = ref('')
const chatInput = ref('')
const isMobile = ref(false)
const statCount = ref<number | null>(null)
const companyName = ref('')

async function signOut() {
  await auth.logout()
  await router.replace('/login')
}

async function syncStatCount() {
  try {
    statCount.value = (await agentApi.stats()).listings
  } catch {
    // keep the bundled count when the backend is unavailable
  }
}

const displayCompany = computed(() => companyName.value || '公司地址')

const examples = computed(() => [
  {
    icon: Clock3,
    title: '通勤优先',
    text: `${displayCompany.value} · 4000 · 40 分钟内`,
    prompt: `公司在${displayCompany.value}，预算 4000，想住 5 号线沿线，通勤 40 分钟内，最好有电梯`,
  },
  {
    icon: Home,
    title: '两个人住',
    text: '两居 · 4500 · 5 号线',
    prompt: '两个人住，想要两居，预算 4500，5 号线沿线，通勤 45 分钟内',
  },
  {
    icon: Wallet,
    title: '预算优先',
    text: '3000 · 龙岗 · 接受远一点',
    prompt: '预算 3000，龙岗方向，接受 60 分钟通勤，两居优先',
  },
  {
    icon: ImageIcon,
    title: '先看图片',
    text: '实拍 · 装修 · 图文一致',
    prompt: '帮我对比 5 号线 4500 以内的几套，重点看实拍和装修',
  },
])

const tabs = computed(() => [
  { key: 'recs', label: '推荐', count: cards.value.length },
  { key: 'compare', label: '对比' },
  { key: 'map', label: '地图' },
])

const conditionChips = computed(() => [
  { label: '预算', value: conditions.value.budget },
  { label: '线路', value: conditions.value.line },
  { label: '通勤', value: conditions.value.commute },
  { label: '户型', value: conditions.value.layout },
  { label: '必须', value: conditions.value.must },
])

const showThread = computed(() => !isMobile.value || !mobileResults.value)
const showCanvas = computed(() => !isMobile.value || mobileResults.value)

function syncMobile() {
  isMobile.value = window.innerWidth < 840
}

onMounted(() => {
  syncMobile()
  window.addEventListener('resize', syncMobile)
  void syncStatCount()
  void agentApi
    .settings()
    .then((settings) => {
      const address = settings.commute_destination?.address
      if (address) {
        companyName.value = address
        store.setCompany(address)
      }
    })
    .catch(() => {
      // keep the generic placeholder; sending a message will surface API errors
    })
})
onBeforeUnmount(() => window.removeEventListener('resize', syncMobile))

watch(cards, (value) => {
  if (isMobile.value && value.length) {
    window.setTimeout(() => {
      mobileResults.value = true
    }, 900)
  }
})

function start(text?: string) {
  const content = text ?? prompt.value
  if (!content.trim()) return
  prompt.value = ''
  mobileResults.value = false
  void store.start(content)
}

function startExample(text: string) {
  prompt.value = text
  start(text)
}

function send() {
  if (!chatInput.value.trim()) return
  store.send(chatInput.value)
  chatInput.value = ''
}

function quick(text: string) {
  store.send(text)
}

function applyConditions(text: string) {
  store.closeSheet()
  prompt.value = text
  start(text)
}

function reset() {
  store.reset()
  prompt.value = ''
  chatInput.value = ''
  mobileResults.value = false
}

function setTab(tab: string) {
  activeTab.value = tab as 'recs' | 'compare' | 'map'
}

function openDetail(listing: Listing) {
  store.openDetail(listing)
}

function openDetailById(id: number) {
  store.openDetailById(id)
}

function setDetailState(state: string, note: string | null) {
  void store.setDetailState(state, note)
  void watchlist.load()
}

async function saveDetailInspection(payload: Parameters<typeof store.saveDetailInspection>[0]) {
  if (await store.saveDetailInspection(payload)) void watchlist.load()
}

function compare(listing: Listing) {
  store.toggleCompare(listing)
  toast(compareIds.value.has(listing.id) ? `已加入对比：${listing.community_name}` : `已移出对比：${listing.community_name}`)
}

function save(listing: Listing) {
  void store.saveListingMonitor(listing)
}

function formatDate(value: string) {
  return new Date(value).toLocaleString('zh-CN', {
    hour12: false,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <div class="min-h-screen bg-canvas text-ink">
    <header
      class="sticky top-0 z-40 flex h-16 items-center gap-3 border-b border-line/80 bg-canvas/85 px-4 backdrop-blur sm:px-7"
    >
      <button class="flex items-center gap-2.5" @click="reset">
        <div class="grid h-8 w-8 place-items-center rounded-[10px] bg-forest text-white">
          <MapPin :size="16" />
        </div>
        <div class="text-left">
          <div class="text-[14.5px] font-bold tracking-tight text-ink">RentRadar</div>
          <div class="-mt-0.5 text-[10px] text-muted">一句话找房 · 深圳 5 号线</div>
        </div>
      </button>

      <div class="ml-auto flex items-center gap-2">
        <span
          class="hidden items-center gap-1.5 rounded-full border border-line bg-paper/70 px-3 py-1 text-[11px] text-muted sm:inline-flex"
        >
          <span class="h-1.5 w-1.5 rounded-full bg-forest" />
          本地已索引 <b class="font-semibold text-ink">{{ statCount ?? '—' }}</b> 套
        </span>
        <button class="btn-ghost btn-sm" title="新对话" @click="reset">
          <Plus :size="16" />
        </button>
        <button class="btn-ghost btn-sm" title="历史需求" @click="store.openHistory()">
          <History :size="16" />
        </button>
        <button class="btn-ghost btn-sm" title="我的监控" @click="store.openMonitors()">
          <Bell :size="16" />
        </button>
        <button class="relative btn-ghost btn-sm" title="看房清单" @click="watchlist.openLedger()">
          <ClipboardList :size="16" />
          <span
            v-if="watchlist.active.length"
            class="absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full bg-forest px-1 text-[9px] font-semibold text-white"
          >{{ watchlist.active.length }}</span>
        </button>
        <span class="hidden max-w-[110px] truncate text-[10.5px] text-muted sm:inline">
          {{ auth.displayName || '—' }}
        </span>
        <button class="btn-ghost btn-sm" title="退出登录" @click="signOut">
          <LogOut :size="15" />
        </button>
        <div class="grid h-8 w-8 place-items-center rounded-full bg-ink text-[10px] font-semibold text-paper">
          {{ (auth.displayName || 'R').slice(0, 1).toUpperCase() }}
        </div>
      </div>
    </header>

    <!-- 入口 -->
    <main
      v-if="phase === 'landing'"
      class="relative flex min-h-[calc(100vh-64px)] items-center justify-center overflow-hidden px-4 py-10 sm:px-6"
    >
      <div class="pointer-events-none absolute -right-64 -top-72 h-[780px] w-[780px] rounded-full bg-forest/10 blur-3xl" />
      <div class="pointer-events-none absolute -bottom-80 -left-64 h-[620px] w-[620px] rounded-full bg-coral/10 blur-3xl" />

      <section class="relative z-10 w-full max-w-[800px] text-center">
        <div class="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-forest">
          <span class="h-px w-5 bg-forest/50" />
          先说人话，再谈条件
        </div>
        <h1 class="mt-4 text-[34px] font-[680] leading-[1.12] tracking-[-1.8px] text-ink sm:text-[52px]">
          今天想住在<span class="text-forest">哪里</span>？
        </h1>
        <p class="mx-auto mt-3 max-w-[520px] text-[14.5px] leading-8 text-muted">
          告诉我公司在哪、预算多少、能接受多长通勤。我先查本机库存，再只对你眼前的几套算通勤、抓详情。
        </p>

        <div
          class="mt-7 rounded-[22px] border border-line2 bg-paper p-4 text-left shadow-lift transition focus-within:border-forest focus-within:ring-4 focus-within:ring-forest-soft"
        >
          <textarea
            v-model="prompt"
            rows="2"
            class="w-full resize-none bg-transparent text-[15px] leading-7 text-ink outline-none placeholder:text-faint sm:text-[16px]"
            :placeholder="`例如：公司在${displayCompany}，预算 4000，想住 5 号线沿线，通勤 40 分钟内，最好有电梯`"
            @keydown.enter.exact.prevent="start()"
          />
          <div class="mt-2 flex items-center gap-2">
            <button class="btn btn-sm" @click="store.openSheet()">
              <Plus :size="13" />
              补充条件
            </button>
            <span class="ml-auto hidden text-[11px] text-faint sm:block">Enter 发送 · Shift + Enter 换行</span>
            <button class="btn-primary" @click="start()">
              开始找房
              <ArrowRight :size="14" />
            </button>
          </div>
        </div>

        <div class="mt-4 grid gap-2.5 text-left sm:grid-cols-2">
          <button
            v-for="example in examples"
            :key="example.title"
            class="flex items-start gap-3 rounded-2xl border border-line bg-paper/60 px-4 py-3 text-left transition hover:-translate-y-0.5 hover:border-forest/30 hover:bg-paper hover:shadow-card"
            @click="startExample(example.prompt)"
          >
            <span class="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-forest-soft text-forest">
              <component :is="example.icon" :size="15" />
            </span>
            <span>
              <b class="block text-[13px] font-semibold text-ink">{{ example.title }}</b>
              <small class="mt-0.5 block text-[11.5px] leading-5 text-muted">{{ example.text }}</small>
            </span>
          </button>
        </div>

        <div class="mt-5 flex flex-wrap justify-center gap-4 text-[11.5px] text-faint">
          <span class="inline-flex items-center gap-1.5"><i class="h-1 w-1 rounded-full bg-forest/60" />先查本地 {{ statCount ?? '—' }} 套</span>
          <span class="inline-flex items-center gap-1.5"><i class="h-1 w-1 rounded-full bg-forest/60" />只为候选算通勤</span>
          <span class="inline-flex items-center gap-1.5"><i class="h-1 w-1 rounded-full bg-forest/60" />不自动下单</span>
        </div>
      </section>
    </main>

    <!-- 对话 + 结果 -->
    <main v-else class="flex h-[calc(100vh-64px)] min-h-[560px]">
      <aside
        class="w-full flex-col border-r border-line bg-paper/60 md:flex md:w-[390px] md:shrink-0"
        :class="showThread ? 'flex' : 'hidden'"
      >
        <div class="flex h-14 shrink-0 items-center gap-2 border-b border-line px-4">
          <div class="min-w-0 flex-1">
            <div class="text-[12.5px] font-semibold text-ink">找房助手</div>
            <div class="-mt-0.5 text-[10px] text-faint">本次会话 · 本地库存</div>
          </div>
          <button v-if="isMobile" class="tag-green" @click="mobileResults = true">结果</button>
          <button class="btn-ghost btn-sm" title="新对话" @click="reset">
            <Plus :size="15" />
          </button>
        </div>

        <ChatThread :messages="messages" :loading="loading" />

        <div class="flex flex-wrap gap-1.5 px-4 pb-2">
          <button class="rounded-full border border-line2 bg-paper px-2.5 py-1 text-[10.5px] text-muted transition hover:border-forest hover:bg-forest-soft hover:text-forest" @click="quick('只看 40 分钟内')">只看 40 分钟内</button>
          <button class="rounded-full border border-line2 bg-paper px-2.5 py-1 text-[10.5px] text-muted transition hover:border-forest hover:bg-forest-soft hover:text-forest" @click="quick('预算压到 4000')">预算压到 4000</button>
          <button class="rounded-full border border-line2 bg-paper px-2.5 py-1 text-[10.5px] text-muted transition hover:border-forest hover:bg-forest-soft hover:text-forest" @click="quick('对比这几套')">对比这几套</button>
          <button class="rounded-full border border-line2 bg-paper px-2.5 py-1 text-[10.5px] text-muted transition hover:border-forest hover:bg-forest-soft hover:text-forest" @click="quick('看图片分析')">看图片</button>
          <button class="rounded-full border border-line2 bg-paper px-2.5 py-1 text-[10.5px] text-muted transition hover:border-forest hover:bg-forest-soft hover:text-forest" @click="quick('保存为监控')">保存监控</button>
        </div>

        <div class="border-t border-line px-3.5 py-3">
          <div class="flex items-center gap-2 rounded-xl border border-line2 bg-paper px-3 py-1.5 transition focus-within:border-forest focus-within:ring-2 focus-within:ring-forest-soft">
            <input
              v-model="chatInput"
              class="min-w-0 flex-1 bg-transparent text-[12.5px] text-ink outline-none placeholder:text-faint"
              placeholder="继续追问，比如「太贵了」「要两居」"
              @keydown.enter="send"
            />
            <button class="grid h-7 w-7 place-items-center rounded-lg bg-forest text-white transition hover:bg-forest-dark" @click="send">
              <ArrowRight :size="14" />
            </button>
          </div>
        </div>
      </aside>

      <section
        class="min-w-0 flex-1 flex-col bg-canvas"
        :class="[showCanvas ? 'flex' : 'hidden', isMobile ? 'fixed inset-x-0 bottom-0 top-16 z-50' : '']"
      >
        <div class="flex flex-wrap items-center gap-2 border-b border-line bg-canvas/80 px-4 py-3 backdrop-blur sm:px-6">
          <button v-if="isMobile" class="btn btn-sm" @click="mobileResults = false">对话</button>
          <button
            v-for="chip in conditionChips"
            :key="chip.label"
            class="inline-flex items-center gap-1 rounded-full border border-line bg-paper px-2.5 py-1 text-[10.5px] text-muted"
          >
            <b class="font-semibold text-ink">{{ chip.value }}</b>
          </button>
          <div class="ml-auto flex items-center gap-1.5">
            <button class="btn btn-sm" @click="store.saveMonitor()">保存监控</button>
            <button class="btn-dark btn-sm" @click="setTab('compare')">对比</button>
          </div>
        </div>

        <AppTabs :model-value="activeTab" :tabs="tabs" class="px-4 sm:px-6" @update:model-value="setTab" />

        <div class="min-h-0 flex-1 overflow-y-auto px-4 pb-24 pt-4 sm:px-6">
          <div class="mb-3 flex flex-wrap items-center gap-2 text-[11.5px] text-muted">
            <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-forest shadow-[0_0_0_3px_#e6efe9]" />
            已出 <b class="font-semibold text-ink">{{ cards.length }}</b> 套推荐
            <span class="text-line2">·</span>
            本地库存排序
            <span class="text-line2">·</span>
            通勤缓存优先
          </div>

          <template v-if="activeTab === 'recs'">
            <div v-if="loading && !cards.length" class="grid gap-4 lg:grid-cols-2">
              <div v-for="index in 2" :key="index" class="h-[360px] animate-pulse rounded-2xl border border-line bg-paper2" />
            </div>
            <div v-else-if="cards.length" class="grid gap-4 lg:grid-cols-2">
              <RecommendationCard
                v-for="(card, index) in cards"
                :key="card.id"
                :listing="card"
                :index="index"
                :selected="compareIds.has(card.id)"
                @open="openDetail"
                @compare="compare"
              />
            </div>
            <div v-else class="grid place-items-center rounded-2xl border border-dashed border-line2 bg-paper2 px-6 py-24 text-center">
              <MessageSquare :size="26" class="text-line2" />
              <p class="mt-3 text-[12.5px] text-muted">还没有候选，先发一句需求。</p>
            </div>
          </template>

          <ComparisonTable v-else-if="activeTab === 'compare'" :cards="comparison" @open="openDetail" />
          <MapPanel v-else />
        </div>
      </section>
    </main>

    <ConditionSheet :open="sheetOpen" :company="conditions.company" @close="store.closeSheet()" @apply="applyConditions" />
    <ListingDetailDrawer
      :listing="detail"
      :loading="detailLoading"
      @close="store.closeDetail()"
      @compare="compare"
      @save="save"
      @state="setDetailState"
      @inspection="saveDetailInspection"
      @refresh="store.refreshDetail()"
    />

    <WatchlistDrawer @open-detail="openDetailById" />

    <AppDrawer
      :open="historyOpen"
      title="历史需求"
      subtitle="后端会话 + 本地缓存"
      @close="store.closeHistory()"
    >
      <div v-if="!history.length" class="rounded-xl border border-dashed border-line2 bg-paper2 px-5 py-12 text-center text-[12px] text-faint">
        还没有历史需求。
      </div>
      <div v-else class="space-y-2">
        <button
          v-for="session in history"
          :key="session.id"
          class="w-full rounded-xl border border-line bg-paper2 px-3.5 py-3 text-left transition hover:border-forest/30 hover:bg-paper"
          @click="store.rerun(session)"
        >
          <div class="flex items-center gap-2">
            <span class="min-w-0 flex-1 truncate text-[12.5px] font-semibold text-ink">{{ session.title }}</span>
            <span class="mono shrink-0 text-[9px] text-faint">{{ formatDate(session.updatedAt) }}</span>
          </div>
          <div class="mt-1 line-clamp-2 text-[10.5px] leading-5 text-muted">{{ session.prompt }}</div>
        </button>
      </div>
    </AppDrawer>

    <AppDrawer
      :open="monitorsOpen"
      title="我的监控"
      subtitle="保存的条件 · 命中后飞书推送"
      @close="store.closeMonitors()"
    >
      <div v-if="!monitors.length" class="rounded-xl border border-dashed border-line2 bg-paper2 px-5 py-12 text-center text-[12px] text-faint">
        还没有保存的监控。完成一次分析后点“保存监控”。
      </div>
      <div v-else class="space-y-2">
        <div
          v-for="monitor in monitors"
          :key="monitor.id"
          class="rounded-xl border border-line bg-paper2 px-3.5 py-3"
        >
          <div class="flex items-start gap-2">
            <div class="min-w-0 flex-1">
              <div class="text-[12.5px] font-semibold text-ink">{{ monitor.name }}</div>
              <div class="mt-1.5 flex flex-wrap gap-1">
                <span class="tag-neutral">{{ monitor.conditions.budget }}</span>
                <span class="tag-neutral">{{ monitor.conditions.line }}</span>
                <span class="tag-neutral">通勤 {{ monitor.conditions.commute }}</span>
              </div>
            </div>
            <span :class="monitor.newMatches ? 'tag-green' : 'tag-neutral'">新 {{ monitor.newMatches }}</span>
            <button class="btn-ghost btn-sm" title="删除监控" @click="store.removeMonitor(monitor.id)">
              <Trash2 :size="13" />
            </button>
          </div>
        </div>
      </div>
    </AppDrawer>
  </div>
</template>
