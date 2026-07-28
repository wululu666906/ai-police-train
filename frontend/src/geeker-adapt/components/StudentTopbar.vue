<template>
  <header class="student-topbar flx-align-center">
    <nav class="breadcrumb" aria-label="当前位置">
      <template v-for="(item, index) in breadcrumbItems" :key="`${item}-${index}`">
        <span v-if="index" class="breadcrumb-separator">/</span>
        <strong v-if="index === breadcrumbItems.length - 1">{{ item }}</strong>
        <span v-else>{{ item }}</span>
      </template>
    </nav>

    <div class="topbar-actions flx-align-center">
      <el-badge :value="notificationCount" :max="99" :hidden="!notificationCount" class="notify-badge">
        <button type="button" class="icon-btn" @click="emit('notify')">
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
import { useRoute } from 'vue-router'
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

const route = useRoute()
const notificationCount = computed(() => Number(props.notificationCount || 0))
const avatarLetter = computed(() => (props.displayName || '学').slice(0, 1).toUpperCase())
const breadcrumbItems = computed(() => {
  const titles = route.matched
    .map((record) => record.meta?.title)
    .filter((title): title is string => typeof title === 'string' && title.trim().length > 0)

  if (titles.length) return titles
  return [String(route.meta?.title || '学生控制台')]
})
</script>

<style scoped lang="scss">
.student-topbar {
  justify-content: space-between;
  height: 56px;
  padding: 0 20px 0 32px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  box-shadow: 0 1px 2px rgb(0 0 0 / 4%);
  flex-shrink: 0;
  min-width: 0;
  overflow: hidden;
}

.breadcrumb {
  display: flex;
  align-items: center;
  flex: 1 1 auto;
  min-width: 0;
  max-width: 100%;
  gap: 8px;
  color: #667085;
  font-size: 14px;

  span,
  strong {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  strong {
    color: #344054;
    font-weight: 600;
  }
}

.breadcrumb-separator {
  flex: 0 0 auto;
  color: #c0c4cc;
}

.topbar-actions {
  gap: 14px;
  flex: 0 1 auto;
  justify-content: flex-end;
  min-width: 0;
  max-width: 100%;
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
  min-width: 0;
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
  min-width: 0;
}

.user-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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

@media (max-width: 760px) {
  .student-topbar {
    height: auto;
    padding: 12px 14px;
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;
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
