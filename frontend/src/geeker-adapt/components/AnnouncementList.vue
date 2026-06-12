<template>
  <div class="card announcement-card">
    <div class="card-head">
      <h3>系统公告</h3>
      <button type="button" class="more-link" @click="onMore">更多 &gt;</button>
    </div>
    <ul class="announcement-list">
      <li v-for="item in visibleItems" :key="item.id" class="announcement-item">
        <el-tag v-if="item.isNew" type="danger" size="small" effect="dark" class="new-tag">新</el-tag>
        <span class="item-title" :title="item.title">{{ item.title }}</span>
        <span class="item-date">{{ item.date }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { MockAnnouncement } from '../../mocks/studentHallMock'

const props = withDefaults(
  defineProps<{
    items: MockAnnouncement[]
    maxItems?: number
  }>(),
  { maxItems: 3 },
)

const visibleItems = computed(() => props.items.slice(0, props.maxItems))

const onMore = () => {
  ElMessage.info('公告列表功能开发中')
}
</script>

<style scoped lang="scss">
.announcement-card {
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

.more-link {
  border: none;
  background: none;
  font-size: 11px;
  color: #6b7280;
  cursor: pointer;

  &:hover {
    color: var(--student-accent, #0066ff);
  }
}

.announcement-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0;
  flex: 1;
  min-height: 0;
}

.announcement-item {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 28px;
  min-height: 28px;
  flex-shrink: 0;
  padding: 0;
  border-bottom: 1px solid #f3f4f6;

  &:last-child {
    border-bottom: none;
  }
}

.new-tag {
  flex-shrink: 0;
  height: 16px !important;
  padding: 0 4px !important;
  font-size: 10px !important;
  line-height: 16px !important;
}

.item-title {
  flex: 1;
  min-width: 0;
  font-size: 11px;
  color: #374151;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-date {
  flex-shrink: 0;
  font-size: 10px;
  color: #9ca3af;
  margin-left: 4px;
}
</style>
