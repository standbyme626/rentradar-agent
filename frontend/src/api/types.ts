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
  filters: Record<string, unknown>
  schedule: Record<string, number>
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
  result: string
}
