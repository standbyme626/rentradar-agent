import type {
  AdminOverview,
  CoverageData,
  QualityData,
} from '@/api/contracts'
import type { Stats } from '@/api/types'

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

export const emptyStats: Stats = {
  listings: 0,
  line5: 0,
  scored: 0,
  ge75: 0,
  avg_score: 0,
  median_score: 0,
  max_score: 0,
  communities: 0,
  geocoded: 0,
  commute_samples: 0,
  commute_communities: 0,
  poi_cache: 0,
  probes: 0,
  listings_no_geo: 0,
  listings_no_commute: 0,
  poi_capped: 0,
  no_commute_but_geo: 0,
}

export const emptyOverview: AdminOverview = {
  stats: emptyStats,
  funnel: [],
  quality: [],
  runs: [],
  nextSteps: [],
}

export const emptyCoverage: CoverageData = {
  stats: emptyStats,
  communities: [],
  priority: [],
}

export const emptyQuality: QualityData = {
  stats: emptyStats,
  geoPriority: [],
  poiCapped: [],
}
