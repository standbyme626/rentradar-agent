import type { Listing } from '../types'
import type {
  AgentEvent,
  AgentRequest,
  AgentService,
  ChatSession,
  PlanStep,
  SavedMonitor,
} from '../contracts'
import { conditionsFor, detectLong } from '@/lib/conditions'
import { delay, mockData } from './data'

const byName = (name: string): Listing | undefined =>
  mockData.listings.find((item) => item.community_name === name)

const CANDS: Listing[] = [byName('海鹰大厦'), byName('龙园创展大厦'), byName('罗湖大厦')].filter(
  Boolean,
) as Listing[]

const LONG: Listing[] = [
  {
    id: -1,
    title: '整租·中兆花园 2室2厅 南',
    community_name: '中兆花园',
    district: '龙岗区',
    layout: '2室2厅1卫',
    area: 65,
    rent: 3200,
    score: 77,
    status: 'active',
    url: '',
    image_url: null,
    tags: ['精装', '南向', '中楼层'],
    agent_type: 'unknown',
    commute_min: 60,
    samples: 1,
    dining_count: 42,
    daily_count: 18,
    nightlife_count: 3,
    score_reasons: {
      price: '比同区同户型中位价低 19%（中位 ¥3950）',
      condition: '精装 / 南向 / 中楼层 / 65㎡',
      commute: '公共交通 60 分钟（含地铁，单次采样）',
      convenience: '1km 餐饮 42 家 / 便利店超市菜场 18 家（高德）',
      freshness: '上架 1.2 天',
      reputation: '暂无口碑数据',
      risk: [],
    },
  },
  {
    id: -2,
    title: '整租·珑城原点广场 1室1厅 南',
    community_name: '珑城原点广场',
    district: '龙岗区',
    layout: '1室1厅1卫',
    area: 33.63,
    rent: 2100,
    score: 77,
    status: 'active',
    url: '',
    image_url: null,
    tags: ['精装', '南向', '高楼层'],
    agent_type: 'unknown',
    commute_min: 92,
    samples: 1,
    dining_count: 42,
    daily_count: 18,
    nightlife_count: 2,
    score_reasons: {
      price: '比同区同户型中位价低 25%（中位 ¥2800）',
      condition: '精装 / 南向 / 高楼层 / 34㎡',
      commute: '公共交通 92 分钟（含地铁，单次采样）',
      convenience: '1km 餐饮 42 家 / 便利店超市菜场 18 家（高德）',
      freshness: '上架 0.8 天',
      reputation: '暂无口碑数据',
      risk: [],
    },
  },
  {
    id: -3,
    title: '整租·和昌拾里花都 1室0厅 东南',
    community_name: '和昌拾里花都',
    district: '龙岗区',
    layout: '1室0厅1卫',
    area: 34,
    rent: 1500,
    score: 76,
    status: 'active',
    url: '',
    image_url: null,
    tags: ['精装', '东南向'],
    agent_type: 'unknown',
    commute_min: 88,
    samples: 1,
    dining_count: 36,
    daily_count: 15,
    nightlife_count: 1,
    score_reasons: {
      price: '比同区同户型中位价低 45%（中位 ¥2715）',
      condition: '精装 / 东南向 / 34㎡',
      commute: '公共交通 88 分钟（含地铁，单次采样）',
      convenience: '1km 餐饮 36 家 / 便利店超市菜场 15 家（高德）',
      freshness: '上架 1.5 天',
      reputation: '暂无口碑数据',
      risk: [],
    },
  },
]

export function cardsFor(prompt: string): Listing[] {
  return detectLong(prompt) ? LONG : CANDS
}

function stepsFor(long: boolean): PlanStep[] {
  return long
    ? [
        { id: 'parse', label: '解析需求', desc: '龙岗 · 3000 · 两居', status: 'done' },
        { id: 'search', label: '本地检索', desc: '90 套龙岗段', status: 'done' },
        { id: 'filter', label: '硬过滤', desc: '14 → 6 套', status: 'done' },
        { id: 'commute', label: '算通勤', desc: '3 套 · 缓存优先', status: 'now' },
        { id: 'detail', label: '抓详情', desc: '候选 only', status: 'pending' },
        { id: 'answer', label: '推荐', desc: '远但便宜', status: 'pending' },
      ]
    : [
        { id: 'parse', label: '解析需求', desc: '5 号线 · ≤4500 · ≤40min', status: 'done' },
        { id: 'search', label: '本地检索', desc: '900 套 5 号线', status: 'done' },
        { id: 'filter', label: '硬过滤', desc: '672 → 18 套', status: 'done' },
        { id: 'commute', label: '算通勤', desc: '6 套 · 缓存 2', status: 'now' },
        { id: 'detail', label: '抓详情', desc: '3 套 · 3–6 图', status: 'pending' },
        { id: 'answer', label: '推荐', desc: '3 套 · 理由 + 取舍', status: 'pending' },
      ]
}

function answerFor(long: boolean): string {
  return long
    ? '龙岗方向这 3 套是“远但便宜”：中兆花园 60 分钟 / ¥3,200，珑城原点 92 分钟 / ¥2,100，和昌拾里 88 分钟 / ¥1,500。如果更看重通勤，可以切回罗湖/福田方向。'
    : '结果出来了：海鹰大厦 16 分钟 / ¥1,900，通勤和租金都占优；龙园创展 29 分钟 / ¥3,500，比较均衡；罗湖大厦 34 分钟 / ¥4,500，两居，预算顶格。右侧可以直接对比。'
}

async function* initialStream(request: AgentRequest): AsyncGenerator<AgentEvent> {
  const long = detectLong(request.message)
  const sessionId = `S-${Date.now().toString().slice(-6)}`
  yield { type: 'session', sessionId, title: request.message.slice(0, 24) }
  yield { type: 'plan', steps: stepsFor(long) }
  await delay(520)
  yield { type: 'step', id: 'commute', status: 'done', desc: long ? '3 套 · 缓存 0' : '6 套 · 缓存 2' }
  yield { type: 'budget', amap: long ? 3 : 6 }
  await delay(520)
  yield { type: 'step', id: 'detail', status: 'done', desc: '候选 only' }
  await delay(380)
  yield { type: 'step', id: 'answer', status: 'done' }
  yield { type: 'cards', cards: cardsFor(request.message), longgang: long }
  yield { type: 'message', text: answerFor(long) }
  yield { type: 'done' }
}

async function* followUpStream(request: AgentRequest): AsyncGenerator<AgentEvent> {
  const lower = request.message.toLowerCase()
  await delay(420)
  if (lower.includes('对比')) {
    yield { type: 'tab', tab: 'compare' }
    yield { type: 'message', text: '已经切到对比视图。当前候选的差异主要在通勤、租金和面积；如果两个人住，优先看两居。' }
  } else if (lower.includes('图片') || lower.includes('看图') || lower.includes('ai')) {
    yield {
      type: 'ai',
      text: '图片分析是下一步：只对候选详情页抓 3–6 张图，做 pHash 和视觉标签。当前版本还没接入，这是设计占位。',
    }
  } else if (lower.includes('4000') || lower.includes('便宜') || lower.includes('预算')) {
    const cards = cardsFor('5号线').filter((item) => (item.rent ?? 0) <= 4000)
    yield { type: 'cards', cards, longgang: false }
    yield { type: 'message', text: `已把预算压到 4000，保留 ${cards.length} 套；这次只重排，不重新调高德。` }
  } else if (lower.includes('通勤') || lower.includes('近')) {
    const cards = [...cardsFor('5号线')].sort((a, b) => (a.commute_min ?? 999) - (b.commute_min ?? 999))
    yield { type: 'cards', cards, longgang: false }
    yield { type: 'message', text: '按通勤从短到长重排。通勤为单次采样，p50/p90 需要多时段样本，当前还没跑。' }
  } else if (lower.includes('保存') || lower.includes('监控')) {
    yield { type: 'toast', message: '已保存监控条件：5 号线 · ≤4500 · 通勤 ≤40 分钟' }
    yield { type: 'message', text: '已保存为监控条件。有新房价或降价，会推飞书。' }
  } else {
    yield { type: 'message', text: '收到。我先复用已有结果，不重复调接口；右侧按你的补充重新排序。' }
  }
  yield { type: 'done' }
}

const demoMonitors: SavedMonitor[] = [
  {
    id: 'M-1',
    name: '5 号线 · ≤4500 · 通勤≤40',
    conditions: conditionsFor('5号线'),
    createdAt: '2026-10-29T17:10:00+08:00',
    newMatches: 2,
  },
  {
    id: 'M-2',
    name: '龙岗 · 3000 · 两居',
    conditions: conditionsFor('龙岗 3000'),
    createdAt: '2026-10-29T16:40:00+08:00',
    newMatches: 0,
  },
]

const demoHistory: ChatSession[] = [
  {
    id: 'S-1042',
    title: '会展中心 · 4000 · 5号线 · 40min',
    prompt: '公司在会展中心，预算 4000，想住 5 号线沿线，通勤 40 分钟内，最好有电梯',
    updatedAt: '2026-10-29T17:12:00+08:00',
  },
  {
    id: 'S-1041',
    title: '两个人住 · 两居 · 4500',
    prompt: '两个人住，想要两居，预算 4500，5 号线沿线，通勤 45 分钟内',
    updatedAt: '2026-10-29T16:40:00+08:00',
  },
  {
    id: 'S-1040',
    title: '龙岗 · 3000 · 接受 60min',
    prompt: '预算 3000，龙岗方向，接受 60 分钟通勤，两居优先',
    updatedAt: '2026-10-29T16:20:00+08:00',
  },
]

export const mockAgentService: AgentService = {
  async *stream(request) {
    if (request.sessionId) {
      yield* followUpStream(request)
    } else {
      yield* initialStream(request)
    }
  },
  async stats() {
    await delay(60)
    return {
      listings: mockData.stats.listings,
      active: mockData.stats.listings,
      scored: mockData.stats.scored,
    }
  },
  async listSessions() {
    await delay(120)
    return demoHistory
  },
  async listMonitors() {
    await delay(120)
    return demoMonitors
  },
  async saveMonitor(input) {
    await delay(180)
    return {
      ...input,
      id: `M-${Date.now().toString().slice(-5)}`,
      createdAt: new Date().toISOString(),
      newMatches: 0,
    }
  },
  async removeMonitor() {
    await delay(80)
  },
}
