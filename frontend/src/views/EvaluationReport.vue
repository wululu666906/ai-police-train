<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const report = ref<any>(null)
const loading = ref(true)

onMounted(() => {
  const data = localStorage.getItem('last_evaluation')
  if (data) {
    report.value = JSON.parse(data)
    loading.value = false
  } else {
    loading.value = false
  }
})

const getScoreColor = (score: number, full: number) => {
  const ratio = score / full
  if (ratio >= 0.9) return 'text-green-600'
  if (ratio >= 0.7) return 'text-blue-600'
  if (ratio >= 0.6) return 'text-orange-500'
  return 'text-red-600'
}

const getPercentage = (score: number, full: number) => (score / full) * 100
</script>

<template>
  <div class="h-screen bg-[#F2F3F5] overflow-y-auto flex flex-col font-sans">
    <header class="bg-[#1D3557] text-white p-6 shadow-xl flex-shrink-0 relative overflow-hidden">
        <div class="absolute right-[-20px] top-[-20px] opacity-10">
           <van-icon name="medal" size="160" />
        </div>
        <div class="flex items-center space-x-4 mb-6 relative z-10">
            <div class="bg-white/20 p-2 rounded-lg backdrop-blur-md cursor-pointer" @click="router.push('/admin/cases')">
                <van-icon name="arrow-left" />
            </div>
            <h1 class="text-xl font-bold">演习训练考核报告</h1>
        </div>

        <div class="flex flex-col items-center py-6 relative z-10">
            <p class="text-blue-200 text-xs uppercase tracking-widest mb-1">Total Score</p>
            <div class="text-6xl font-black italic tracking-tighter drop-shadow-md">
                {{ report?.total_score || 0 }}<span class="text-xl not-italic ml-1">Pts</span>
            </div>
            <div class="mt-4 px-6 py-1.5 bg-white/10 rounded-full border border-white/20 text-xs backdrop-blur-sm">
                综合评估：<span class="font-bold text-yellow-400">{{ report?.total_score >= 90 ? '卓越' : (report?.total_score >= 80 ? '优秀' : '合格') }}</span>
            </div>
        </div>
    </header>
    
    <div v-if="loading" class="flex flex-col items-center justify-center py-20">
      <van-loading color="#1D3557" vertical>分析成绩中...</van-loading>
    </div>
    
    <div v-else-if="report" class="flex-1 p-6 space-y-6 max-w-4xl mx-auto w-full">
      <!-- 维度得分详情 -->
      <section class="space-y-4">
        <h3 class="text-gray-800 font-bold flex items-center px-2">
            <span class="w-1 h-4 bg-[#1D3557] mr-2 rounded-full"></span>
            多维度量化考核
        </h3>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div v-for="s in report.scores" :key="s.dimension" class="bg-white p-5 rounded-2xl shadow-sm border border-gray-100 flex flex-col justify-between">
                <div>
                    <div class="flex justify-between items-start mb-2">
                        <span class="text-sm font-bold text-gray-700">{{ s.dimension }}</span>
                        <span class="text-xs font-black" :class="getScoreColor(s.score, s.full_score)">
                            {{ s.score }}/{{ s.full_score }}
                        </span>
                    </div>
                    <p class="text-xs text-gray-400 leading-relaxed min-h-[32px]">{{ s.reason }}</p>
                </div>
                <div class="mt-4 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div 
                        class="h-full bg-[#457B9D] transition-all duration-1000"
                        :style="{ width: getPercentage(s.score, s.full_score) + '%' }"
                    ></div>
                </div>
            </div>
        </div>
      </section>
      
      <!-- 亮点与改进 -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div class="bg-white rounded-2xl shadow-sm border-t-4 border-green-500 p-6">
           <div class="flex items-center text-green-600 font-bold mb-4">
              <van-icon name="checked" class="mr-2" size="20" />
              表现亮点 (Strengths)
           </div>
           <ul class="space-y-3">
              <li v-for="item in report.strengths" :key="item" class="text-sm text-gray-600 flex items-start">
                  <span class="inline-block w-1.5 h-1.5 rounded-full bg-green-200 mr-2 mt-1.5 flex-shrink-0"></span>
                  {{ item }}
              </li>
           </ul>
        </div>
        
        <div class="bg-white rounded-2xl shadow-sm border-t-4 border-orange-400 p-6">
           <div class="flex items-center text-orange-500 font-bold mb-4">
              <van-icon name="warning" class="mr-2" size="20" />
              改进空间 (Improvements)
           </div>
           <ul class="space-y-3">
              <li v-for="item in report.improvements" :key="item" class="text-sm text-gray-600 flex items-start">
                  <span class="inline-block w-1.5 h-1.5 rounded-full bg-orange-100 mr-2 mt-1.5 flex-shrink-0"></span>
                  {{ item }}
              </li>
           </ul>
        </div>
      </div>
      
      <!-- 专家评语 -->
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 relative">
        <van-icon name="chat" class="absolute right-8 top-8 text-gray-100" size="60" />
        <h3 class="font-bold text-[#1D3557] mb-4">专家点评总结</h3>
        <p class="text-gray-500 text-sm leading-loose italic relative z-10">
          "{{ report.suggestions }}"
        </p>
      </div>
      
      <!-- Actions -->
      <div class="flex space-x-4 pt-4 pb-12">
        <van-button 
            block 
            round 
            class="!border-gray-200 !text-gray-600 !bg-white hover:!bg-gray-50 h-12" 
            @click="router.push('/admin/cases')"
        >
            返回剧本库
        </van-button>
        <van-button 
            block 
            round 
            type="primary" 
            class="!bg-[#1D3557] !border-none h-12 shadow-lg shadow-blue-900/10" 
            @click="router.back()"
        >
            再次演练挑战
        </van-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.grid > div {
    animation: slideUp 0.5s ease-out forwards;
    opacity: 0;
}

@keyframes slideUp {
    from {
        opacity: 0;
        transform: translateY(20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}
</style>

<style>
.van-nav-bar__title { color: white !important; }
.van-nav-bar .van-icon { color: #64748b !important; }
</style>
