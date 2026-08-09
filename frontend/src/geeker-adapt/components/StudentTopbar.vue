<template>
  <header class="student-topbar flx-align-center">
    <div class="topbar-actions flx-align-center">
      <el-badge :value="notificationCount" :max="99" :hidden="!notificationCount" class="notify-badge">
        <button type="button" class="icon-btn" @click="emit('notify')">
          <el-icon :size="20"><Bell /></el-icon>
        </button>
      </el-badge>

      <div class="user-block flx-align-center">
        <el-avatar :size="40" class="user-avatar">{{ avatarLetter }}</el-avatar>
        <div class="user-meta">
          <span class="user-name">{{ displayName }}</span>
          <span class="user-status flx-align-center">
            <i class="status-dot" />
            学员
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
import { Bell } from '@element-plus/icons-vue'

const props = defineProps<{
  displayName: string
  canBackToAdmin?: boolean
  notificationCount?: number
}>()

const emit = defineEmits<{
  logout: []
  'back-admin': []
  notify: []
}>()

const notificationCount = computed(() => Number(props.notificationCount || 0))
const avatarLetter = computed(() => (props.displayName || '学员').slice(0, 1).toUpperCase())
</script>

<style scoped lang="scss">
.student-topbar {
  justify-content: flex-end;
  gap: 20px;
  height: 82px;
  padding: 14px 28px 12px 0;
  background: transparent;
  border-bottom: none;
  box-shadow: none;
  flex-shrink: 0;
  min-width: 0;
  overflow: visible;
}

.topbar-actions {
  gap: 16px;
  flex: 0 0 auto;
  justify-content: flex-end;
  min-width: 0;
  max-width: 100%;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border: 1px solid rgba(223, 232, 246, 0.86);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
  color: #1f2a44;
  cursor: pointer;
  box-shadow: 0 10px 24px rgba(67, 106, 173, 0.08);
  transition: background 0.15s, color 0.15s, transform 0.15s;

  &:hover {
    background: #eef5ff;
    color: #2463ff;
    transform: translateY(-1px);
  }
}

.notify-badge :deep(.el-badge__content) {
  border: none;
}

.user-block {
  gap: 10px;
  padding: 4px 10px 4px 4px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid rgba(223, 232, 246, 0.86);
  min-width: 0;
  box-shadow: 0 10px 24px rgba(67, 106, 173, 0.08);
}

.user-avatar {
  background: linear-gradient(135deg, #183fa8, #3566f6);
  color: #fff;
  font-weight: 800;
  font-size: 15px;
}

.user-meta {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.user-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  font-weight: 800;
  color: #1f2937;
  line-height: 1.2;
}

.user-status {
  gap: 5px;
  width: fit-content;
  border-radius: 999px;
  padding: 1px 8px;
  background: #eaf1ff;
  font-size: 11px;
  color: #3566f6;
  font-weight: 700;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--student-success, #52c41a);
}

.action-btn {
  height: 36px;
  color: #4a5467 !important;
  border-color: rgba(215, 226, 244, 0.95) !important;
  background: rgba(255, 255, 255, 0.66) !important;
  border-radius: 10px !important;
}

@media (max-width: 960px) {
  .student-topbar {
    height: auto;
    padding: 14px 16px 8px 0;
    align-items: flex-end;
    gap: 12px;
  }

  .topbar-actions {
    flex-wrap: wrap;
  }
}

@media (max-width: 640px) {
  .user-meta {
    display: none;
  }
}
</style>
