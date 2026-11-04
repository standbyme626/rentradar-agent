import type { Conditions } from '@/api/contracts'

export function detectLong(prompt: string): boolean {
  return /龙岗|3000/.test(prompt)
}

export function conditionsFor(prompt: string): Conditions {
  const isLong = detectLong(prompt)
  return {
    company: '',
    budget: '未设置',
    line: '5 号线',
    commute: '不限',
    layout: '不限',
    district: '',
    must: '无硬条件',
    isLong,
  }
}
