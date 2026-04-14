<template>
  <div class="p-4 text-white pb-20">
    <h2 class="text-lg font-bold mb-4">数据总览</h2>
    <!-- 统计板 -->
    <div class="grid grid-cols-2 gap-4 mt-2">
      <div v-for="s in stats" :key="s.title" class="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-sm flex items-center justify-between">
        <div>
          <div class="text-slate-400 text-xs mb-1">{{s.title}}</div>
          <div class="text-2xl font-bold text-indigo-400">{{s.val}}</div>
        </div>
        <van-icon :name="s.icon" class="text-3xl text-slate-600" />
      </div>
    </div>
    
    <div class="mt-8">
      <h3 class="mb-4 text-slate-300 font-semibold">知识库快捷入口</h3>
      <div class="bg-gradient-to-r from-teal-900/40 to-emerald-900/40 border border-teal-500/30 p-4 rounded-xl flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <div class="w-10 h-10 bg-teal-500/20 rounded-full flex items-center justify-center">
            <van-icon name="description" class="text-teal-400 text-xl" />
          </div>
          <div>
            <div class="font-medium">RAG 法律条文库</div>
            <div class="text-xs text-slate-400 mt-0.5">上传或检索现有法条规则</div>
          </div>
        </div>
        <van-icon name="arrow" class="text-slate-500" />
      </div>
      <div class="bg-gradient-to-r from-orange-900/40 to-amber-900/40 border border-orange-500/30 p-4 rounded-xl flex items-center justify-between mt-3">
        <div class="flex items-center space-x-3">
          <div class="w-10 h-10 bg-orange-500/20 rounded-full flex items-center justify-center">
            <van-icon name="chat-o" class="text-orange-400 text-xl" />
          </div>
          <div>
            <div class="font-medium">全局 Prompt 管理</div>
            <div class="text-xs text-slate-400 mt-0.5">定制化 AI 人设和指令模板</div>
          </div>
        </div>
        <van-icon name="arrow" class="text-slate-500" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import request from '../utils/request'

const stats = ref([
  { title: '总案件剧本', key: 'cases', val: 0, icon: 'orders-o' },
  { title: '预置角色数', key: 'roles', val: 0, icon: 'contact-o' },
  { title: 'RAG片段', key: 'rag', val: 0, icon: 'desktop-o' },
  { title: '今日演练', key: 'sessions', val: 0, icon: 'chart-trending-o' },
])

onMounted(async () => {
  try {
    const res: any = await request.get('/dashboard/stats')
    stats.value.forEach(item => {
      if (res[item.key] !== undefined) {
        item.val = res[item.key]
      }
    })
  } catch (e) {
    console.error('Dashboard stats error:', e)
  }
})
</script>
