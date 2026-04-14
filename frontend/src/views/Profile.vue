<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const user = ref({
  name: localStorage.getItem('username') || '警员张三',
  role: '超级管理员',
  avatar: 'https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg'
})

const doLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  router.push('/login')
}
</script>

<template>
  <div class="p-4 text-white pb-20">
    <!-- 用户卡片 -->
    <div class="bg-gradient-to-r from-blue-600 to-indigo-600 rounded-2xl p-6 shadow-lg mb-6 flex items-center space-x-4">
      <div class="w-16 h-16 rounded-full border-2 border-white/30 overflow-hidden">
        <img :src="user.avatar" class="w-full h-full object-cover"/>
      </div>
      <div>
        <h2 class="text-xl font-bold">{{user.name}}</h2>
        <div class="text-blue-200 text-sm mt-1 px-2 py-0.5 bg-black/20 rounded-full inline-block">{{user.role}}</div>
      </div>
    </div>
    
    <van-cell-group inset class="!bg-slate-800 !border-none custom-group mb-6">
      <van-cell title="系统设置" is-link icon="setting-o" class="!bg-transparent !text-slate-200 border-b border-slate-700/50"/>
      <van-cell title="操作日志" is-link icon="orders-o" class="!bg-transparent !text-slate-200 border-b border-slate-700/50"/>
      <van-cell title="切换为学员模式" is-link icon="exchange" class="!bg-transparent !text-slate-200" @click="$router.push('/training/1')"/>
    </van-cell-group>
    
    <div class="mt-8 px-4">
      <van-button block round type="danger" @click="doLogout" class="!bg-red-500/20 !border-red-500/50 !text-red-400">退出登录</van-button>
    </div>
  </div>
</template>

<style scoped>
:deep(.van-cell__right-icon) {
  color: #64748b !important;
}
:deep(.van-cell__left-icon) {
  color: #818cf8 !important;
}
</style>
