<template>
  <div class="card donut-card">
    <h3 class="card-title">训练状态分布</h3>
    <div class="chart-wrap">
      <ECharts :option="chartOption" :height="72" />
    </div>
    <div class="legend legend--row">
      <div v-for="item in data" :key="item.name" class="legend-item">
        <i class="legend-dot" :style="{ background: item.color }" />
        <span>{{ item.name }}</span>
        <strong>{{ item.value }}%</strong>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ECOption } from './ECharts/config'
import ECharts from './ECharts/index.vue'
import type { MockStatusSlice } from '../../mocks/studentHallMock'

const props = defineProps<{
  data: MockStatusSlice[]
}>()

const chartOption = computed<ECOption>(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c}%' },
  series: [
    {
      type: 'pie',
      radius: ['52%', '72%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: false,
      label: { show: false },
      data: props.data.map((item) => ({
        name: item.name,
        value: item.value,
        itemStyle: { color: item.color },
      })),
    },
  ],
}))
</script>

<style scoped lang="scss">
.donut-card {
  height: 100%;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

.card-title {
  margin: 0 0 2px;
  font-size: 12px;
  font-weight: 700;
  color: #1f2937;
  flex-shrink: 0;
}

.chart-wrap {
  height: 72px;
  flex-shrink: 0;
}

.legend {
  display: grid;
  gap: 2px;
  margin-top: 2px;
  flex-shrink: 0;

  &--row {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 4px;
  }
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  color: #6b7280;
  min-width: 0;

  span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  strong {
    margin-left: auto;
    color: #111827;
    font-weight: 700;
    flex-shrink: 0;
  }
}

.legend-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  flex-shrink: 0;
}
</style>
