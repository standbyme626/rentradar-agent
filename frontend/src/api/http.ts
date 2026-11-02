import { apiConfig } from './config'

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `HTTP ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

function headers(extra?: HeadersInit): Headers {
  const result = new Headers(extra)
  if (!result.has('Content-Type')) result.set('Content-Type', 'application/json')
  return result
}

function isAuthPath(path: string): boolean {
  return ['/auth/login', '/auth/refresh', '/auth/logout'].some((item) => path.includes(item))
}

let refreshPromise: Promise<boolean> | null = null

async function refreshAccess(): Promise<boolean> {
  if (refreshPromise) return refreshPromise
  refreshPromise = (async () => {
    try {
      const response = await fetch(`${apiConfig.baseUrl}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      })
      return response.ok
    } catch {
      return false
    } finally {
      refreshPromise = null
    }
  })()
  return refreshPromise
}

function unauthorized() {
  window.dispatchEvent(new CustomEvent('rentradar:unauthorized'))
}

async function parseError(response: Response): Promise<ApiError> {
  const text = await response.text()
  let detail: unknown = text
  try {
    const parsed = JSON.parse(text) as { detail?: unknown }
    detail = parsed.detail ?? parsed
  } catch {
    // keep the raw body when the server did not return JSON
  }
  const error = new ApiError(response.status, detail)
  if (response.status === 401) unauthorized()
  return error
}

async function fetchWithAuth(
  path: string,
  init: RequestInit,
  signal: AbortSignal,
): Promise<Response> {
  const options: RequestInit = {
    ...init,
    credentials: 'include',
    headers: headers(init.headers),
    signal,
  }
  let response = await fetch(`${apiConfig.baseUrl}${path}`, options)
  if (response.status === 401 && !isAuthPath(path)) {
    const refreshed = await refreshAccess()
    if (refreshed) {
      response = await fetch(`${apiConfig.baseUrl}${path}`, options)
    }
  }
  return response
}

export async function request<T>(path: string, init: RequestInit = {}, timeout = 15000): Promise<T> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeout)
  try {
    const response = await fetchWithAuth(path, init, controller.signal)
    if (!response.ok) throw await parseError(response)
    if (response.status === 204) return undefined as T
    return (await response.json()) as T
  } finally {
    window.clearTimeout(timer)
  }
}

export async function* stream<T>(path: string, body: unknown, signal?: AbortSignal): AsyncGenerator<T> {
  const init: RequestInit = {
    method: 'POST',
    credentials: 'include',
    headers: headers({ Accept: 'text/event-stream' }),
    body: JSON.stringify(body),
  }
  let response = await fetch(`${apiConfig.baseUrl}${path}`, {
    ...init,
    signal,
  })
  if (response.status === 401 && !isAuthPath(path)) {
    const refreshed = await refreshAccess()
    if (refreshed) {
      response = await fetch(`${apiConfig.baseUrl}${path}`, {
        ...init,
        signal,
      })
    }
  }
  if (!response.ok) throw await parseError(response)
  if (!response.body) throw new ApiError(500, 'SSE response has no body')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let boundary = buffer.indexOf('\n\n')
    while (boundary >= 0) {
      const chunk = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      const data = chunk
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trim())
        .join('\n')
      if (data && data !== '[DONE]') {
        yield JSON.parse(data) as T
      }
      boundary = buffer.indexOf('\n\n')
    }
  }
}
