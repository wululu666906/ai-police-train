<template>
  <div ref="chartRef" class="geeker-echarts" :style="echartsStyle" />
</template>

<script setup lang="ts">
import { computed, markRaw, nextTick, onActivated, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { ECElementEvent, EChartsType } from 'echarts/core'
import echarts, { type ECOption } from './config'

const props = withDefaults(
  defineProps<{
    option: ECOption
    renderer?: 'canvas' | 'svg'
    resize?: boolean
    theme?: object | string
    width?: number | string
    height?: number | string
    onClick?: (event: ECElementEvent) => void
  }>(),
  {
    renderer: 'canvas',
    resize: true,
  },
)

const echartsStyle = computed(() => {
  if (props.width || props.height) {
    return {
      height: props.height ? `${props.height}px` : '100%',
      width: props.width ? `${props.width}px` : '100%',
    }
  }
  return { height: '100%', width: '100%' }
})

const chartRef = ref<HTMLDivElement>()
const chartInstance = ref<EChartsType>()

const draw = () => {
  chartInstance.value?.setOption(props.option, { notMerge: true })
}

watch(() => props.option, draw, { deep: true })

const handleClick = (event: ECElementEvent) => props.onClick?.(event)

const init = () => {
  if (!chartRef.value) return
  chartInstance.value = echarts.getInstanceByDom(chartRef.value) ?? undefined

  if (!chartInstance.value) {
    chartInstance.value = markRaw(
      echarts.init(chartRef.value, props.theme, { renderer: props.renderer }),
    )
    chartInstance.value.on('click', handleClick)
    draw()
  }
}

const resizeChart = () => {
  if (chartInstance.value && props.resize) {
    chartInstance.value.resize({ animation: { duration: 200 } })
  }
}

let resizeTimer: ReturnType<typeof setTimeout> | null = null
const debouncedResize = () => {
  if (resizeTimer) clearTimeout(resizeTimer)
  resizeTimer = setTimeout(resizeChart, 200)
}

onMounted(() => {
  nextTick(init)
  window.addEventListener('resize', debouncedResize)
})

onActivated(resizeChart)

onBeforeUnmount(() => {
  if (resizeTimer) clearTimeout(resizeTimer)
  chartInstance.value?.dispose()
  window.removeEventListener('resize', debouncedResize)
})

defineExpose({
  getInstance: () => chartInstance.value,
  resize: resizeChart,
  draw,
})
</script>

<style scoped>
.geeker-echarts {
  min-height: 0;
}
</style>
