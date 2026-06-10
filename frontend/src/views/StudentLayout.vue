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
  background: #fff;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif;
  overflow-x: hidden;
}

.top-nav {
  height: 56px;
  background: linear-gradient(90deg, #05204a 0%, #082a63 55%, #05204a 100%);
  border-bottom: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  box-shadow: 0 2px 10px rgba(15, 30, 60, 0.12);
  position: sticky;
  top: 0;
  z-index: 100;
  gap: 14px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #fff;
}

.logo-text {
  font-size: 14px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0;
  white-space: nowrap;
}

.nav-links {
  display: flex;
  justify-content: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.nav-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 38px;
  padding: 0 18px;
  border-radius: 999px;
  color: rgba(255, 255, 255, 0.68);
  font-size: 14px;
  font-weight: 700;
  text-decoration: none;
  transition: all 0.2s ease;
}

.nav-link:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.1);
}

.nav-link.active {
  color: #fff;
  background: #1677ff;
  box-shadow: 0 8px 20px rgba(22, 119, 255, 0.28);
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
  color: rgba(255, 255, 255, 0.78);
  font-size: 13px;
  white-space: nowrap;
}

.logout-btn,
.back-admin-btn {
  height: 32px !important;
  border-radius: 999px !important;
  border-color: rgba(255, 255, 255, 0.24) !important;
  color: rgba(255, 255, 255, 0.88) !important;
  background: rgba(255, 255, 255, 0.08) !important;
}

.main-content {
  min-height: calc(100vh - 52px);
  background: #fff;
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
