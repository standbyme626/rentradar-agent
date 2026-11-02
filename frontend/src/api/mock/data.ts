import raw from '../mockData.json'
import type { MockData } from '../types'

export const mockData = raw as unknown as MockData

export const delay = (ms = 220) => new Promise((resolve) => window.setTimeout(resolve, ms))
