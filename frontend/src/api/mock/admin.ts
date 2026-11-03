import type {
  AgentCostData,
  AgentEvalData,
  AgentEvalRun,
  AgentSession,
  Candidate,
  Community,
  ImagesData,
  OpsStatus,
  ReferenceRent,
  ReputationMention,
  ShareLink,
  SourceInfo,
  CityInfo,
  ReputationOverview,
  ReputationSummary,
  Run,
  Stats,
  Task,
} from '../types'
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
  alertPush: true,
  alertQueueBacklog: 100,
  alertQueuedMinutes: 30,
  alertDiskPct: 85,
  alertBackupHours: 26,
  alertCooldownMinutes: 30,
  alertIntervalMinutes: 10,
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
  async images() {
    await delay(120)
    return {
      stats: {
        candidates: 0,
        downloaded: 0,
        failed: 0,
        analyzed: 0,
        pending: 0,
        suspicious: 0,
        watch: 0,
        vision_pending: 0,
        vision_enabled: false,
        duplicate_distance: 10,
      },
      queue: { items: [] },
      duplicates: [],
      vision_enabled: false,
    } satisfies ImagesData
  },
  async analyzeImages(listingIds) {
    await delay(180)
    return {
      id: `J-${Date.now().toString().slice(-5)}`,
      type: 'image_analysis',
      status: 'queued',
      calls: Math.max(1, listingIds.length),
      createdAt: new Date().toISOString(),
    }
  },
  async reputation() {
    await delay(120)
    return {
      stats: {
        communities: 0,
        with_evidence: 0,
        without_evidence: 0,
        verified: 0,
        uncertain: 0,
        high_risk: 0,
        sources: 0,
      },
      risky: [],
      missing: [],
      recent: [],
      issue_types: {},
      sources: [],
      half_life_days: 180,
    } satisfies ReputationOverview
  },
  async reputationCommunities() {
    await delay(100)
    return []
  },
  async reputationCommunity(id) {
    await delay(100)
    const summary: ReputationSummary = {
      count: 0,
      uncertain: 0,
      score: 0.5,
      status: 'insufficient',
      label: '口碑数据不足（中性分）',
      risk: 'unknown',
      sources: [],
      issue_types: {},
    }
    return {
      community: { id, name: '演示小区', district: '福田区' },
      summary,
      mentions: [],
    }
  },
  async createReputationMention(payload) {
    await delay(160)
    return {
      id: Date.now(),
      source: payload.source,
      url: payload.url ?? null,
      title: payload.title ?? null,
      excerpt: payload.excerpt,
      issue_type: payload.issueType ?? null,
      severity: payload.severity,
      confidence: payload.confidence,
      match_status: payload.matchStatus,
      published_at: payload.publishedAt ?? null,
      created_at: new Date().toISOString(),
      expires_at: null,
    } satisfies ReputationMention
  },
  async updateReputationMention(id, matchStatus) {
    await delay(100)
    return {
      id,
      source: 'manual',
      url: null,
      title: null,
      excerpt: '演示证据',
      issue_type: 'other',
      severity: 'low',
      confidence: 0.5,
      match_status: matchStatus as ReputationMention['match_status'],
      published_at: null,
      created_at: new Date().toISOString(),
      expires_at: null,
    } satisfies ReputationMention
  },
  async deleteReputationMention() {
    await delay(80)
  },
  async extractReputation() {
    await delay(400)
    return { drafts: [], note: '演示模式不调用模型。' }
  },
  async agentEval() {
    await delay(120)
    return {
      dataset_version: '2026-11-04',
      dataset_cases: 60,
      latest: null,
      history: [],
    } satisfies AgentEvalData
  },
  async runAgentEval() {
    await delay(300)
    const metrics = {
      intent_case_accuracy: 1,
      intent_field_accuracy: 1,
      tool_accuracy: 1,
      arg_accuracy: 1,
      schema_valid_rate: 1,
      grounding_rate: 1,
      guardrail_accuracy: 1,
      overall_pass_rate: 1,
      query_cases: 48,
      guardrail_cases: 12,
    }
    return {
      id: Date.now(),
      version: '2026-11-04',
      mode: 'rules',
      total: 60,
      passed: 60,
      metrics,
      cases: [],
      duration_ms: 42,
      created_at: new Date().toISOString(),
    } satisfies AgentEvalRun
  },
  async agentCost() {
    await delay(120)
    return {
      days: 7,
      sessions: {
        total: 0,
        done: 0,
        blocked: 0,
        failed: 0,
        running: 0,
        fallback: 0,
        fallback_rate: 0,
        prompt_tokens: 0,
        completion_tokens: 0,
        cost: 0,
        avg_latency_ms: 0,
      },
      tools: { calls: 0, errors: 0, avg_latency_ms: 0, success_rate: null },
      guardrails: { injection_blocks: 0, pii_masked: 0, quota_blocked: 0 },
      provider: {
        code: 'modelscope_deepseek',
        model: 'DeepSeek-V4.1-Flash',
        used: 0,
        limit: 500,
        remaining: 500,
        calls: 0,
        errors: 0,
        avg_latency_ms: 0,
      },
      daily: [],
      total_sessions: 0,
    } satisfies AgentCostData
  },
  async opsStatus() {
    await delay(120)
    return mockOpsStatus
  },
  async runOpsCheck() {
    await delay(300)
    return { alerts: mockOpsStatus.alerts, delivered: { ok: true } }
  },
  async shareLinks() {
    await delay(80)
    return mockShareLinks
  },
  async createShareLink(label, expiresDays) {
    await delay(120)
    return {
      id: Date.now(),
      label,
      token_prefix: 'rr_share_abc123',
      scope: 'dashboard',
      created_at: new Date().toISOString(),
      expires_at: new Date(Date.now() + expiresDays * 86400000).toISOString(),
      revoked_at: null,
      last_used_at: null,
      use_count: 0,
      active: true,
      token: `rr_share_demo_${Date.now()}`,
    } satisfies ShareLink
  },
  async revokeShareLink(id) {
    await delay(80)
    return { ...mockShareLinks[0], id, revoked_at: new Date().toISOString(), active: false }
  },
  async sources() {
    await delay(80)
    return mockSources
  },
  async updateSource(code, enabled) {
    await delay(80)
    return { ...mockSources[0], code, enabled }
  },
  async cities() {
    await delay(80)
    return mockCities
  },
  async updateCity(code, enabled) {
    await delay(80)
    return { ...mockCities[0], code, enabled }
  },
  async createTask(payload) {
    await delay(120)
    return {
      id: Date.now(),
      name: String(payload.name ?? '新任务'),
      enabled: true,
      city_code: String(payload.cityCode ?? 'sz'),
      source_code: String(payload.sourceCode ?? 'beike'),
      filters: {},
      schedule: { fast_minutes: 10, slow_minutes: 180 },
    }
  },
  async updateTask(id, payload) {
    await delay(80)
    return { ...tasks[0], id, ...payload }
  },
  async disableTask(id) {
    await delay(80)
    return { ...tasks[0], id, enabled: false }
  },
  async referenceRents(city) {
    await delay(80)
    return mockReferenceRents.filter((item) => !city || city === 'sz')
  },
  async importReferenceRents(city, rows) {
    await delay(120)
    return { created: rows.length, updated: 0, total: rows.length }
  },
  async deleteReferenceRent() {
    await delay(80)
    return { ok: true }
  },
}

const mockOpsStatus: OpsStatus = {
  snapshot: {
    generated_at: new Date().toISOString(),
    db: 'ok',
    queued_jobs: 1,
    running_jobs: 0,
    oldest_queued_minutes: 2.4,
    failed_jobs_1h: 0,
    failing_tasks: [],
    providers: [
      { code: 'beike_api', status: 'ok', consecutive_failures: 0, circuit_open_until: null, last_error: null },
      { code: 'opencode_go_deepseek', status: 'ok', consecutive_failures: 0, circuit_open_until: null, last_error: null },
    ],
    disk: { path: '/', used_pct: 61.2, free_gb: 39.4 },
    backup: { configured: true, dir: '/home/kkk/backups/rentradar', latest_age_hours: 5.2, marker: { status: 'ok' } },
  },
  alerts: [],
  state: {},
  settings: { alertPush: true, alertIntervalMinutes: 10 },
}

const mockShareLinks: ShareLink[] = [
  {
    id: 1,
    label: '给朋友看的总览',
    token_prefix: 'rr_share_demo01',
    scope: 'dashboard',
    created_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 7 * 86400000).toISOString(),
    revoked_at: null,
    last_used_at: null,
    use_count: 0,
    active: true,
  },
]

const mockSources: SourceInfo[] = [
  { id: 1, code: 'beike', name: '贝壳租房', kind: 'api', enabled: true, rate_limit: {}, listings: 1395, tasks: 1, supported: true, reserved: false, note: '贝壳 App 列表 API' },
  { id: 2, code: 'manual', name: '手动导入（品牌公寓/线下房源）', kind: 'json', enabled: false, rate_limit: {}, listings: 0, tasks: 0, supported: true, reserved: false, note: '手动导入（品牌公寓/线下房源）' },
  { id: 3, code: 'ziroom', name: '自如（预留，未接入）', kind: 'html', enabled: false, rate_limit: {}, listings: 0, tasks: 0, supported: false, reserved: true, note: '自如（预留，未接入）' },
]

const mockCities: CityInfo[] = [
  { id: 1, code: 'sz', name: '深圳', domain_template: 'https://sz.zu.ke.com', center_lng: 114.057868, center_lat: 22.543099, enabled: true, listings: 1395, communities: 587, tasks: 2, active_listings: 1201, enabled_tasks: 1 },
  { id: 2, code: 'sh', name: '上海', domain_template: 'https://sh.zu.ke.com', center_lng: 121.473701, center_lat: 31.230416, enabled: false, listings: 0, communities: 0, tasks: 0, active_listings: 0, enabled_tasks: 0 },
]

const mockReferenceRents: ReferenceRent[] = [
  { id: 1, community_id: 1, community_name: '居里十舍', district: '龙岗区', layout: '2室', monthly_rent: 4600, reference_month: '2026-10', source: 'housing_bureau', url: null, confidence: 0.8, updated_at: new Date().toISOString() },
]
