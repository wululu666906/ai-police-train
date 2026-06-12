<template>
  <header class="student-topbar flx-align-center">
    <div class="topbar-spacer" />

    <div class="topbar-actions flx-align-center">
      <el-badge :value="notificationCount" :max="99" class="notify-badge">
        <button type="button" class="icon-btn" @click="onNotifyClick">
          <el-icon :size="18"><Bell /></el-icon>
        </button>
      </el-badge>

      <div class="user-block flx-align-center">
        <el-avatar :size="32" class="user-avatar">{{ avatarLetter }}</el-avatar>
        <div class="user-meta">
          <span class="user-name">{{ displayName }}</span>
          <span class="user-status flx-align-center">
            <i class="status-dot" />
            在线
          </span>
        </div>
      </div>

      <el-button v-if="canBackToAdmin" size="small" plain class="action-btn" @click="emit('back-admin')">
        返回管理端
      </el-button>
      <el-button size="small" plain class="action-btn" @click="emit('logout')">退出登录</el-button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Bell } from '@element-plus/icons-vue'
import { MOCK_NOTIFICATION_COUNT } from '../../mocks/studentHallMock'

const props = defineProps<{
  displayName: string
  canBackToAdmin?: boolean
}>()

const emit = defineEmits<{
  logout: []
  'back-admin': []
}>()

const notificationCount = MOCK_NOTIFICATION_COUNT
const avatarLetter = computed(() => (props.displayName || '学').slice(0, 1).toUpperCase())

const onNotifyClick = () => {
  ElMessage.info('通知功能开发中')
}
</script>

<style scoped lang="scss">
.student-topbar {
  justify-content: flex-end;
  height: 56px;
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  box-shadow: 0 1px 2px rgb(0 0 0 / 4%);
}

.topbar-spacer {
  flex: 1;
}

.topbar-actions {
  gap: 14px;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 8px;
  background: #f3f4f6;
  color: #4b5563;
  cursor: pointer;
  transition: background 0.15s;

  &:hover {
    background: #e5e7eb;
  }
}

.notify-badge :deep(.el-badge__content) {
  border: none;
}

.user-block {
  gap: 10px;
  padding: 4px 8px;
  border-radius: 8px;
}

.user-avatar {
  background: linear-gradient(135deg, #0066ff, #3d8bfd);
  color: #fff;
  font-weight: 700;
  font-size: 14px;
}

.user-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-name {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.2;
}

.user-status {
  gap: 4px;
  font-size: 11px;
  color: #6b7280;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--student-success, #52c41a);
}

.action-btn {
  color: #374151 !important;
  border-color: #d1d5db !important;
}

@media (max-width: 640px) {
  .user-meta {
    display: none;
  }
}
</style>
