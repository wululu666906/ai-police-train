<template>
  <aside class="student-sidebar">
    <div class="sidebar-brand flx-align-center">
      <div class="brand-icon">
        <el-icon :size="22"><Medal /></el-icon>
      </div>
      <span class="brand-text">警情训练系统</span>
    </div>

    <nav class="sidebar-nav">
      <template v-for="item in menuItems" :key="item.key">
        <el-tooltip v-if="item.disabled" content="功能开发中" placement="right">
          <button type="button" class="nav-item nav-item--disabled" disabled>
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.label }}</span>
            <el-icon v-if="item.hasChildren" class="nav-arrow"><ArrowDown /></el-icon>
          </button>
        </el-tooltip>
        <button
          v-else
          type="button"
          class="nav-item"
          :class="{ 'nav-item--active': isActive(item.path, item.activePaths) }"
          @click="go(item.path)"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
          <el-icon v-if="item.hasChildren" class="nav-arrow"><ArrowDown /></el-icon>
        </button>
      </template>
    </nav>

    <div class="sidebar-promo">
      <div class="promo-shield">
        <el-icon :size="36"><Medal /></el-icon>
      </div>
      <p class="promo-title">守护训练公正-提升实战能力</p>
      <p class="promo-sub">科技赋能训练管理</p>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { Aim, ArrowDown, Clock, Files, Grid, Medal, Reading, Setting, VideoPlay } from '@element-plus/icons-vue'

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

const menuItems = rawMenuItems.filter((item) => !['videos', 'face-demo'].includes(item.key))

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
  width: 220px;
  min-height: 100vh;
  flex-shrink: 0;
  background: var(--student-sidebar-bg, #001529);
  color: rgba(255, 255, 255, 0.85);
}

.sidebar-brand {
  gap: 10px;
  padding: 18px 16px 20px;
}

.brand-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: rgba(0, 102, 255, 0.2);
  color: #fff;
}

.brand-text {
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  white-space: nowrap;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 0 12px;
  flex: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 11px 14px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: rgba(255, 255, 255, 0.72);
  font-size: 14px;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s, color 0.15s;

  span {
    flex: 1;
  }

  &:hover:not(:disabled) {
    color: #fff;
    background: rgba(255, 255, 255, 0.08);
  }

  &--active {
    color: #fff !important;
    background: var(--student-sidebar-active, #0066ff) !important;
    font-weight: 600;
  }

  &--disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
}

.nav-arrow {
  font-size: 12px;
  opacity: 0.6;
}

.sidebar-promo {
  margin: 16px 12px 20px;
  padding: 18px 14px;
  border-radius: 10px;
  background: linear-gradient(145deg, #0a2a5e 0%, #0d3d7a 100%);
  text-align: center;
}

.promo-shield {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  margin: 0 auto 12px;
  border-radius: 50%;
  background: radial-gradient(circle at 30% 30%, #3d8bfd, #0066ff 60%, #0044aa);
  color: #fff;
  box-shadow: 0 8px 24px rgba(0, 102, 255, 0.35);
}

.promo-title {
  margin: 0 0 6px;
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.92);
  line-height: 1.5;
}

.promo-sub {
  margin: 0;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.55);
}

@media (max-width: 960px) {
  .student-sidebar {
    width: 72px;
  }

  .brand-text,
  .nav-item span,
  .nav-arrow,
  .sidebar-promo {
    display: none;
  }

  .sidebar-brand {
    justify-content: center;
    padding-inline: 8px;
  }

  .nav-item {
    justify-content: center;
    padding-inline: 10px;
  }
}
</style>
