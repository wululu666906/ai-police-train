<template>
  <div class="p-4 text-white pb-20">
      <div class="flex justify-between items-center mb-4">
        <h2 class="text-white text-lg font-bold">案件剧本库</h2>
        <van-button 
          type="primary" 
          size="small" 
          icon="plus" 
          class="!bg-indigo-600 !border-none !rounded-full"
          @click="showAdd = true"
        >
          录入案件
        </van-button>
      </div>
      
      <div class="space-y-3">
        <div v-for="c in cases" :key="c.id" class="bg-slate-800 p-4 rounded-xl border border-slate-700 shadow-lg">
          <div class="flex justify-between items-start mb-2">
            <h3 class="text-white font-medium truncate pr-2">{{c.title}}</h3>
            <span class="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs rounded">{{c.case_type}}</span>
          </div>
          <div class="flex justify-between items-center text-slate-400 text-sm mt-3">
            <span class="flex items-center"><van-icon name="cluster-o" class="mr-1" />包含 {{c.scenes?.length || 0}} 个场景</span>
            <span>{{new Date(c.created_at).toLocaleDateString()}}</span>
          </div>
        </div>
      </div>

      <!-- 录入案件弹出层 -->
      <van-popup v-model:show="showAdd" position="bottom" round class="!bg-slate-900 border-t border-slate-800">
        <div class="p-6">
          <div class="flex justify-between items-center mb-6">
            <h3 class="text-white text-lg font-bold">录入新警情剧本</h3>
            <van-icon name="cross" class="text-slate-500" @click="showAdd = false"/>
          </div>
          <van-cell-group inset class="!bg-slate-800 !mx-0">
            <van-field v-model="newCase.title" label="标题" placeholder="例如：东二环路口斗殴" class="!bg-transparent !text-white"/>
            <van-field v-model="newCase.case_type" label="类型" placeholder="纠纷/打架/盗窃" class="!bg-transparent !text-white"/>
            <van-field v-model="newCase.background" label="背景" type="textarea" rows="3" placeholder="详细描述警情背景..." class="!bg-transparent !text-white"/>
          </van-cell-group>
          <div class="mt-8">
            <van-button block round type="primary" class="!bg-indigo-600 !border-none" @click="submitCase">确认提交</van-button>
          </div>
        </div>
      </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import request from '../utils/request'
import { showToast } from 'vant'

const cases = ref<any[]>([])
const showAdd = ref(false)
const newCase = ref({
  title: '',
  case_type: '打架斗殴',
  background: ''
})

const fetchCases = async () => {
  try {
    const res: any = await request.get('/cases/')
    cases.value = res
  } catch (e) {
    console.error('Fetch cases error:', e)
  }
}

const submitCase = async () => {
  if (!newCase.value.title || !newCase.value.background) {
    showToast('请填写完整信息')
    return
  }
  try {
    await request.post('/cases/', {
      ...newCase.value,
      scenes: []
    })
    showToast({ type: 'success', message: '录入成功' })
    showAdd.value = false
    fetchCases()
  } catch (e) {
    console.error('Submit case error:', e)
  }
}

onMounted(fetchCases)
</script>
