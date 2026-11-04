import type { PublicDashboard } from '../types'

export async function fetchPublicDashboard(token: string): Promise<PublicDashboard> {
  const response = await fetch(`/api/public/dashboard/${encodeURIComponent(token)}`, {
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`${response.status}: ${detail.slice(0, 200)}`)
  }
  return (await response.json()) as PublicDashboard
}
