<template>
  <div class="student-app">
    <header class="top-nav">
      <div class="nav-left">
        <div class="logo">
          <van-icon name="shield-o" size="22" />
          <span class="logo-text">警情模拟训练系统</span>
        </div>
      </div>

      <nav class="nav-links">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-link"
          :class="{ active: route.path === item.path }"
        >
          <van-icon :name="item.icon" />
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="nav-right">
        <div class="user-info">
          <van-icon name="manager-o" size="18" />
          <span>{{ displayName }}</span>
        </div>
        <van-button
          v-if="canBackToAdmin"
          size="small"
          plain
          icon="wap-home-o"
          class="back-admin-btn"
          @click="router.push('/admin/dashboard')"
        >
          返回管理端
        </van-button>
        <van-button size="small" plain icon="revoke" class="logout-btn" @click="logout">
          退出登录
        </van-button>
      </div>
    </header>

    <main class="main-content">
      <router-view v-slot="{ Component }">
        <transition name="page-fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { clearAuth } from '../utils/auth'

const route = useRoute()
const router = useRouter()

const displayName = computed(() => localStorage.getItem('username') || '学员')
const canBackToAdmin = computed(() => localStorage.getItem('role') === 'admin')

const navItems = [
  { label: '训练大厅', icon: 'apps-o', path: '/student/hall' },
  { label: '训练历史', icon: 'records-o', path: '/student/history' },
]

const logout = () => {
  clearAuth()
  router.push('/login')
}
</script>

<style scoped>
.student-app {
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(22, 93, 255, 0.08), transparent 22%),
    linear-gradient(180deg, #f4f7fb 0%, #eef3f9 100%);
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif;
  overflow-x: hidden;
}

.top-nav {
  height: 56px;
  background: #0e2f56;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.18);
  position: sticky;
  top: 0;
  z-index: 100;
  gap: 16px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #fff;
}

.logo-text {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.nav-links {
  display: flex;
  gap: 6px;
  min-width: 0;
}

.nav-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 999px;
  color: rgba(255, 255, 255, 0.72);
  font-size: 14px;
  text-decoration: none;
  transition: all 0.2s ease;
}

.nav-link:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.08);
}

.nav-link.active {
  color: #fff;
  background: #165dff;
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  color: rgba(255, 255, 255, 0.76);
  font-size: 13px;
}

.logout-btn,
.back-admin-btn {
  border-radius: 999px !important;
  border-color: rgba(255, 255, 255, 0.18) !important;
  color: #fff !important;
  background: rgba(255, 255, 255, 0.08) !important;
}

.main-content {
  min-height: calc(100vh - 56px);
}

.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s ease;
}

.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
}

@media (max-width: 960px) {
  .top-nav {
    height: auto;
    padding: 12px 14px;
    flex-wrap: wrap;
  }

  .nav-links {
    order: 3;
    width: 100%;
    overflow-x: auto;
    padding-bottom: 2px;
  }

  .nav-right {
    margin-left: auto;
  }

  .logo-text {
    font-size: 15px;
  }
}

@media (max-width: 640px) {
  .user-info {
    display: none;
  }

  .nav-link {
    white-space: nowrap;
  }
}
</style>
