import type { AgentSession, Candidate, Community, Listing, Run, Stats, Task } from './types'

export type PlanStatus = 'done' | 'now' | 'pending' | 'failed'

export interface PlanStep {
  id: string
  label: string
  desc: string
  status: PlanStatus
}

export interface Conditions {
  company: string
  budget: string
  line: string
  commute: string
  layout: string
  district?: string
  must: string
  isLong: boolean
}

export type AgentTab = 'recs' | 'compare' | 'map'

export type AgentEvent =
  | { type: 'session'; sessionId: string; title: string }
  | { type: 'plan'; steps: PlanStep[] }
  | { type: 'step'; id: string; status: PlanStatus; desc?: string }
  | { type: 'message'; text: string }
  | { type: 'conditions'; conditions: Conditions }
  | { type: 'cards'; cards: Listing[]; longgang: boolean }
  | { type: 'budget'; amap: number; cap?: number }
  | { type: 'tab'; tab: AgentTab }
  | { type: 'ai'; text: string }
  | { type: 'toast'; message: string }
  | { type: 'done' }
  | { type: 'error'; message: string }

export interface ChatMessage {
  id: number
  role: 'user' | 'agent'
  kind: 'text' | 'plan' | 'ai'
  text?: string
  steps?: PlanStep[]
}

export interface ChatSession {
  id: string
  title: string
  prompt: string
  updatedAt: string
}

export interface SavedMonitor {
  id: string
  name: string
  conditions: Conditions
  createdAt: string
  newMatches: number
}

export interface AgentRequest {
  sessionId?: string
  message: string
}

export interface AgentTraceTool {
  name: string
  args: string
  latency: string
  result: string
}

export interface AgentTrace {
  sessionId: string
  query: string
  stage: string
  plan: PlanStep[]
  tools: AgentTraceTool[]
  llm: string
  guardrails: string
  result: string
}

export interface AgentService {
  stream(request: AgentRequest): AsyncGenerator<AgentEvent>
  stats(): Promise<{ listings: number; active: number; scored: number }>
  listSessions(): Promise<ChatSession[]>
  listMonitors(): Promise<SavedMonitor[]>
  saveMonitor(input: Omit<SavedMonitor, 'id' | 'createdAt' | 'newMatches'>): Promise<SavedMonitor>
  removeMonitor(id: string): Promise<void>
}

export interface FunnelStep {
  value: number
  label: string
  drop?: string
}

export interface QualityItem {
  label: string
  desc: string
  tone: 'green' | 'amber' | 'coral'
  badge: string
}

export interface NextStep {
  title: string
  desc: string
}

export interface AdminOverview {
  stats: Stats
  funnel: FunnelStep[]
  quality: QualityItem[]
  runs: Run[]
  nextSteps: NextStep[]
}

export interface CoverageData {
  stats: Stats
  communities: Community[]
  priority: Community[]
}

export interface QualityData {
  stats: Stats
  geoPriority: Community[]
  poiCapped: Community[]
}

export interface AgentSessionSummary {
  id: string
  query: string
  stage: string
  cand: string
  tools: number | string
  amap: number | string
  latency: string
  status: 'done' | 'running' | 'blocked' | 'failed'
}

export interface AdminSettings {
  amapMonthlyCap: number
  sessionAmapCap: number
  batchCap: number
  aiDailyCap: number
  notifyBatchCap: number
  notifyScoreMin: number
  priceDropPct: number
  quietStart: string
  quietEnd: string
  feishu: boolean
  digest: boolean
  quiet: boolean
  pauseAlert: boolean
  monitorPush: boolean
}

export interface AuthUser {
  id: number
  username: string
  role: 'admin' | 'viewer'
  isActive: boolean
  lastLoginAt: string | null
}

export interface AuthService {
  login(username: string, password: string): Promise<AuthUser>
  logout(): Promise<void>
  me(): Promise<AuthUser>
  changePassword(oldPassword: string, newPassword: string): Promise<{ ok: boolean; reLogin: boolean }>
}

export interface AuditLogEntry {
  id: number
  username: string | null
  action: string
  target: string | null
  detail: Record<string, unknown>
  ip: string | null
  createdAt: string
}

export interface Job {
  id: string
  type: 'analysis' | 'sampling' | 'geocode' | 'task'
  status: 'queued' | 'running' | 'done' | 'failed'
  calls?: number
  createdAt: string
}

export interface SamplingRequest {
  origin: string
  count: number
  buckets: string[]
  modes: string[]
}

export interface CrawlCoverageShard {
  condition: string
  station: string
  scope: string
  listings: number
  complete: boolean
  last_run: {
    id: number | null
    status: string | null
    started_at: string | null
    finished_at: string | null
    pages: number | null
    fetched: number | null
    total: number | null
    duplicates: number | null
    suspect_skipped: boolean
  } | null
}

export interface CrawlCoverage {
  task_id: number | null
  task_name: string | null
  line: string | null
  shard_cursor: number
  shards: CrawlCoverageShard[]
  summary: {
    shards: number
    listings: number
    complete: number
    scanned: number
    last_scan_at: string | null
  }
}

export interface AdminService {
  overview(): Promise<AdminOverview>
  candidates(): Promise<Candidate[]>
  coverage(): Promise<CoverageData>
  crawlCoverage(taskId?: number): Promise<CrawlCoverage>
  quality(): Promise<QualityData>
  agentSessions(): Promise<AgentSession[]>
  runs(): Promise<Run[]>
  tasks(): Promise<Task[]>
  runTask(taskId: number): Promise<{ ok: boolean; job_id: number }>
  settings(): Promise<AdminSettings>
  updateSettings(patch: Partial<AdminSettings>): Promise<AdminSettings>
  enqueueAnalysis(listingIds: number[]): Promise<Job>
  startSampling(request: SamplingRequest): Promise<Job>
  enqueueGeocode(communityIds: number[]): Promise<Job>
  annotateSession(sessionId: string, label: string): Promise<void>
  auditLogs(limit?: number): Promise<AuditLogEntry[]>
}

export type ProviderDomain =
  | 'housing'
  | 'maps'
  | 'transit'
  | 'opendata'
  | 'reputation'
  | 'ai'
  | 'notify'

export interface ProviderQuota {
  period: string
  limit: number
  used: number
  remaining: number | null
  unit: string
}

export interface ProviderHealth {
  status: string
  consecutive_failures: number
  circuit_open_until: string | null
  last_ok_at: string | null
  last_error: string | null
}

export interface ProviderCall {
  id: number
  provider: string
  capability: string
  status: string
  latency_ms: number | null
  quota_units: number
  cached: boolean
  error_code: string | null
  error_message: string | null
  created_at: string
}

export interface ProviderInfo {
  code: string
  name: string
  domain: ProviderDomain
  capabilities: string[]
  auth: string
  coord_system: string
  description: string
  docs_url: string
  proxy: string | null
  priority: number
  enabled: boolean
  configured: boolean
  implemented: boolean
  quota: ProviderQuota
  health: ProviderHealth
  last_call: ProviderCall | null
  test_note: string | null
}

export interface ProviderTestResult {
  provider: string
  ok: boolean
  message: string
  latency_ms: number
  quota_units: number
  health: ProviderHealth
}

export interface ProviderUsage {
  provider: string
  period: string
  used: number
  limit: number
  updated_at: string
}

export interface ProviderPatch {
  enabled?: boolean
  priority?: number
}

export interface ProviderService {
  list(domain?: string): Promise<ProviderInfo[]>
  test(code: string): Promise<ProviderTestResult>
  calls(provider?: string, limit?: number): Promise<ProviderCall[]>
  usage(code: string): Promise<ProviderUsage[]>
  update(code: string, patch: ProviderPatch): Promise<ProviderInfo>
}
