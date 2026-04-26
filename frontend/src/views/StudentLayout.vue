<template>
  <div class="student-app">
    <!-- Top Navigation Bar -->
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
          <van-button size="small" plain type="primary" @click="$router.push('/admin/dashboard')" class="!bg-white/10 !border-white/20 !text-white !rounded-full !px-4 mr-2">
            切换到管理端
          </van-button>
          <van-icon name="manager-o" size="18" />
          <span>学员 001</span>
        </div>
      </div>
    </header>

    <!-- Main Content -->
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
import { useRoute } from 'vue-router'

const route = useRoute()

const navItems = [
  { label: '训练大厅', icon: 'apps-o', path: '/student/hall' },
  { label: '训练历史', icon: 'records-o', path: '/student/history' }
]
</script>

<style scoped>
.student-app {
  min-height: 100vh;
  background: #F2F3F5;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Inter', sans-serif;
}

/* Top Navigation */
.top-nav {
  height: 56px;
  background: #0E2F56;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-left .logo {
  display: flex;
  align-items: center;
  gap: 10px;
  color: white;
}

.logo-text {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 1px;
}

.nav-links {
  display: flex;
  gap: 4px;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  border-radius: 4px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 14px;
  text-decoration: none;
  transition: all 0.2s;
}

.nav-link:hover {
  color: white;
  background: rgba(255, 255, 255, 0.08);
}

.nav-link.active {
  color: white;
  background: #165DFF;
}

.nav-right .user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
}

/* Main Content */
.main-content {
  min-height: calc(100vh - 56px);
}

/* Page transition */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.2s ease;
}
.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
}
</style>
