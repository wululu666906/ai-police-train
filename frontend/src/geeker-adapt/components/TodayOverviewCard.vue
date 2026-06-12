<template>
  <div class="card overview-card">
    <div class="card-head">
      <h3>今日训练概览</h3>
      <span class="card-date">{{ data.date }}</span>
    </div>
    <div class="metric-row">
      <div class="metric-cell">
        <span class="metric-cell-label">训练次数</span>
        <div class="metric-cell-value">
          <strong>{{ data.trainingCount }}</strong>
          <em>+{{ data.trainingDelta }}</em>
        </div>
      </div>
      <div class="metric-cell">
        <span class="metric-cell-label">完成训练</span>
        <div class="metric-cell-value">
          <strong>{{ data.completedCount }}</strong>
          <em>+{{ data.completedDelta }}</em>
        </div>
      </div>
      <div class="metric-cell">
        <span class="metric-cell-label">平均得分</span>
        <div class="metric-cell-value">
          <strong>{{ data.avgScore }}</strong>
          <em>+{{ data.avgScoreDelta }}</em>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { MockTodayOverview } from '../../mocks/studentHallMock'
import '../styles/dashboard-metrics.scss'

defineProps<{
  data: MockTodayOverview
}>()
</script>

<style scoped lang="scss">
.overview-card {
  height: 100%;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  flex-shrink: 0;

  h3 {
    margin: 0;
    font-size: 13px;
    font-weight: 700;
    color: #1f2937;
  }
}

.card-date {
  font-size: 11px;
  color: #9ca3af;
}

.metric-row {
  flex: 1;
  min-height: 0;
}
</style>
