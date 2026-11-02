<template>
  <div
    class="relative flex h-[440px] flex-col items-center justify-center overflow-hidden rounded-2xl border border-line bg-paper2 text-center"
    style="background-image: linear-gradient(rgba(31, 93, 74, 0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(31, 93, 74, 0.045) 1px, transparent 1px); background-size: 28px 28px"
  >
    <div class="absolute left-[20%] top-[46%] h-0.5 w-[45%] -rotate-12 rounded-full bg-forest/35">
      <span class="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-forest/60" />
    </div>
    <span class="absolute left-[32%] top-[38%] h-4 w-4 -rotate-45 rounded-[50%_50%_50%_0] bg-forest shadow" />
    <span class="absolute left-[55%] top-[30%] h-4 w-4 -rotate-45 rounded-[50%_50%_50%_0] bg-coral shadow" />
    <span class="absolute left-[48%] top-[62%] h-4 w-4 -rotate-45 rounded-[50%_50%_50%_0] bg-amber shadow" />
    <div class="relative mt-24 text-[14px] font-semibold text-ink">5 号线沿线候选</div>
    <div class="relative mt-1 text-[11.5px] text-muted">地图视图即将接入 · 当前先用列表 + 对比</div>
  </div>
</template>
