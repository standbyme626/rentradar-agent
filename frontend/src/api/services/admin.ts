import { apiConfig } from '../config'
import { request } from '../http'
import { mockAdminService } from '../mock/admin'
import type {
  AdminOverview,
  AdminService,
  AdminSettings,
  AuditLogEntry,
  CoverageData,
  Job,
  QualityData,
  SamplingRequest,
} from '../contracts'
import type { AgentSession, Candidate, Run, Task } from '../types'

const httpAdminService: AdminService = {
  overview: () => request<AdminOverview>('/admin/overview'),
  candidates: () => request<Candidate[]>('/admin/candidates'),
  coverage: () => request<CoverageData>('/admin/coverage'),
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
}

export const adminApi: AdminService = apiConfig.useMockAdmin ? mockAdminService : httpAdminService
