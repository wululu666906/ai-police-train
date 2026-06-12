<template>
  <div class="card quick-card">
    <h3 class="card-title">快捷入口</h3>
    <div class="quick-grid">
      <button v-for="item in items" :key="item.key" type="button" class="quick-item" @click="onClick(item.label)">
        <div class="quick-icon" :style="{ background: item.color }">
          <el-icon :size="16"><component :is="item.icon" /></el-icon>
        </div>
        <span>{{ item.label }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { PieChart, Reading, Setting } from '@element-plus/icons-vue'

const items = [
  { key: 'stats', label: '训练数据统计', icon: PieChart, color: 'linear-gradient(135deg, #0066ff, #3d8bfd)' },
  { key: 'knowledge', label: '个人知识库', icon: Reading, color: 'linear-gradient(135deg, #7c3aed, #a78bfa)' },
  { key: 'settings', label: '系统设置', icon: Setting, color: 'linear-gradient(135deg, #ea580c, #fb923c)' },
]

const onClick = (label: string) => {
  ElMessage.info(`${label}功能开发中`)
}
</script>

<style scoped lang="scss">
.quick-card {
  height: 100%;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

.card-title {
  margin: 0 0 6px;
  font-size: 12px;
  font-weight: 700;
  color: #1f2937;
  flex-shrink: 0;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 4px;
  flex: 1;
  align-content: start;
}

.quick-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 2px;
  border: none;
  border-radius: 6px;
  background: transparent;
  cursor: pointer;

  span {
    font-size: 9px;
    color: #4b5563;
    text-align: center;
    line-height: 1.15;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 100%;
  }

  &:hover {
    background: #f9fafb;
  }
}

.quick-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  color: #fff;
  flex-shrink: 0;
}
</style>
