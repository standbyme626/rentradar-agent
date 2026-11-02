export const statusLabels: Record<string, string> = {
  active: '在售',
  gone: '已下架',
  suspect: '疑似',
  relisted: '重新上架',
}

export const eventLabels: Record<string, string> = {
  new: '新上架',
  price_drop: '降价',
  price_up: '涨价',
  gone: '下架',
  relisted: '重新上架',
  suspect: '疑似',
}

export const reasonLabels: Record<string, string> = {
  price: '性价比',
  commute: '通勤',
  condition: '居住条件',
  convenience: '生活便利',
  reputation: '口碑',
  freshness: '新鲜度',
  risk: '风险',
}

export function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

export function formatRent(value?: number | null): string {
  return value == null ? '—' : `¥${value.toLocaleString('zh-CN')}`
}

export function statusClass(status: string): string {
  if (status === 'active' || status === 'relisted') return 'bg-emerald-50 text-emerald-700'
  if (status === 'suspect') return 'bg-amber-50 text-amber-700'
  if (status === 'gone') return 'bg-slate-100 text-slate-500'
  return 'bg-slate-100 text-slate-600'
}

export function eventClass(type: string): string {
  if (type === 'new' || type === 'relisted') return 'bg-emerald-50 text-emerald-700'
  if (type === 'price_drop') return 'bg-sky-50 text-sky-700'
  if (type === 'suspect' || type === 'price_up') return 'bg-amber-50 text-amber-700'
  return 'bg-slate-100 text-slate-500'
}

export function notifyLabel(payload: Record<string, unknown>, notified: boolean): string {
  if (payload && payload.baseline) return '基线'
  return notified ? '已通知' : '待通知'
}
