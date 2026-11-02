<script setup lang="ts">
import { Image, Sparkles } from 'lucide-vue-next'
import { useToast } from '@/composables/useToast'

const { toast } = useToast()
</script>

<template>
  <div>
    <h2 class="text-[20px] font-bold tracking-tight">图片 / AI</h2>
    <p class="mt-1 text-[12.5px] text-muted">当前未接入。下一步只对候选运行，不占高德额度。</p>

    <div class="mt-3 rounded-xl border border-forest/15 bg-forest-soft/60 px-3.5 py-2.5 text-[11px] leading-5 text-forest">
      <b>现状：</b>只有列表页封面 URL；没有 images 表、没有下载、没有 pHash、没有视觉标签。详情页也未抓取。
    </div>

    <div class="mt-4 grid gap-4 xl:grid-cols-2">
      <section class="card p-4">
        <h3 class="panel-title">计划管线</h3>
        <div class="mt-3 flex flex-wrap items-center gap-1.5 text-[10.5px] text-muted">
          <span class="rounded-lg border border-line bg-paper2 px-2.5 py-1.5">列表封面</span><span>→</span>
          <span class="rounded-lg border border-dashed border-line2 px-2.5 py-1.5 opacity-60">候选详情 3–6 图</span><span>→</span>
          <span class="rounded-lg border border-dashed border-line2 px-2.5 py-1.5 opacity-60">本地存储 + pHash</span><span>→</span>
          <span class="rounded-lg border border-dashed border-line2 px-2.5 py-1.5 opacity-60">Qwen-VL 标签</span><span>→</span>
          <span class="rounded-lg border border-dashed border-line2 px-2.5 py-1.5 opacity-60">假房源信号</span>
        </div>
        <div class="mt-3 rounded-xl border border-line bg-paper2 px-3.5 py-2.5 text-[10.5px] leading-5 text-muted">
          标签：实拍/样板间、装修程度、朝向采光、可见水渍/霉斑、图文不符。每条标签存置信度 + 证据图；假房源需 ≥2 个信号（pHash 复用 / 价格异常 / 中介话术 / 图文不符）。
        </div>
        <div class="mt-3 flex flex-wrap gap-1.5">
          <span class="tag-neutral">仅候选</span><span class="tag-neutral">魔搭免费额度</span><span class="tag-neutral">不占高德</span><span class="tag-neutral">证据可追溯</span>
        </div>
      </section>

      <section class="card p-4">
        <h3 class="panel-title">队列 <span class="hint">0 待处理 / 0 已分析</span></h3>
        <div class="grid place-items-center px-4 py-10 text-center">
          <Image :size="28" class="text-line2" />
          <p class="mt-2 text-[12px] text-faint">接入后这里显示候选房源的抓图、pHash 和 AI 标签进度。</p>
        </div>
        <div class="flex justify-center gap-2">
          <button class="btn" disabled>抓取候选详情图</button>
          <button class="btn" disabled>运行视觉分析</button>
        </div>
      </section>
    </div>

    <section class="card mt-4 p-4">
      <h3 class="panel-title flex items-center gap-2"><Sparkles :size="15" class="text-forest" />设计预览：单套图片分析</h3>
      <div class="mt-3 grid gap-3 sm:grid-cols-3">
        <div class="rounded-xl border border-line bg-paper2 px-3.5 py-3">
          <div class="text-[10px] text-muted">实拍概率</div>
          <div class="mt-0.5 text-[22px] font-bold text-forest">82%</div>
          <div class="text-[9.5px] text-faint">图 2 / 图 4 为手机实拍</div>
        </div>
        <div class="rounded-xl border border-line bg-paper2 px-3.5 py-3">
          <div class="text-[10px] text-muted">装修 / 朝向</div>
          <div class="mt-0.5 text-[18px] font-bold">精装 · 南向</div>
          <div class="text-[9.5px] text-faint">采光良好；图文一致 0.86</div>
        </div>
        <div class="rounded-xl border border-line bg-paper2 px-3.5 py-3">
          <div class="text-[10px] text-muted">可见问题</div>
          <div class="mt-0.5 text-[18px] font-bold text-amber">1 处水渍</div>
          <div class="text-[9.5px] text-faint">图 2 墙面右下角；置信度 0.71</div>
        </div>
      </div>
      <button class="btn mt-3" @click="toast('图片分析管线将在后端接入后启用（演示）')">查看设计说明</button>
    </section>
  </div>
</template>
