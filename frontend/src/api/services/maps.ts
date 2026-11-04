import { request } from '../http'
import type { MapData } from '../types'

export const mapApi = {
  communities: () => request<MapData>('/maps/communities'),
}
