<template>
  <div class="space-y-8 pb-20">
    <!-- Main Stats Header -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <div v-for="s in stats" :key="s.title" class="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 flex items-center space-x-4">
        <div class="w-12 h-12 bg-[#1D3557]/10 flex items-center justify-center rounded-xl text-2xl text-[#1D3557]">
          <van-icon :name="s.icon" />
        </div>
        <div>
          <div class="text-gray-400 text-[10px] font-black uppercase tracking-widest">{{s.title}}</div>
          <div class="text-2xl font-black text-gray-800">{{s.val}}</div>
        </div>
      </div>
    </div>
    
    <!-- Analytics Section -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <!-- Activity Trend -->
      <div class="lg:col-span-2 bg-white rounded-3xl shadow-sm border border-gray-100 p-8">
        <div class="flex items-center justify-between mb-8">
          <h3 class="font-bold text-gray-800 text-lg flex items-center">
            <span class="w-1.5 h-6 bg-[#1D3557] rounded-full mr-3"></span>
            训练活跃度分析 (Activity Trend)
          </h3>
          <div class="flex items-center space-x-2">
            <span class="w-3 h-3 bg-[#457B9D] rounded-sm"></span>
            <span class="text-xs text-gray-400">近 7 日演练次数</span>
          </div>
        </div>
        
        <div class="h-48 flex items-end justify-between px-4 space-x-4">
          <div v-for="(v, i) in [12, 18, 15, 25, 32, 28, 40]" :key="i" class="flex-1 flex flex-col items-center group">
            <div 
              class="w-full bg-[#457B9D]/20 rounded-t-lg group-hover:bg-[#1D3557] transition-all cursor-crosshair relative"
              :style="{ height: (v * 2.5) + 'px' }"
            >
              <div class="opacity-0 group-hover:opacity-100 absolute -top-8 left-1/2 -translate-x-1/2 bg-gray-800 text-white text-[10px] py-1 px-2 rounded whitespace-nowrap z-10 transition-opacity">
                {{v}} 次
              </div>
            </div>
            <span class="text-[10px] text-gray-400 mt-3 font-medium">04-{{10 + i}}</span>
          </div>
        </div>
      </div>

      <!-- Logic Health -->
      <div class="bg-white rounded-3xl shadow-sm border border-gray-100 p-8 flex flex-col">
          <h3 class="font-bold text-gray-800 text-lg mb-6">系统引擎负载</h3>
          <div class="flex-1 flex flex-col justify-center space-y-8">
              <div class="space-y-2">
                  <div class="flex justify-between text-xs font-bold">
                      <span class="text-gray-400">RAG API 响应耗时</span>
                      <span class="text-[#1D3557]">180ms</span>
                  </div>
                  <van-progress :percentage="15" stroke-width="4" color="#1D3557" track-color="#f2f3f5" :show-pivot="false" />
              </div>
              <div class="space-y-2">
                  <div class="flex justify-between text-xs font-bold">
                      <span class="text-gray-400">向量维度匹配度</span>
                      <span class="text-green-500">98.2%</span>
                  </div>
                  <van-progress :percentage="98" stroke-width="4" color="#10b981" track-color="#f2f3f5" :show-pivot="false" />
              </div>
              <div class="space-y-2">
                  <div class="flex justify-between text-xs font-bold">
                      <span class="text-gray-400">大模型并发占用</span>
                      <span class="text-orange-500">42%</span>
                  </div>
                  <van-progress :percentage="42" stroke-width="4" color="#f59e0b" track-color="#f2f3f5" :show-pivot="false" />
              </div>
          </div>
      </div>
    </div>

    <!-- Bottom Actions -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
      <div class="bg-[#1D3557] rounded-3xl shadow-xl p-8 text-white relative overflow-hidden group cursor-pointer" @click="router.push('/admin/knowledge')">
         <div class="absolute right-[-20px] bottom-[-20px] opacity-10 group-hover:scale-110 transition-transform">
            <van-icon name="cluster" size="180" />
         </div>
         <div class="relative z-10 space-y-4">
            <h3 class="text-xl font-bold flex items-center">
               <van-icon name="points" class="mr-3" /> 强化 AI 知识库
            </h3>
            <p class="text-sm text-blue-200/80 leading-loose max-w-[80%]">
               当前知识库已覆盖核心法条与实务操作，点击前往进行精细化条目管理。
            </p>
            <div class="pt-4 flex items-center text-xs font-black uppercase tracking-widest text-blue-300">
                前往管理 <van-icon name="arrow" class="ml-2" />
            </div>
         </div>
      </div>

      <div class="bg-white rounded-3xl shadow-sm p-8 border border-gray-100 flex flex-col justify-between group cursor-pointer hover:shadow-md transition-all">
        <div>
          <div class="w-14 h-14 bg-indigo-50 border border-indigo-100 rounded-2xl flex items-center justify-center mb-6">
             <van-icon name="idcard" class="text-2xl text-indigo-600" />
          </div>
          <h3 class="font-bold text-gray-800 text-lg mb-2">角色建模中心</h3>
          <p class="text-sm text-gray-400 leading-relaxed">
             配置预设的 AI 人物 archetypes，包括其初始情绪阈值、反抗程度与语言习惯。
          </p>
        </div>
        <div class="pt-6 flex justify-end">
          <van-button 
            plain 
            round 
            size="small"
            class="!border-gray-200 !text-gray-600 px-6 hover:!bg-gray-50 transition-colors"
            @click="router.push('/admin/roles')"
          >
            自定义角色
          </van-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import request from '../utils/request'

const router = useRouter()
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
