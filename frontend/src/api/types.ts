export interface ScoreReasons {
  price?: string
  commute?: string
  condition?: string
  convenience?: string
  freshness?: string
  reputation?: string
  risk?: string[]
  [key: string]: unknown
}

export interface Listing {
  id: number
  title: string
  community_name: string
  district: string | null
  layout: string | null
  area: number | null
  rent: number | null
  score: number | null
  score_reasons: ScoreReasons
  image_url: string | null
  tags: string[]
  agent_type: string | null
  status: string
  url: string
  first_seen_at?: string
  commute_min?: number | null
  samples?: number
  dining_count?: number | null
  daily_count?: number | null
  nightlife_count?: number | null
}

export interface Candidate extends Listing {
  has_geo: boolean
  has_commute: boolean
  commute_p50?: number | null
  commute_p90?: number | null
  commute_buckets?: number
  commute_static?: boolean | null
}

export interface CommuteStats {
  samples: number
  buckets: string[]
  bucket_count: number
  multi_bucket: boolean
  p50_min: number | null
  p90_min: number | null
  static: boolean
  provider: string | null
  mode: string | null
  direction: string
  direction_label: string
  transfers: number | null
  walk_min: number | null
  fetched_at: string | null
  destination: string | null
  example: boolean
}

export interface Inspection {
  items: Record<string, boolean>
  note: string | null
  photos: string[]
  updated_at: string | null
}

export interface Snapshot {
  rent: number
  seen_at: string
  image_hash?: string | null
}

export interface DeliveryProbe {
  id: number
  platform: string
  probe_at: string
  meal_period: string | null
  address_label: string | null
  eta_min_low: number | null
  eta_min_high: number | null
  fee: number | null
  merchant_count: number | null
  confidence: number | null
}

export interface ListingDetail extends Listing {
  source_code: string
  city_code: string
  source_listing_id: string
  orientation: string | null
  floor: string | null
  last_seen_at?: string
  snapshots: Snapshot[]
  events: Array<Record<string, unknown>>
  delivery_probes: DeliveryProbe[]
  watch_state: string | null
  watch_note: string | null
  watch_updated_at: string | null
  inspection: Inspection
  commute_stats: CommuteStats | null
  reputation?: (ReputationSummary & { mentions?: ReputationMention[] }) | null
  image_analysis?: ImageAnalysis | null
}

export interface WatchlistEntry {
  listing: Listing
  state: string
  note: string | null
  updated_at: string | null
  inspection: Inspection
}

export interface Community {
  id: number
  name: string
  district: string | null
  lng: number | null
  lat: number | null
  listings: number
  dining_count: number | null
  daily_count: number | null
  nightlife_count: number | null
  commute_min: number | null
  commute_p50?: number | null
  commute_p90?: number | null
  commute_buckets?: number
  commute_static?: boolean | null
  samples: number
}

export interface Run {
  id: number
  status: string
  stats: Record<string, number | string | boolean | null>
  error: string | null
  started_at: string
  finished_at: string | null
}

export interface Task {
  id: number
  name: string
  enabled: boolean
  city_code?: string
  source_code?: string
  filters: Record<string, unknown>
  schedule: Record<string, number>
  last_run_status?: string | null
  last_run_at?: string | null
}

export interface Stats {
  listings: number
  line5: number
  scored: number
  ge75: number
  avg_score: number
  median_score: number
  max_score: number
  communities: number
  geocoded: number
  commute_samples: number
  commute_communities: number
  poi_cache: number
  probes: number
  listings_no_geo: number
  listings_no_commute: number
  poi_capped: number
  no_commute_but_geo: number
  scored_geo?: number
  scored_commute?: number
  commute_p50_communities?: number
  commute_multi_bucket?: number
  amap_used?: number
  amap_limit?: number
}

export interface MockData {
  stats: Stats
  listings: Listing[]
  candidates: Candidate[]
  communities: Community[]
  runs: Run[]
  tasks: Task[]
}

export interface AgentToolCall {
  step: number
  tool: string
  args: Record<string, unknown>
  status: string
  latency: string
  summary: string
  error: string | null
}

export interface AgentGuardrail {
  stage: string
  summary?: string
  flags?: string[]
  pii_hits?: number
  injections?: string[]
  blocked?: string
  used?: number | null
  limit?: number | null
  remaining?: number | null
  calls?: number
}

export interface AgentSession {
  id: string
  query: string
  stage: string
  cand: string
  tools: number | string
  amap: number | string
  latency: string
  status: 'done' | 'running' | 'blocked' | 'failed'
  model?: string
  promptTokens?: number
  completionTokens?: number
  cost?: number
  fallback?: boolean
  plan: Array<[string, string, 'done' | 'now' | 'pending' | 'failed', string]>
  toolsList: Array<[string, string, string, string]>
  guardrails?: AgentGuardrail[]
  toolCalls?: AgentToolCall[]
  result: string
}

export interface ImageAnalysisSignal {
  code: string
  label: string
  severity: 'low' | 'medium' | 'high'
  confidence: number
  evidence: Record<string, unknown>
}

export interface ImageAnalysis {
  verdict: 'clear' | 'watch' | 'suspicious' | 'unknown'
  confidence: number | null
  signals: ImageAnalysisSignal[]
  quality: Record<string, number | boolean | null>
  needs_vision: boolean
  analyzed_at: string | null
}

export interface ListingImage {
  id: number
  listing_id: number
  kind: string
  url: string
  local_path: string | null
  status: string
  width: number | null
  height: number | null
  bytes: number | null
  phash: string | null
  brightness: number | null
  error: string | null
  downloaded_at: string | null
}

export interface ImageQueueItem {
  listing_id: number
  title: string | null
  community_name: string | null
  district: string | null
  rent: number | null
  score: number | null
  image_url: string | null
  image: ListingImage | null
  analysis: ImageAnalysis | null
}

export interface ImageStats {
  candidates: number
  downloaded: number
  failed: number
  analyzed: number
  pending: number
  suspicious: number
  watch: number
  vision_pending: number
  vision_enabled: boolean
  duplicate_distance: number
}

export interface ImageDuplicateGroup {
  size: number
  listings: Array<{ listing_id: number; title: string }>
}

export interface ImagesData {
  stats: ImageStats
  queue: { items: ImageQueueItem[] }
  duplicates: ImageDuplicateGroup[]
  vision_enabled: boolean
}

export interface ReputationSummary {
  count: number
  uncertain: number
  score: number
  status: 'insufficient' | 'low' | 'watch' | 'high'
  label: string
  risk: string
  sources: string[]
  issue_types: Record<string, number>
  top_issue?: string | null
  top_issue_label?: string | null
  latest_at?: string | null
}

export interface ReputationMention {
  id: number
  source: string
  url: string | null
  title: string | null
  excerpt: string
  issue_type: string | null
  issue_label?: string | null
  severity: 'low' | 'medium' | 'high'
  confidence: number
  match_status: 'verified' | 'uncertain' | 'rejected'
  published_at: string | null
  created_at: string
  expires_at: string | null
}

export interface ReputationOverview {
  stats: {
    communities: number
    with_evidence: number
    without_evidence: number
    verified: number
    uncertain: number
    high_risk: number
    sources: number
  }
  risky: Array<ReputationSummary & { community_id: number; name: string; district: string | null }>
  missing: Array<{ community_id: number; name: string; district: string | null; listings: number }>
  recent: ReputationMention[]
  issue_types: Record<string, string>
  sources: string[]
  half_life_days: number
}

export interface AgentEvalCase {
  id: string
  kind: 'query' | 'guardrail'
  message: string
  passed: boolean
  details: Record<string, unknown>
}

export interface AgentEvalMetrics {
  intent_case_accuracy: number
  intent_field_accuracy: number
  tool_accuracy: number
  arg_accuracy: number
  schema_valid_rate: number
  grounding_rate: number
  guardrail_accuracy: number
  overall_pass_rate: number
  query_cases: number
  guardrail_cases: number
}

export interface AgentEvalRun {
  id: number
  version: string
  mode: string
  total: number
  passed: number
  metrics: AgentEvalMetrics
  cases: AgentEvalCase[]
  duration_ms: number
  created_at: string
}

export interface AgentEvalData {
  dataset_version: string
  dataset_cases: number
  latest: AgentEvalRun | null
  history: Array<{
    id: number
    version: string
    mode: string
    passed: number
    total: number
    metrics: AgentEvalMetrics
    created_at: string
  }>
}

export interface AgentCostData {
  days: number
  sessions: {
    total: number
    done: number
    blocked: number
    failed: number
    running: number
    fallback: number
    fallback_rate: number
    prompt_tokens: number
    completion_tokens: number
    cost: number
    avg_latency_ms: number
  }
  tools: { calls: number; errors: number; avg_latency_ms: number; success_rate: number | null }
  guardrails: { injection_blocks: number; pii_masked: number; quota_blocked: number }
  provider: {
    code: string
    model: string
    used: number
    limit: number
    remaining: number | null
    calls: number
    errors: number
    avg_latency_ms: number
  }
  daily: Array<{ date: string; sessions: number; tokens: number; blocked: number }>
  total_sessions: number
}

export interface MapCommunity {
  id: number
  name: string
  district: string | null
  lng: number
  lat: number
  coord_system: string
  listings: number
  min_rent: number | null
  median_rent: number | null
  avg_score: number | null
  commute_p50: number | null
  commute_p90: number | null
  commute_buckets: number
  commute_static: boolean | null
  sample_listing: {
    id: number
    title: string | null
    rent: number | null
    score: number | null
    image_url: string | null
    url: string
  }
}

export interface MapData {
  communities: MapCommunity[]
  center: [number, number]
  coord_system: string
  tiles: {
    enabled: boolean
    layers: string[]
    attribution: string
    max_zoom: number
    cache_days: number
  }
  stats: { communities: number; listings: number; with_commute: number }
}

export interface OpsAlert {
  code: string
  severity: 'critical' | 'warning' | 'info'
  message: string
}

export interface OpsSnapshot {
  generated_at: string
  db: string
  queued_jobs: number
  running_jobs: number
  oldest_queued_minutes: number | null
  failed_jobs_1h: number
  failing_tasks: Array<{ task_id: number; name: string; last_error: string }>
  providers: Array<{
    code: string
    status: string
    consecutive_failures: number
    circuit_open_until: string | null
    last_error: string | null
  }>
  disk: { path: string; used_pct: number; free_gb: number } | null
  backup: {
    configured: boolean
    dir: string
    latest_age_hours: number | null
    marker: Record<string, unknown>
  }
}

export interface OpsStatus {
  snapshot: OpsSnapshot
  alerts: OpsAlert[]
  state: Record<string, unknown>
  settings: { alertPush?: boolean; alertIntervalMinutes?: number }
}

export interface ShareLink {
  id: number
  label: string
  token_prefix: string
  scope: string
  created_at: string
  expires_at: string | null
  revoked_at: string | null
  last_used_at: string | null
  use_count: number
  active: boolean
  token?: string
}

export interface SourceInfo {
  id: number
  code: string
  name: string
  kind: string
  enabled: boolean
  rate_limit: Record<string, unknown>
  listings: number
  tasks: number
  supported: boolean
  reserved: boolean
  note: string
}

export interface CityInfo {
  id: number
  code: string
  name: string
  domain_template: string
  center_lng: number | null
  center_lat: number | null
  enabled: boolean
  listings: number
  communities: number
  tasks: number
  active_listings?: number
  enabled_tasks?: number
}

export interface ReferenceRent {
  id: number
  community_id: number | null
  community_name: string | null
  district: string | null
  layout: string
  monthly_rent: number
  reference_month: string
  source: string
  url: string | null
  confidence: number
  updated_at: string
}

export interface PublicDashboard {
  generated_at: string
  totals: {
    active_listings: number
    scored_listings: number
    communities: number
    districts: number
    scored_ratio: number
  }
  districts: Array<{
    name: string
    listings: number
    median_rent: number | null
    avg_score: number | null
  }>
  price_bands: Record<string, number>
  line5: { shards: number; listings: number; complete: number; scanned: number }
  data_note: string
  source: { name: string; url: string }
}
