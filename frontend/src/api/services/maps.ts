import { request } from '../http'
import type { MapData, TransitCatalog } from '../types'

export const mapApi = {
  communities: () => request<MapData>('/maps/communities'),
  stations: () => request<TransitCatalog>('/maps/stations'),
}
