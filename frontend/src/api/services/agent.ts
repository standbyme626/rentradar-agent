import { apiConfig } from '../config'
import { request, stream as streamSse } from '../http'
import { mockAgentService } from '../mock/agent'
import type {
  AgentEvent,
  AgentRequest,
  AgentService,
  ChatSession,
  SavedMonitor,
} from '../contracts'

const httpAgentService: AgentService = {
  async *stream(requestBody: AgentRequest) {
    yield* streamSse<AgentEvent>('/agent/messages/stream', requestBody)
  },
  async stats() {
    return request<{ listings: number; active: number; scored: number }>('/agent/stats')
  },
  async listSessions() {
    return request<ChatSession[]>('/agent/sessions')
  },
  async listMonitors() {
    return request<SavedMonitor[]>('/agent/monitors')
  },
  async saveMonitor(input) {
    return request<SavedMonitor>('/agent/monitors', {
      method: 'POST',
      body: JSON.stringify(input),
    })
  },
  async removeMonitor(id) {
    await request(`/agent/monitors/${encodeURIComponent(id)}`, { method: 'DELETE' })
  },
}

export const agentApi: AgentService = apiConfig.useMockAgent ? mockAgentService : httpAgentService
