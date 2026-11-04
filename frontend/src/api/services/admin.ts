import { apiConfig } from '../config'
import { request } from '../http'
import { mockAdminService } from '../mock/admin'
import type {
  AdminOverview,
  CommuteDestination,
  AdminService,
  AdminSettings,
  AuditLogEntry,
  CoverageData,
  CrawlCoverage,
  Job,
  QualityData,
  ReputationDraft,
  ReputationMentionInput,
  SamplingRequest,
} from '../contracts'
import type {
  AgentCostData,
  AgentEvalData,
  AgentEvalRun,
  AgentSession,
  Candidate,
  ImagesData,
  OpsStatus,
  ReferenceRent,
  ReputationMention,
  ReputationOverview,
  ReputationSummary,
  Run,
  ShareLink,
  SourceInfo,
  CityInfo,
  Task,
} from '../types'

const httpAdminService: AdminService = {
  overview: () => request<AdminOverview>('/admin/overview'),
  candidates: () => request<Candidate[]>('/admin/candidates'),
  coverage: () => request<CoverageData>('/admin/coverage'),
  crawlCoverage: (taskId) =>
    request<CrawlCoverage>(
      `/admin/crawl-coverage${taskId ? `?task_id=${taskId}` : ''}`,
    ),
  quality: () => request<QualityData>('/admin/quality'),
  agentSessions: () => request<AgentSession[]>('/admin/agent/sessions'),
  runs: () => request<Run[]>('/admin/runs'),
  tasks: () => request<Task[]>('/admin/tasks'),
  runTask: (taskId) =>
    request<{ ok: boolean; job_id: number }>(`/admin/tasks/${taskId}/run`, {
      method: 'POST',
    }),
  settings: () => request<AdminSettings>('/admin/settings'),
  updateSettings: (patch) =>
    request<AdminSettings>('/admin/settings', { method: 'PUT', body: JSON.stringify(patch) }),
  enqueueAnalysis: (listingIds) =>
    request<Job>('/admin/jobs/analysis', {
      method: 'POST',
      body: JSON.stringify({ listingIds }),
    }),
  startSampling: (sampling: SamplingRequest) =>
    request<Job>('/admin/jobs/sampling', {
      method: 'POST',
      body: JSON.stringify(sampling),
    }),
  enqueueGeocode: (communityIds) =>
    request<Job>('/admin/jobs/geocode', {
      method: 'POST',
      body: JSON.stringify({ communityIds }),
    }),
  async annotateSession(sessionId, label) {
    await request(`/admin/agent/sessions/${sessionId}/annotate`, {
      method: 'POST',
      body: JSON.stringify({ label }),
    })
  },
  auditLogs: (limit = 100) =>
    request<AuditLogEntry[]>(`/admin/audit?limit=${limit}`),
  images: () => request<ImagesData>('/admin/images'),
  analyzeImages: (listingIds, limit = 30) =>
    request<Job>('/admin/images/analyze', {
      method: 'POST',
      body: JSON.stringify({ listingIds, limit }),
    }),
  reputation: () => request<ReputationOverview>('/admin/reputation'),
  reputationCommunities: (q) =>
    request<Array<{ id: number; name: string; district: string | null }>>(
      `/admin/reputation/communities?q=${encodeURIComponent(q)}`,
    ),
  reputationCommunity: (id) =>
    request<{
      community: { id: number; name: string; district: string | null }
      summary: ReputationSummary
      mentions: ReputationMention[]
    }>(`/admin/reputation/communities/${id}`),
  createReputationMention: (payload: ReputationMentionInput) =>
    request<ReputationMention>('/admin/reputation/mentions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateReputationMention: (id, matchStatus) =>
    request<ReputationMention>(`/admin/reputation/mentions/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ matchStatus }),
    }),
  deleteReputationMention: (id) =>
    request<void>(`/admin/reputation/mentions/${id}`, { method: 'DELETE' }),
  extractReputation: async (communityId, text) => {
    const result = await request<{ drafts: ReputationDraft[]; note: string }>(
      '/admin/reputation/extract',
      {
        method: 'POST',
        body: JSON.stringify({ communityId, text }),
      },
      60000,
    )
    return { drafts: result.drafts, note: result.note }
  },
  agentEval: () => request<AgentEvalData>('/admin/agent/eval'),
  runAgentEval: () =>
    request<AgentEvalRun>('/admin/agent/eval/run', {
      method: 'POST',
      body: JSON.stringify({ mode: 'rules' }),
    }),
  agentCost: (days = 7) => request<AgentCostData>(`/admin/agent/cost?days=${days}`),
  commuteDestination: () =>
    request<CommuteDestination | null>('/admin/commute/destination'),
  opsStatus: () => request<OpsStatus>('/admin/ops/status'),
  runOpsCheck: (force = false) =>
    request<Record<string, unknown>>(`/admin/ops/check?force=${force ? 'true' : 'false'}`, {
      method: 'POST',
    }),
  shareLinks: () => request<ShareLink[]>('/admin/share-links'),
  createShareLink: (label, expiresDays) =>
    request<ShareLink>('/admin/share-links', {
      method: 'POST',
      body: JSON.stringify({ label, expiresDays }),
    }),
  revokeShareLink: (id) =>
    request<ShareLink>(`/admin/share-links/${id}`, { method: 'DELETE' }),
  sources: () => request<SourceInfo[]>('/admin/sources'),
  updateSource: (code, enabled) =>
    request<SourceInfo>(`/admin/sources/${code}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    }),
  cities: () => request<CityInfo[]>('/admin/cities'),
  updateCity: (code, enabled) =>
    request<CityInfo>(`/admin/cities/${code}`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    }),
  createTask: (payload) =>
    request<Task>('/admin/tasks', { method: 'POST', body: JSON.stringify(payload) }),
  updateTask: (id, payload) =>
    request<Task>(`/admin/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  disableTask: (id) => request<Task>(`/admin/tasks/${id}`, { method: 'DELETE' }),
  referenceRents: (city) =>
    request<ReferenceRent[]>(`/admin/reference-rents${city ? `?city=${city}` : ''}`),
  importReferenceRents: (city, rows) =>
    request<Record<string, number>>('/admin/reference-rents/import', {
      method: 'POST',
      body: JSON.stringify({ cityCode: city, rows }),
    }),
  deleteReferenceRent: (id) =>
    request<{ ok: boolean }>(`/admin/reference-rents/${id}`, { method: 'DELETE' }),
}

export const adminApi: AdminService = apiConfig.useMockAdmin ? mockAdminService : httpAdminService
