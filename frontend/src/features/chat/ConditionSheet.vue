<script setup lang="ts">
import { reactive, watch } from 'vue'
import AppSheet from '@/components/ui/AppSheet.vue'

const props = defineProps<{ open: boolean; company?: string }>()
const emit = defineEmits<{ close: []; apply: [prompt: string] }>()

const form = reactive({
  company: '',
  budget: '',
  commute: '',
  layout: '',
  area: '',
  musts: [] as string[],
})

const mustOptions = ['电梯', '南向', '精装', '可养宠', '近地铁']

watch(
  () => props.open,
  (open) => {
    if (open && props.company) form.company = props.company
  },
)

function toggleMust(value: string) {
  if (form.musts.includes(value)) form.musts = form.musts.filter((item) => item !== value)
  else form.musts = [...form.musts, value]
}

function apply() {
  const must = form.musts.length ? `，最好有${form.musts.join('、')}` : ''
  const parts = [
    form.company ? `公司在${form.company}` : null,
    form.budget ? `预算 ${form.budget}` : '预算不限',
    form.area ? form.area : '区域不限',
    form.commute ? `通勤 ${form.commute} 内` : '通勤不限',
    form.layout ? form.layout : '户型不限',
  ]
  emit('apply', `${parts.filter(Boolean).join('，')}${must}`)
}
</script>

<template>
  <AppSheet :open="props.open" title="补充条件" @close="emit('close')">
    <div class="grid gap-4 sm:grid-cols-2">
      <div class="sm:col-span-2">
        <label class="label">公司地址</label>
        <input v-model="form.company" class="input" />
      </div>
      <div>
        <label class="label">预算</label>
        <select v-model="form.budget" class="input">
          <option value="">请选择</option>
          <option>3000 以内</option>
          <option>3500–4500</option>
          <option>4500–6000</option>
          <option>6000 以上</option>
        </select>
      </div>
      <div>
        <label class="label">通勤上限</label>
        <select v-model="form.commute" class="input">
          <option value="">请选择</option>
          <option>30 分钟</option>
          <option>40 分钟</option>
          <option>60 分钟</option>
          <option>90 分钟</option>
        </select>
      </div>
      <div>
        <label class="label">户型</label>
        <select v-model="form.layout" class="input">
          <option value="">请选择</option>
          <option>1–2 居室</option>
          <option>两居</option>
          <option>三居</option>
          <option>不限</option>
        </select>
      </div>
      <div>
        <label class="label">线路 / 区域</label>
        <select v-model="form.area" class="input">
          <option value="">请选择</option>
          <option>5 号线沿线</option>
          <option>龙岗方向</option>
          <option>罗湖 / 福田</option>
          <option>不限</option>
        </select>
      </div>
      <div class="sm:col-span-2">
        <label class="label">必须项</label>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="option in mustOptions"
            :key="option"
            type="button"
            class="rounded-full border px-3 py-1.5 text-[11px] transition"
            :class="
              form.musts.includes(option)
                ? 'border-forest bg-forest-soft font-semibold text-forest'
                : 'border-line2 bg-paper text-muted hover:border-line2'
            "
            @click="toggleMust(option)"
          >
            {{ option }}
          </button>
        </div>
      </div>
    </div>
    <template #footer>
      <button class="btn" @click="emit('close')">取消</button>
      <button class="btn-primary" @click="apply">应用到问题</button>
    </template>
  </AppSheet>
</template>
