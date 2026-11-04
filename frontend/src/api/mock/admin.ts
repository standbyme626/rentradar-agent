import type { AgentSession, Candidate, Community, Run, Stats, Task } from '../types'
import type {
  AdminOverview,
  AdminService,
  AdminSettings,
  AuditLogEntry,
  CoverageData,
  CrawlCoverage,
  QualityData,
} from '../contracts'
import { delay, mockData } from './data'

export const stats: Stats = mockData.stats
export const listings = mockData.listings
export const candidates: Candidate[] = mockData.candidates
export const communities: Community[] = mockData.communities
export const runs: Run[] = mockData.runs
export const tasks: Task[] = mockData.tasks

export const money = (value: number | null | undefined) =>
  value == null ? '—' : `¥${value.toLocaleString('zh-CN')}`

export const formatTime = (value: string) =>
  new Date(value).toLocaleString('zh-CN', {
    hour12: false,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })

export const agentSessions: AgentSession[] = [
  {
    id: 'S-1042',
    query: '会展中心 · 4000 · 5号线 · 40min',
    stage: '已推荐',
    cand: '18 → 6 → 3',
    tools: 9,
    amap: 7,
    latency: '8.1s',
    status: 'done',
    plan: [
      ['解析需求', 'line=5 · 预算≤4500 · 通勤≤40 · 电梯', 'done', '120ms'],
      ['本地检索', '900 → 672 → 18', 'done', '12ms'],
      ['算通勤', '6 套 · 缓存命中 2', 'done', '4.1s'],
      ['抓详情', '3 套 · 3–6 图', 'done', '5.2s'],
      ['推荐', '3 套 · 理由 + 取舍', 'done', '200ms'],
    ],
    toolsList: [
      ['search_listings', 'line=5 · rent≤4500 · elevator=true', '12ms', 'local · 18'],
      ['commute', '海鹰大厦 · 08:00 · transit', '420ms', '1 次 · 16min'],
      ['commute', '龙园创展 · 08:00 · transit', '390ms', '缓存 · 29min'],
      ['poi', '海鹰大厦 · 1km', '180ms', '缓存 · 600/252'],
      ['fetch_detail', '海鹰大厦 · 3 图', '1.8s', '0 高德'],
      ['analyze_images', '海鹰大厦 · 5 标签', '1.2s', '0 高德 · 魔搭'],
      ['save_monitor', '5号线 · ≤4500 · ≤40', '30ms', '飞书'],
    ],
    result: '推荐 3 套；用户打开详情 2 次、对比 1 次，未保存监控。',
  },
  {
    id: 'S-1041',
    query: '两个人住 · 两居 · 4500',
    stage: '已保存监控',
    cand: '20 → 8 → 3',
    tools: 11,
    amap: 8,
    latency: '9.4s',
    status: 'done',
    plan: [
      ['解析需求', '两居 · 预算≤4500 · 5号线', 'done', '130ms'],
      ['本地检索', '900 → 672 → 20', 'done', '14ms'],
      ['算通勤', '8 套 · 缓存 3', 'done', '4.8s'],
      ['抓详情', '3 套', 'done', '3.9s'],
      ['推荐 + 保存监控', '3 套', 'done', '260ms'],
    ],
    toolsList: [
      ['search_listings', 'layout=2室 · rent≤4500', '14ms', 'local · 20'],
      ['commute', '8 套 · transit', '4.8s', '8 次 · 3 缓存'],
      ['fetch_detail', '3 套 · 4 图', '3.9s', '0 高德'],
      ['save_monitor', '两居 · 5号线 · ≤4500', '40ms', '飞书'],
    ],
    result: '推荐 3 套；保存监控 1 个；用户打开详情 2 次。',
  },
  {
    id: 'S-1040',
    query: '龙岗 · 3000 · 接受 60min',
    stage: '已推荐',
    cand: '14 → 6 → 3',
    tools: 7,
    amap: 6,
    latency: '7.2s',
    status: 'done',
    plan: [
      ['解析需求', '龙岗 · 预算≤3000 · 通勤≤90', 'done', '100ms'],
      ['本地检索', '90 → 14 → 6', 'done', '9ms'],
      ['算通勤', '3 套', 'done', '2.9s'],
      ['推荐', '3 套 · 远但便宜', 'done', '180ms'],
    ],
    toolsList: [
      ['search_listings', 'district=龙岗 · rent≤3000', '9ms', 'local · 6'],
      ['commute', '中兆花园', '380ms', '1 次 · 60min'],
      ['commute', '珑城原点', '390ms', '1 次 · 92min'],
      ['commute', '和昌拾里', '370ms', '1 次 · 88min'],
    ],
    result: '推荐 3 套“远但便宜”；用户打开详情 1 次。',
  },
  {
    id: 'S-1039',
    query: '预算 2000 · 福田',
    stage: '本地无匹配 · 预算拦截',
    cand: '0',
    tools: 1,
    amap: 0,
    latency: '1.1s',
    status: 'blocked',
    plan: [
      ['解析需求', '预算≤2000 · 福田 · 通勤≤30', 'done', '90ms'],
      ['本地检索', '0 匹配', 'done', '8ms'],
      ['护栏', '拒绝外部调用，建议放宽条件', 'done', '0ms'],
    ],
    toolsList: [
      ['search_listings', 'rent≤2000 · district=福田', '8ms', 'local · 0'],
      ['guardrail', 'no_external_calls', '0ms', 'blocked'],
    ],
    result: '回复“本地无匹配”，未调用高德；引导放宽预算或区域。',
  },
  {
    id: 'S-1038',
    query: '看图片分析 · 5号线',
    stage: '图片工具未接入',
    cand: '18 → 3',
    tools: 3,
    amap: 0,
    latency: '3.4s',
    status: 'failed',
    plan: [
      ['解析需求', '图片分析 · 5号线', 'done', '100ms'],
      ['本地检索', '18 套', 'done', '10ms'],
      ['抓详情', '3 套', 'done', '3.2s'],
      ['图片分析', '工具未接入', 'failed', '—'],
    ],
    toolsList: [
      ['search_listings', 'line=5', '10ms', 'local · 18'],
      ['fetch_detail', '3 套 · 3 图', '3.2s', '0 高德'],
      ['analyze_images', '—', '—', 'tool unavailable'],
    ],
    result: '会话中止；没有产生高德调用；返回“图片管线未接入”。',
  },
  {
    id: 'S-1037',
    query: '会展中心 · 通勤 30min',
    stage: '运行中 · 算通勤',
    cand: '22 → 6',
    tools: '6/12',
    amap: '4/8',
    latency: '4.2s',
    status: 'running',
    plan: [
      ['解析需求', '会展中心 · 通勤≤30', 'done', '110ms'],
      ['本地检索', '22 → 6', 'done', '11ms'],
      ['算通勤', '4 / 8', 'now', 'running'],
      ['抓详情', '待开始', 'pending', '—'],
      ['推荐', '待开始', 'pending', '—'],
    ],
    toolsList: [
      ['search_listings', 'line=5 · commute≤30', '11ms', 'local · 6'],
      ['commute', '海鹰大厦', '420ms', '1 次 · 16min'],
      ['commute', '龙园创展', '390ms', '缓存 · 29min'],
      ['commute', '罗湖大厦', '—', 'running'],
    ],
    result: '运行中；已用高德 4 次，剩余 11 次。',
  },
]

const noGeo = stats.communities - stats.geocoded
const scoredGeo = stats.scored - stats.listings_no_geo

export const mockOverview: AdminOverview = {
  stats,
  funnel: [
    { value: stats.line5, label: '5 号线' },
    { value: stats.scored, label: '已评分', drop: '-228 硬过滤' },
    { value: scoredGeo, label: '有坐标', drop: `-${stats.listings_no_geo} 缺坐标` },
    { value: scoredGeo, label: '有通勤' },
    { value: 0, label: '有图片/AI', drop: '未接入' },
  ],
  quality: [
    { label: '缺坐标', desc: `${noGeo} 个小区 · ${stats.listings_no_geo} 套房受影响`, tone: 'coral', badge: '高优先' },
    { label: 'POI 封顶', desc: `${stats.poi_capped} 个小区餐饮 count ≥ 600，密度区分度不足`, tone: 'amber', badge: '中' },
    { label: '详情图', desc: '0 / 900 套有详情图，AI 无法运行', tone: 'coral', badge: '未接入' },
    { label: '外卖样本', desc: `${stats.probes} 条，全是夜宵；缺午餐/晚餐`, tone: 'amber', badge: '部分' },
    { label: '价格快照', desc: `${stats.listings} 套在库，快照持续积累`, tone: 'green', badge: '正常' },
  ],
  runs,
  nextSteps: [
    { title: '过验证码，恢复采集', desc: '成本 0；在 Windows Chrome 手动通过后，启用任务 1 并启动 worker/scheduler。' },
    { title: '优先补 5 个高房源量小区的坐标', desc: '约 25–30 次高德调用；能覆盖最多房源的兜底通勤。' },
    { title: '只对 Top 10 候选跑 p50/p90', desc: '10 小区 × 4 时段 × 10 个工作日 ≈ 400 次；先跑 2 个时段可减半。' },
    { title: '接入候选详情图 + pHash + Qwen-VL', desc: '不占高德；只对候选 3–6 张图，先做 Top 5。' },
  ],
}

export const mockCoverage: CoverageData = {
  stats,
  communities,
  priority: [...communities].filter((item) => item.lng == null).sort((a, b) => b.listings - a.listings).slice(0, 5),
}

export const mockQuality: QualityData = {
  stats,
  geoPriority: [...communities].filter((item) => item.lng == null).sort((a, b) => b.listings - a.listings).slice(0, 10),
  poiCapped: [...communities].filter((item) => (item.dining_count ?? 0) >= 600).slice(0, 10),
}

const defaultSettings: AdminSettings = {
  amapMonthlyCap: 5000,
  sessionAmapCap: 15,
  batchCap: 10,
  aiDailyCap: 500,
  notifyBatchCap: 10,
  notifyScoreMin: 75,
  priceDropPct: 8,
  quietStart: '23:00',
  quietEnd: '08:00',
  feishu: true,
  digest: true,
  quiet: true,
  pauseAlert: true,
  monitorPush: true,
}

const demoAudit: AuditLogEntry[] = [
  {
    id: 1,
    username: 'admin',
    action: 'auth.login',
    target: 'admin',
    detail: { role: 'admin' },
    ip: '192.168.31.10',
    createdAt: new Date().toISOString(),
  },
]

let currentSettings = { ...defaultSettings }

const mockCrawlCoverage: CrawlCoverage = {
  task_id: 1,
  task_name: '贝壳 5 号线',
  line: 'li110460696',
  shard_cursor: 3,
  shards: [
    {
      condition: 'li110460696s100021264',
      station: '赤湾',
      scope: 'line:li110460696s100021264',
      listings: 28,
      complete: true,
      last_run: {
        id: 31,
        status: 'done',
        started_at: '2026-11-04T01:00:00+08:00',
        finished_at: '2026-11-04T01:00:40+08:00',
        pages: 1,
        fetched: 28,
        total: 28,
        duplicates: 0,
        suspect_skipped: false,
      },
    },
    {
      condition: 'li110460696s24000001333516',
      station: '荔湾',
      scope: 'line:li110460696s24000001333516',
      listings: 116,
      complete: true,
      last_run: {
        id: 30,
        status: 'done',
        started_at: '2026-11-04T00:50:00+08:00',
        finished_at: '2026-11-04T00:52:00+08:00',
        pages: 4,
        fetched: 116,
        total: 116,
        duplicates: 2,
        suspect_skipped: false,
      },
    },
    {
      condition: 'li110460696s24000001333677',
      station: '铁路公园',
      scope: 'line:li110460696s24000001333677',
      listings: 50,
      complete: false,
      last_run: {
        id: 29,
        status: 'done',
        started_at: '2026-11-04T00:40:00+08:00',
        finished_at: '2026-11-04T00:41:00+08:00',
        pages: 1,
        fetched: 30,
        total: 50,
        duplicates: 4,
        suspect_skipped: true,
      },
    },
  ],
  summary: {
    shards: 3,
    listings: 194,
    complete: 2,
    scanned: 3,
    last_scan_at: '2026-11-04T01:00:00+08:00',
  },
}

export const mockAdminService: AdminService = {
  async overview() {
    await delay(160)
    return mockOverview
  },
  async candidates() {
    await delay(160)
    return candidates
  },
  async coverage() {
    await delay(160)
    return mockCoverage
  },
  async crawlCoverage() {
    await delay(120)
    return mockCrawlCoverage
  },
  async quality() {
    await delay(160)
    return mockQuality
  },
  async agentSessions() {
    await delay(140)
    return agentSessions
  },
  async runs() {
    await delay(120)
    return runs
  },
  async tasks() {
    await delay(120)
    return tasks
  },
  async runTask(_taskId: number) {
    await delay(180)
    return { ok: true, job_id: Date.now() }
  },
  async settings() {
    await delay(100)
    return { ...currentSettings }
  },
  async updateSettings(patch) {
    await delay(180)
    currentSettings = { ...currentSettings, ...patch }
    return { ...currentSettings }
  },
  async enqueueAnalysis(listingIds) {
    await delay(220)
    return {
      id: `J-${Date.now().toString().slice(-5)}`,
      type: 'analysis',
      status: 'queued',
      calls: listingIds.length,
      createdAt: new Date().toISOString(),
    }
  },
  async startSampling(request) {
    await delay(220)
    return {
      id: `J-${Date.now().toString().slice(-5)}`,
      type: 'sampling',
      status: 'queued',
      calls: request.count * request.buckets.length * request.modes.length,
      createdAt: new Date().toISOString(),
    }
  },
  async enqueueGeocode(communityIds) {
    await delay(200)
    return {
      id: `J-${Date.now().toString().slice(-5)}`,
      type: 'geocode',
      status: 'queued',
      calls: communityIds.length * 6,
      createdAt: new Date().toISOString(),
    }
  },
  async annotateSession() {
    await delay(160)
  },
  async auditLogs() {
    await delay(100)
    return demoAudit
  },
}
