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
