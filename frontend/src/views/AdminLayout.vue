<template>
  <div class="flex h-screen bg-[#F2F3F5]">
    <aside class="w-[240px] bg-[#1D3557] flex flex-col shadow-xl z-20">
      <div class="p-6">
        <h1 class="text-white text-xl font-bold flex items-center">
          <van-icon name="shield-reveal-o" class="mr-2" />
          警情模拟平台
        </h1>
        <p class="text-blue-300/60 text-xs mt-1 uppercase tracking-wider">Management Terminal</p>
      </div>

      <nav class="flex-1 mt-4 px-3 space-y-1">
        <div
          v-for="item in navItems"
          :key="item.name"
          @click="onChange(item.name)"
          :class="[
            'flex items-center px-4 py-3 rounded-lg cursor-pointer transition-all duration-200',
            active === item.name
              ? 'bg-[#457B9D] text-white shadow-lg'
              : 'text-blue-100/70 hover:bg-white/5 hover:text-white'
          ]"
        >
          <van-icon :name="item.icon" class="text-lg mr-3" />
          <span class="font-medium">{{ item.label }}</span>
        </div>
      </nav>

      <div class="p-4 border-t border-white/5">
        <div class="flex items-center px-4 py-3 text-blue-100/50 hover:text-white cursor-pointer" @click="router.push('/login')">
          <van-icon name="log-out" class="mr-3" />
          <span>退出系统</span>
        </div>
      </div>
    </aside>

    <main class="flex-1 flex flex-col overflow-hidden">
      <header class="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-8 flex-shrink-0">
        <div class="flex items-center">
          <van-icon name="bars" class="text-gray-400 mr-4 cursor-pointer hover:text-blue-600 transition-colors" />
          <h2 class="text-gray-700 font-bold text-lg">{{ getTitle() }}</h2>
        </div>
        <div class="flex items-center space-x-6">
          <van-button
            size="small"
            plain
            type="primary"
            icon="exchange"
            @click="router.push('/student/hall')"
            class="!rounded-full !px-6 !border-blue-100 !text-blue-600 hover:!bg-blue-50 transition-all shadow-sm font-bold"
          >
            进入学员端演练
          </van-button>
          <div class="text-right">
            <p class="text-sm font-bold text-gray-700">超级管理员</p>
            <p class="text-xs text-gray-400">admin@police.gov.cn</p>
          </div>
          <van-image round width="40" height="40" src="https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg" />
        </div>
      </header>

      <div class="flex-1 overflow-y-auto p-8">
        <router-view :key="route.path" v-slot="{ Component }">
          <transition name="fade-slide" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const active = ref('cases')

const navItems = [
  { name: 'dashboard', label: '数据总览', icon: 'bar-chart-o' },
  { name: 'cases', label: '案件剧本库', icon: 'orders-o' },
  { name: 'data-quality', label: '数据质检', icon: 'warning-o' },
  { name: 'knowledge', label: '知识库管理', icon: 'cluster-o' },
  { name: 'roles', label: 'AI角色库', icon: 'friends-o' },
  { name: 'profile', label: '个人中心', icon: 'user-o' }
]

watch(() => route.path, (val) => {
  if (val.includes('/dashboard')) active.value = 'dashboard'
  else if (val.includes('/cases')) active.value = 'cases'
  else if (val.includes('/data-quality')) active.value = 'data-quality'
  else if (val.includes('/knowledge')) active.value = 'knowledge'
  else if (val.includes('/roles')) active.value = 'roles'
  else if (val.includes('/profile')) active.value = 'profile'
}, { immediate: true })

const onChange = (name: string) => {
  router.push(`/admin/${name}`)
}

const getTitle = () => {
  return navItems.find(i => i.name === active.value)?.label || '管理后台'
}
</script>

<style scoped>
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.3s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateX(10px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-10px);
}
</style>
