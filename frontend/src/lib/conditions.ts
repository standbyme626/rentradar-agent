import type { Conditions } from '@/api/contracts'

export function detectLong(prompt: string): boolean {
  return /龙岗|3000/.test(prompt)
}

export function conditionsFor(prompt: string): Conditions {
  const isLong = detectLong(prompt)
  return isLong
    ? {
        company: '',
        budget: '3000 元/月以内',
        line: '5 号线 · 龙岗段',
        commute: '可接受 60–90 分钟',
        layout: '两居优先',
        district: '',
        must: '预算优先',
        isLong,
      }
    : {
        company: '',
        budget: '3500–4500 元/月',
        line: '5 号线沿线',
        commute: '≤ 40 分钟',
        layout: '1–2 居室',
        district: '',
        must: '电梯（待详情核实）',
        isLong,
      }
}
