<template>
  <div class="select-filter">
    <div v-for="item in data" :key="item.key" class="select-filter-item">
      <div class="select-filter-item-title">
        <span>{{ item.title }} ：</span>
      </div>
      <span v-if="!item.options.length" class="select-filter-notData">暂无数据</span>
      <el-scrollbar>
        <ul class="select-filter-list">
          <li
            v-for="option in item.options"
            :key="String(option.value)"
            :class="{
              active: isOptionActive(item.key, option.value),
            }"
            @click="select(item, option)"
          >
            <slot :row="option">
              <el-icon v-if="option.icon">
                <component :is="option.icon" />
              </el-icon>
              <span>{{ option.label }}</span>
            </slot>
          </li>
        </ul>
      </el-scrollbar>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { Component } from 'vue'

interface OptionsProps {
  value: string | number
  label: string
  icon?: Component
}

interface SelectDataProps {
  title: string
  key: string
  multiple?: boolean
  options: OptionsProps[]
}

interface SelectFilterProps {
  data?: SelectDataProps[]
  defaultValues?: Record<string, unknown>
}

const props = withDefaults(defineProps<SelectFilterProps>(), {
  data: () => [],
  defaultValues: () => ({}),
})

const emit = defineEmits<{
  change: [value: Record<string, unknown>]
}>()

const selected = ref<Record<string, unknown>>({})

const isOptionActive = (key: string, value: string | number) => {
  const current = selected.value[key]
  if (Array.isArray(current)) return current.includes(value)
  return current === value
}

watch(
  () => props.defaultValues,
  () => {
    props.data.forEach((item) => {
      if (item.multiple) selected.value[item.key] = props.defaultValues[item.key] ?? ['']
      else selected.value[item.key] = props.defaultValues[item.key] ?? ''
    })
  },
  { deep: true, immediate: true },
)

const select = (item: SelectDataProps, option: OptionsProps) => {
  if (!item.multiple) {
    if (selected.value[item.key] !== option.value) selected.value[item.key] = option.value
  } else {
    const current = Array.isArray(selected.value[item.key]) ? [...(selected.value[item.key] as unknown[])] : []
    if (item.options[0].value === option.value) {
      selected.value[item.key] = [option.value]
    } else if (current.includes(option.value)) {
      const next = current.filter((value) => value !== option.value)
      selected.value[item.key] = next.length ? next : [item.options[0].value]
    } else {
      const next = current.filter((value) => value !== item.options[0].value)
      next.push(option.value)
      selected.value[item.key] = next
    }
  }
  emit('change', { ...selected.value })
}
</script>

<style scoped lang="scss">
@use './index.scss' as *;
</style>
