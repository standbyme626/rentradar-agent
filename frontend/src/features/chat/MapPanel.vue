<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { apiConfig } from '@/api/config'
import { mockData } from '@/api/mock/data'

type AmapWindow = Window & {
  AMap?: any
  _AMapSecurityConfig?: { securityJsCode: string }
}

const container = ref<HTMLElement | null>(null)
const status = ref<'idle' | 'loading' | 'ready' | 'error' | 'no-key'>('idle')
const message = ref('')
const markerCount = ref(0)
let map: any = null

async function loadAmap(): Promise<any> {
  const w = window as AmapWindow
  if (w.AMap) return w.AMap
  await new Promise<void>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = `https://webapi.amap.com/maps?v=2.0&key=${apiConfig.amapJsKey}`
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('高德 JS API 加载失败'))
    document.head.appendChild(script)
  })
  return w.AMap
}

onMounted(async () => {
  if (!apiConfig.amapJsKey) {
    status.value = 'no-key'
    return
  }
  status.value = 'loading'
  try {
    const w = window as AmapWindow
    if (apiConfig.amapSecurityCode) {
      w._AMapSecurityConfig = { securityJsCode: apiConfig.amapSecurityCode }
    }
    const AMap = await loadAmap()
    if (!container.value) return
    map = new AMap.Map(container.value, {
      zoom: 11,
      center: [114.12, 22.62],
      mapStyle: 'amap://styles/whitesmoke',
    })
    const points = mockData.communities
      .filter((item) => item.lng != null && item.lat != null)
      .slice(0, 20)
      .map((item) => ({ name: item.name, lng: item.lng as number, lat: item.lat as number }))
    points.forEach((item) => {
      new AMap.Marker({
        position: [item.lng, item.lat],
        title: item.name,
        map,
      })
    })
    markerCount.value = points.length
    status.value = 'ready'
  } catch (error) {
    status.value = 'error'
    message.value = error instanceof Error ? error.message : '地图加载失败'
  }
})

onBeforeUnmount(() => {
  map?.destroy?.()
  map = null
})
</script>

<template>
  <div class="relative h-[440px] overflow-hidden rounded-2xl border border-line bg-paper2">
    <div ref="container" class="h-full w-full" />
    <div v-if="status !== 'ready'" class="absolute inset-0 flex flex-col items-center justify-center px-6 text-center">
      <div
        class="absolute inset-0"
        style="background-image: linear-gradient(rgba(31, 93, 74, 0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(31, 93, 74, 0.045) 1px, transparent 1px); background-size: 28px 28px"
      />
      <span class="absolute left-[20%] top-[46%] h-0.5 w-[45%] -rotate-12 rounded-full bg-forest/35" />
      <span class="absolute left-[32%] top-[38%] h-4 w-4 -rotate-45 rounded-[50%_50%_50%_0] bg-forest shadow" />
      <span class="absolute left-[55%] top-[30%] h-4 w-4 -rotate-45 rounded-[50%_50%_50%_0] bg-coral shadow" />
      <span class="absolute left-[48%] top-[62%] h-4 w-4 -rotate-45 rounded-[50%_50%_50%_0] bg-amber shadow" />
      <div class="relative mt-24 text-[14px] font-semibold text-ink">
        {{ status === 'loading' ? '地图加载中…' : status === 'error' ? '地图加载失败' : '5 号线沿线候选' }}
      </div>
      <div class="relative mt-1 max-w-[360px] text-[11.5px] leading-5 text-muted">
        {{
          status === 'no-key'
            ? '配置 VITE_AMAP_JS_KEY 后启用真实地图；当前显示占位。'
            : status === 'error'
              ? message
              : '正在加载高德 JS API。'
        }}
      </div>
    </div>
    <span v-if="status === 'ready'" class="absolute bottom-3 left-3 rounded-full bg-paper/90 px-2.5 py-1 text-[10px] text-muted shadow">
      已加载 {{ markerCount }} 个小区
    </span>
  </div>
</template>
