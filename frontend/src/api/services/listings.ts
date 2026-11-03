import { request, requestBlob } from '../http'
import type { Inspection, ListingDetail, WatchlistEntry } from '../types'

export const listingApi = {
  detail: (id: number) => request<ListingDetail>(`/listings/${id}`),
  watchlist: () => request<WatchlistEntry[]>('/listings/watchlist'),
  setState: (id: number, state: string, note?: string | null) =>
    request<{ ok: boolean; state: string }>(`/listings/${id}/state`, {
      method: 'PATCH',
      body: JSON.stringify({ state, note: note ?? null }),
    }),
  inspection: (id: number) => request<Inspection>(`/listings/${id}/inspection`),
  saveInspection: (id: number, payload: Pick<Inspection, 'items' | 'note' | 'photos'>) =>
    request<Inspection>(`/listings/${id}/inspection`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  exportWatchlist: () => requestBlob('/listings/watchlist/export.csv'),
}
