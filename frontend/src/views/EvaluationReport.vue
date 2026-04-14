<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Circle, Progress } from 'vant'

const router = useRouter()
const route = useRoute()
const report = ref<any>(null)
const loading = ref(true)

onMounted(() => {
  // 从路由或本地缓存获取报告数据
  const data = localStorage.getItem('last_evaluation_report')
  if (data) {
    report.value = JSON.parse(data)
    loading.value = false
  } else {
    // 兜底逻辑
    loading.value = false
  }
})

const getGradeColor = (grade: string) => {
  if (grade === 'S') return 'text-yellow-400'
  if (grade === 'A') return 'text-green-400'
  if (grade === 'B') return 'text-blue-400'
  return 'text-red-400'
}
</script>

<template>
  <div class="h-screen bg-slate-900 overflow-y-auto pb-12">
    <van-nav-bar 
      title="演练评估报告" 
      left-arrow 
      @click-left="router.push('/cases')"
      class="!bg-transparent !border-none"
    />
    
    <div v-if="loading" class="flex flex-col items-center justify-center py-20">
      <van-loading color="#818cf8" vertical>AI 评分生成中...</van-loading>
    </div>
    
    <div v-else-if="report" class="px-6 space-y-6">
      <!-- 总体评价头 -->
      <div class="bg-gradient-to-b from-indigo-900/40 to-slate-900 rounded-3xl p-8 border border-indigo-500/30 text-center relative overflow-hidden">
        <div class="absolute top-0 right-0 p-8 transform rotate-12 opacity-10">
          <van-icon name="medal" size="120" color="#fff" />
        </div>
        
        <div class="text-slate-400 text-sm mb-2 uppercase tracking-widest">Training Grade</div>
        <div class="text-7xl font-black mb-4 italic" :class="getGradeColor(report.grade)">
          {{report.grade}}
        </div>
        <div class="text-white text-xl font-bold">最终得分：{{report.overall_score}}</div>
      </div>
      
      <!-- 维度得分 (代替雷达图) -->
      <div class="bg-slate-800/50 rounded-2xl p-6 border border-slate-700/50">
        <h3 class="text-white text-sm font-bold mb-4 flex items-center">
          <van-icon name="chart-trending-o" class="mr-2 text-indigo-400" />
          多维评价指标
        </h3>
        <div class="space-y-4">
          <div v-for="(val, key) in report.dimensions" :key="key">
            <div class="flex justify-between text-xs text-slate-400 mb-1 capitalize">
              <span>{{key.replace('_', ' ')}}</span>
              <span>{{val}}%</span>
            </div>
            <van-progress 
              :percentage="val" 
              stroke-width="6" 
              :color="'linear-gradient(to right, #6366f1, #a855f7)'"
              track-color="#1e293b"
              :show-pivot="false"
            />
          </div>
        </div>
      </div>
      
      <!-- 亮点与改进 -->
      <div class="grid grid-cols-1 gap-4">
        <div class="bg-green-500/10 border border-green-500/20 rounded-xl p-4">
          <div class="text-green-400 text-xs font-bold mb-2 flex items-center">
            <van-icon name="success" class="mr-1"/> 表现亮点
          </div>
          <ul class="text-slate-300 text-sm space-y-1.5 list-disc list-inside">
            <li v-for="h in report.highlights" :key="h">{{h}}</li>
          </ul>
        </div>
        
        <div class="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
          <div class="text-red-400 text-xs font-bold mb-2 flex items-center">
            <van-icon name="warning-o" class="mr-1"/> 改进建议
          </div>
          <ul class="text-slate-300 text-sm space-y-1.5 list-disc list-inside">
            <li v-for="s in report.shortcomings" :key="s">{{s}}</li>
          </ul>
        </div>
      </div>
      
      <!-- 教官点评 -->
      <div class="bg-slate-800 p-5 rounded-xl border-l-4 border-indigo-500">
        <div class="text-indigo-400 text-xs font-bold mb-1">教官总结：</div>
        <div class="text-slate-200 text-sm italic leading-relaxed">
          "{{report.suggestion}}"
        </div>
      </div>
      
      <div class="flex space-x-3 pt-4 pb-8">
        <van-button block round class="!bg-slate-700 !border-none !text-slate-200" @click="router.push('/cases')">返回剧本集</van-button>
        <van-button block round type="primary" class="!bg-indigo-600 !border-none" @click="router.back()">重新演练</van-button>
      </div>
    </div>
  </div>
</template>

<style>
.van-nav-bar__title { color: white !important; }
.van-nav-bar .van-icon { color: #64748b !important; }
</style>
