<template>
  <aside class="hall-right-panel">
    <TodayOverviewCard class="right-panel-card right-panel-card--overview" :data="overview" />
    <StatusDonutChart class="right-panel-card right-panel-card--chart" :data="distribution" />
    <AnnouncementList class="right-panel-card right-panel-card--announce" :items="announcements" :max-items="3" />
    <QuickAccessGrid class="right-panel-card right-panel-card--quick" />
  </aside>
</template>

<script setup lang="ts">
import {
  MOCK_ANNOUNCEMENTS,
  MOCK_STATUS_DISTRIBUTION,
  MOCK_TODAY_OVERVIEW,
} from '../../mocks/studentHallMock'
import TodayOverviewCard from './TodayOverviewCard.vue'
import StatusDonutChart from './StatusDonutChart.vue'
import AnnouncementList from './AnnouncementList.vue'
import QuickAccessGrid from './QuickAccessGrid.vue'

const overview = { ...MOCK_TODAY_OVERVIEW, date: new Date().toISOString().slice(0, 10) }
const distribution = MOCK_STATUS_DISTRIBUTION
const announcements = MOCK_ANNOUNCEMENTS
</script>

<style scoped lang="scss">
.hall-right-panel {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: flex-start;
  gap: 6px;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

:deep(.right-panel-card) {
  flex-shrink: 0;
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

:deep(.right-panel-card--overview) {
  height: 100px;
}

:deep(.right-panel-card--chart) {
  height: 132px;
}

:deep(.right-panel-card--announce) {
  height: 156px;
}

:deep(.right-panel-card--quick) {
  height: 86px;
}
</style>
