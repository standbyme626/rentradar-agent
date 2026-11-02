import { request } from '../http'
import type {
  ProviderCall,
  ProviderInfo,
  ProviderPatch,
  ProviderService,
  ProviderTestResult,
  ProviderUsage,
} from '../contracts'

const httpProviderService: ProviderService = {
  list: (domain) =>
    request<ProviderInfo[]>(
      `/admin/providers${domain ? `?domain=${encodeURIComponent(domain)}` : ''}`,
    ),
  test: (code) =>
    request<ProviderTestResult>(`/admin/providers/${encodeURIComponent(code)}/test`, {
      method: 'POST',
    }),
  calls: (provider, limit = 50) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (provider) params.set('provider', provider)
    return request<ProviderCall[]>(`/admin/provider-calls?${params.toString()}`)
  },
  usage: (code) =>
    request<ProviderUsage[]>(`/admin/providers/${encodeURIComponent(code)}/usage`),
  update: (code, patch: ProviderPatch) =>
    request<ProviderInfo>(`/admin/providers/${encodeURIComponent(code)}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),
}

export const providersApi: ProviderService = httpProviderService
