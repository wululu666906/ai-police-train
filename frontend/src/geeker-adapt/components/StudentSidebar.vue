<template>
  <aside class="student-sidebar" :class="{ 'student-sidebar--collapsed': collapsed }">
    <div class="sidebar-brand">
      <div class="brand-icon" aria-hidden="true">
        <svg viewBox="0 0 36 40" role="img">
          <path
            class="brand-shield"
            d="M18 2.8 31.2 7.6v11.3c0 8.3-5.2 15.2-13.2 18.3C10 34.1 4.8 27.2 4.8 18.9V7.6L18 2.8Z"
          />
          <path class="brand-shield-edge" d="M18 6.1 27.8 9.7v8.8c0 6.1-3.7 11.4-9.8 14-6.1-2.6-9.8-7.9-9.8-14V9.7L18 6.1Z" />
          <path class="brand-star" d="m18 9.2 1.4 4.2h4.4l-3.6 2.6 1.4 4.2-3.6-2.6-3.6 2.6 1.4-4.2-3.6-2.6h4.4L18 9.2Z" />
          <circle cx="13" cy="24" r="1.3" />
          <circle cx="18" cy="26" r="1.3" />
          <circle cx="23" cy="24" r="1.3" />
        </svg>
      </div>
      <div class="brand-copy">
        <span class="brand-text">AI虚拟警情模拟训练平台</span>
        <span class="brand-subtitle">学生训练与学习中心</span>
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
          @click="item.key === 'notifications' ? emit('notify') : go(item.path)"
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
        class="student-profile"
        :title="collapsed ? '展开导航' : '收起导航'"
        @click="emit('toggle-collapse')"
      >
        <span class="student-profile__avatar">{{ (displayName || '学员').slice(0, 1) }}</span>
        <span class="student-profile__copy">
          <strong>{{ displayName || '学员' }}</strong>
          <small>学员端</small>
        </span>
        <span class="student-profile__arrow">⌄</span>
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import type { Component } from 'vue'
import { ArrowDown, Bell, Clock, Files, Grid, User, VideoPlay } from '@element-plus/icons-vue'

const { collapsed, displayName } = defineProps<{
  collapsed: boolean
  displayName?: string
}>()

const emit = defineEmits<{
  (event: 'toggle-collapse'): void
  (event: 'notify'): void
}>()

const route = useRoute()
const router = useRouter()

type StudentMenuItem = {
  key: string
  label: string
  icon: Component
  path: string
  disabled: boolean
  activePaths?: string[]
  hasChildren?: boolean
}

const rawMenuItems: StudentMenuItem[] = [
  { key: 'home', label: '首页', icon: Grid, path: '/student/home', disabled: false },
  { key: 'training-center', label: '训练大厅', icon: VideoPlay, path: '/student/training-center', disabled: false, activePaths: ['/student/hall', '/student/training', '/student/videos', '/student/video-training'] },
  { key: 'classes', label: '我的班级', icon: Files, path: '/student/classes', disabled: false },
  { key: 'history', label: '练习记录', icon: Clock, path: '/student/history', disabled: false, activePaths: ['/student/text-history', '/student/video-history', '/student/evaluation'] },
  { key: 'notifications', label: '通知中心', icon: Bell, path: '', disabled: false },
  { key: 'settings', label: '个人中心', icon: User, path: '/student/settings', disabled: false },
]

const menuItems = rawMenuItems

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
  width: 230px;
  min-height: 100vh;
  flex-shrink: 0;
  color: #26334d;
  background: transparent;
  transition: width 0.38s cubic-bezier(0.22, 1, 0.36, 1);
  will-change: width;

  &--collapsed {
    width: 72px;
  }
}

.sidebar-brand {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  min-height: 66px;
  padding: 12px 8px 10px 12px;
  overflow: hidden;
}

.brand-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 38px;
  flex: 0 0 34px;
  color: #fff;
  filter: drop-shadow(0 8px 14px rgba(17, 67, 171, 0.2));
}

.brand-icon svg {
  display: block;
  width: 100%;
  height: 100%;
}

.brand-shield {
  fill: #0b4fbd;
}

.brand-shield-edge {
  fill: none;
  stroke: rgba(255, 255, 255, 0.58);
  stroke-width: 1.2;
}

.brand-star,
.brand-icon circle {
  fill: #fff;
}

.brand-copy {
  min-width: 0;
}

.brand-text,
.brand-subtitle {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.brand-text {
  color: #142552;
  font-size: 15px;
  font-weight: 900;
  line-height: 1.2;
}

.brand-subtitle {
  margin-top: 3px;
  color: #7f8da6;
  font-size: 11px;
  line-height: 1.2;
}

.sidebar-nav {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding: 20px 16px 18px;
}

.student-sidebar--collapsed .sidebar-brand {
  grid-template-columns: 1fr;
  justify-items: center;
  padding-inline: 0;
}

.student-sidebar--collapsed .brand-copy {
  display: none;
}

.student-sidebar--collapsed .sidebar-nav {
  align-items: center;
  padding-inline: 0;
}

.nav-item {
  position: relative;
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 60px;
  padding: 0 16px;
  overflow: hidden;
  border: none;
  border-radius: 16px;
  background: transparent;
  color: #7f8da6;
  cursor: pointer;
  font-size: 16px;
  text-align: left;
  transition: background-color 0.18s ease, color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;

  &:hover:not(:disabled) {
    background: rgba(235, 243, 255, 0.78);
    color: #2463ff;
    transform: translateX(2px);
  }

  &--active {
    background: rgba(231, 240, 255, 0.92);
    color: #155cff;
    font-weight: 800;
    box-shadow: inset 0 0 0 1px rgba(198, 216, 255, 0.84), 0 14px 30px rgba(52, 104, 230, 0.08);
  }

  &--disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}

.student-sidebar--collapsed .nav-item,
.student-sidebar--collapsed .nav-item:hover {
  width: 44px;
  height: 44px;
  min-height: 44px;
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
  border-radius: 10px;
  color: inherit;
}

.nav-label,
.nav-arrow {
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.nav-label {
  display: block;
  text-overflow: ellipsis;
}

.nav-arrow {
  position: absolute;
  right: 12px;
  font-size: 12px;
  opacity: 0.6;
}

.student-sidebar--collapsed .nav-label,
.student-sidebar--collapsed .nav-arrow {
  width: 0;
  max-width: 0;
  visibility: hidden;
  opacity: 0;
  transform: translateX(-4px);
  transition: none;
}

.sidebar-footer {
  display: block;
  padding: 14px 18px 24px;
}

.student-profile {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) 14px;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 52px;
  border: 0;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.68);
  color: inherit;
  cursor: pointer;
  text-align: left;
  box-shadow: 0 12px 28px rgba(67, 106, 173, 0.08);
}

.student-profile__avatar {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #1656d9;
  color: #fff;
  font-size: 15px;
  font-weight: 900;
}

.student-profile__copy {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.student-profile__copy strong,
.student-profile__copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.student-profile__copy strong {
  color: #17213b;
  font-size: 13px;
}

.student-profile__copy small {
  width: fit-content;
  padding: 1px 8px;
  border-radius: 999px;
  background: #eaf1ff;
  color: #3566f6;
  font-size: 11px;
  font-weight: 800;
}

.student-profile__arrow {
  color: #64748b;
  font-size: 18px;
}

.student-sidebar--collapsed .student-profile {
  grid-template-columns: 1fr;
  justify-items: center;
  padding: 0;
}

.student-sidebar--collapsed .student-profile__copy,
.student-sidebar--collapsed .student-profile__arrow {
  display: none;
}

@media (max-width: 960px) {
  .student-sidebar {
    width: 72px;
  }

  .sidebar-brand {
    grid-template-columns: 1fr;
    justify-items: center;
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
    width: 44px;
    height: 44px;
    min-height: 44px;
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
