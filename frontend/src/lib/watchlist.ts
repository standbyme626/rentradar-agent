export const WATCH_STATES = [
  { key: 'new', label: '新收藏', className: 'tag-green' },
  { key: 'seen', label: '已看过', className: 'tag-neutral' },
  { key: 'contacted', label: '已联系', className: 'tag-amber' },
  { key: 'viewed', label: '已看房', className: 'tag-green' },
  { key: 'rejected', label: '已淘汰', className: 'tag-coral' },
] as const

export type WatchState = (typeof WATCH_STATES)[number]['key']

export const CHECKLIST_KEYS = [
  'soundproofing',
  'leak',
  'water',
  'power',
  'network',
  'delivery',
  'property',
  'elevator',
] as const

export const CHECKLIST_LABELS: Record<string, string> = {
  soundproofing: '隔音',
  leak: '漏水',
  water: '水电',
  power: '供电',
  network: '网络',
  delivery: '外卖',
  property: '物业',
  elevator: '电梯',
}

export function stateLabel(state: string | null | undefined): string {
  return WATCH_STATES.find((item) => item.key === state)?.label ?? '未加入'
}

export function stateClass(state: string | null | undefined): string {
  return WATCH_STATES.find((item) => item.key === state)?.className ?? 'tag-neutral'
}

export function checkedCount(items: Record<string, boolean> | undefined): number {
  return CHECKLIST_KEYS.filter((key) => items?.[key]).length
}
