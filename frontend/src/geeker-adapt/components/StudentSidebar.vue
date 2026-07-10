<template>
  <aside class="student-sidebar" :class="{ 'student-sidebar--collapsed': collapsed }">
    <div class="sidebar-brand">
      <div class="brand-icon">
        <el-icon :size="22"><Medal /></el-icon>
      </div>
      <div class="brand-copy">
        <span class="brand-text">警情训练系统</span>
        <span class="brand-subtitle">Student Console</span>
      </div>
    </div>

    <nav class="sidebar-nav">
      <template v-for="item in menuItems" :key="item.key">
        <button
          type="button"
          class="nav-item"
          :class="{
            'nav-item--active': !item.disabled && isActive(item.path, item.activePaths),
            'nav-item--disabled': item.disabled,
          }"
          :disabled="item.disabled"
          :title="collapsed ? item.label : ''"
          @click="go(item.path)"
        >
          <span class="nav-icon"><el-icon><component :is="item.icon" /></el-icon></span>
          <span class="nav-label">{{ item.label }}</span>
          <el-icon v-if="item.hasChildren" class="nav-arrow"><ArrowDown /></el-icon>
        </button>
      </template>
    </nav>

    <div class="sidebar-footer">
      <button
        type="button"
        class="nav-item collapse-button"
        :title="collapsed ? '展开导航' : '收起导航'"
        @click="emit('toggle-collapse')"
      >
        <span class="nav-icon">
          <el-icon><component :is="collapsed ? Expand : Fold" /></el-icon>
        </span>
        <span class="nav-label">{{ collapsed ? '展开' : '收起' }}</span>
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { Aim, ArrowDown, Clock, Expand, Files, Fold, Grid, Medal, Reading, Setting, VideoPlay } from '@element-plus/icons-vue'

defineProps<{
  collapsed: boolean
}>()

const emit = defineEmits<{
  (event: 'toggle-collapse'): void
}>()

const route = useRoute()
const router = useRouter()

const rawMenuItems = [
  { key: 'hall', label: '训练大厅', icon: Grid, path: '/student/hall', disabled: false },
  { key: 'videos', label: '视频实训', icon: VideoPlay, path: '/student/videos', disabled: false },
  { key: 'face-demo', label: '人脸核验', icon: Aim, path: '/student/face-demo', disabled: false },
  { key: 'video-history', label: '实训记录', icon: Clock, path: '/student/video-history', disabled: false },
  { key: 'tasks', label: '班级作业', icon: Files, path: '/student/classes', disabled: false },
  { key: 'history', label: '训练历史', icon: Clock, path: '/student/history', disabled: false, activePaths: ['/student/evaluation'] },
  { key: 'knowledge', label: '个人知识库', icon: Reading, path: '', disabled: true },
  { key: 'settings', label: '个人设置', icon: Setting, path: '/student/settings', disabled: false },
]

const menuItems = rawMenuItems.filter((item) => item.key !== 'face-demo')

const isActive = (path?: string, activePaths: string[] = []) =>
  Boolean((path && (route.path === path || route.path.startsWith(`${path}/`))) || activePaths.some((item) => route.path === item))

const go = (path?: string) => {
  if (path && path !== route.path) router.push(path)
}
</script>

<style scoped lang="scss">
.student-sidebar {
  display: flex;
  flex-direction: column;
  width: 160px;
  min-height: 100vh;
  flex-shrink: 0;
  background: var(--police-sidebar-bg, #0f1e3c);
  color: rgba(255, 255, 255, 0.85);
  box-shadow: 0 10px 32px rgba(15, 30, 60, 0.22);
  transition: width 0.38s cubic-bezier(0.22, 1, 0.36, 1);
  will-change: width;

  &--collapsed {
    width: 56px;
  }
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 73px;
  padding: 20px 16px 16px;
  overflow: hidden;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  transition:
    gap 0.26s ease,
    padding 0.26s ease;
}

.student-sidebar--collapsed .sidebar-brand {
  justify-content: center;
  gap: 0;
  padding-inline: 0;
}

.brand-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  border-radius: 8px;
  background: var(--police-primary, #003087);
  color: #fff;
  box-shadow: 0 4px 12px rgba(0, 48, 135, 0.35);
}

.brand-copy {
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  transition:
    max-width 0.32s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.32s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.32s cubic-bezier(0.22, 1, 0.36, 1);
}

.student-sidebar--collapsed .brand-copy {
  width: 0;
  max-width: 0;
  opacity: 0;
  transform: translateX(-4px);
  transition: none;
}

.brand-text {
  display: block;
  overflow: hidden;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.25;
  text-overflow: ellipsis;
}

.brand-subtitle {
  display: block;
  margin-top: 2px;
  color: rgba(219, 234, 254, 0.55);
  font-size: 10px;
  line-height: 1.2;
  text-transform: uppercase;
}

.sidebar-nav {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
  padding: 12px 8px;
  transition: padding 0.26s ease;
}

.student-sidebar--collapsed .sidebar-nav {
  align-items: center;
  padding: 12px 0;
}

.nav-item {
  position: relative;
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 40px;
  padding: 4px 12px;
  overflow: hidden;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: rgba(255, 255, 255, 0.65);
  cursor: pointer;
  font-size: 14px;
  text-align: left;
  transition:
    padding 0.2s ease,
    gap 0.2s ease,
    background-color 0.2s ease,
    color 0.2s ease,
    box-shadow 0.2s ease;

  &:hover:not(:disabled) {
    padding-left: 16px;
    background: #002d6e;
    color: #fff;
  }

  &--active {
    background: var(--police-primary, #003087);
    color: #fff;
    font-weight: 600;
    box-shadow: 0 2px 8px rgba(0, 48, 135, 0.4);
  }

  &--disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}

.student-sidebar--collapsed .nav-item,
.student-sidebar--collapsed .nav-item:hover {
  width: 40px;
  height: 40px;
  grid-template-columns: 1fr;
  justify-items: center;
  gap: 0;
  padding: 0;
}

.nav-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 6px;
  color: rgba(255, 255, 255, 0.72);
  transition:
    background-color 0.2s ease,
    color 0.2s ease;
}

.nav-item:hover:not(:disabled) .nav-icon,
.nav-item--active .nav-icon {
  color: #fff;
}

.nav-item--active .nav-icon {
  background: rgba(255, 255, 255, 0.1);
}

.nav-label,
.nav-arrow {
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  transition:
    max-width 0.2s ease,
    opacity 0.2s ease,
    transform 0.2s ease;
}

.nav-label {
  display: block;
  text-overflow: ellipsis;
}

.nav-arrow {
  position: absolute;
  right: 10px;
  font-size: 12px;
  opacity: 0.6;
}

.student-sidebar--collapsed .nav-label,
.student-sidebar--collapsed .nav-arrow {
  display: block;
  width: 0;
  max-width: 0;
  visibility: hidden;
  opacity: 0;
  transform: translateX(-4px);
  transition: none;
}

.sidebar-footer {
  display: block;
  padding: 12px 12px 16px;
  transition: padding 0.38s cubic-bezier(0.22, 1, 0.36, 1);
}

.student-sidebar--collapsed .sidebar-footer {
  display: flex;
  justify-content: center;
  padding-inline: 0;
}

.collapse-button {
  color: rgba(255, 255, 255, 0.65);
}

@media (max-width: 960px) {
  .student-sidebar {
    width: 56px;
  }

  .sidebar-brand {
    justify-content: center;
    gap: 0;
    padding-inline: 0;
  }

  .brand-copy,
  .nav-label,
  .nav-arrow {
    display: none;
  }

  .sidebar-nav {
    align-items: center;
    padding-inline: 0;
  }

  .nav-item,
  .nav-item:hover {
    width: 40px;
    height: 40px;
    grid-template-columns: 1fr;
    justify-items: center;
    gap: 0;
    padding: 0;
  }

  .sidebar-footer {
    display: none;
  }
}
</style>
