<template>
  <div class="h-screen bg-slate-900 pb-12 flex flex-col">
    <van-nav-bar 
      :title="getTitle()" 
      :border="false"
      class="!bg-slate-900 nav-dark flex-shrink-0 z-10"
    />
    
    <div class="flex-1 overflow-y-auto relative">
      <router-view v-slot="{ Component }">
        <transition name="van-fade">
          <component :is="Component" />
        </transition>
      </router-view>
    </div>
    
    <van-tabbar v-model="active" @change="onChange" class="!bg-slate-900 !border-t !border-slate-800" active-color="#818cf8" inactive-color="#64748b">
      <van-tabbar-item name="cases" icon="orders-o">案件管理</van-tabbar-item>
      <van-tabbar-item name="roles" icon="friends-o">账号角色</van-tabbar-item>
      <van-tabbar-item name="dashboard" icon="bar-chart-o">数据知识</van-tabbar-item>
      <van-tabbar-item name="profile" icon="user-o">我的</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const active = ref('cases')

// 同步路由状态到 tabbar
watch(() => route.path, (val) => {
  if (val.includes('/cases')) active.value = 'cases'
  else if (val.includes('/roles')) active.value = 'roles'
  else if (val.includes('/dashboard')) active.value = 'dashboard'
  else if (val.includes('/profile')) active.value = 'profile'
}, { immediate: true })

const onChange = (name: string) => {
  router.push(`/admin/${name}`)
}

const getTitle = () => {
  switch (active.value) {
    case 'cases': return '案件与场景管理';
    case 'roles': return '角色与属性配置';
    case 'dashboard': return '知识库与数据监控';
    case 'profile': return '警员中心';
    default: return '控制台';
  }
}
</script>

<style>
.nav-dark .van-nav-bar__title {
  color: white !important;
}
.van-tabbar {
  z-index: 50;
}
</style>
