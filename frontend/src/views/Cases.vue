<template>
  <div class="space-y-6">
    <!-- Header Actions -->
    <div class="flex justify-between items-center">
      <div>
        <h1 class="text-2xl font-bold text-gray-800">案件剧本库</h1>
        <p class="text-sm text-gray-500 mt-1">管理及创建用于模拟训练的警情脚本</p>
      </div>
      <van-button 
        type="primary" 
        icon="plus" 
        class="!bg-[#1D3557] !border-none px-6"
        @click="openAddModal"
      >
        录入新案件
      </van-button>
    </div>

    <!-- Case Grid -->
    <div v-if="cases.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
      <div 
        v-for="c in cases" 
        :key="c.id" 
        class="bg-white rounded-[2rem] shadow-sm border border-gray-100 hover:shadow-xl hover:-translate-y-1 transition-all duration-300 p-8 flex flex-col group cursor-pointer"
        @click="editCase(c)"
      >
        <div class="flex justify-between items-start mb-6">
          <div class="w-12 h-12 bg-blue-50 rounded-2xl flex items-center justify-center border border-blue-100/50">
            <van-icon name="balance-o" class="text-xl text-blue-600" />
          </div>
          <van-tag round :type="getTagType(c.case_type)" class="px-3 py-1 font-bold">{{ c.case_type }}</van-tag>
        </div>
        
        <div class="flex-1 mb-6">
          <h3 class="text-lg font-black text-gray-800 leading-tight mb-2 group-hover:text-[#1D3557] transition-colors">
            {{ c.title }}
          </h3>
          <p class="text-[10px] text-gray-300 font-bold uppercase tracking-widest mb-4">CASE_IDENTIFIER: #{{ c.id }}</p>
          <p class="text-gray-500 text-sm line-clamp-2 leading-relaxed italic">
            "{{ c.background || '系统正在等待详细背景注入...' }}"
          </p>
        </div>

        <div class="flex items-center justify-between pt-6 border-t border-gray-50">
          <div class="flex items-center space-x-4">
            <div class="flex flex-col">
                <span class="text-[9px] text-gray-400 font-black uppercase">场景数量</span>
                <span class="text-sm font-bold text-gray-700">{{ c.scenes?.length || 0 }} SCENES</span>
            </div>
          </div>
          <van-button 
            size="small" 
            plain 
            round 
            @click.stop="deleteCase(c)" 
            class="!text-red-400 !border-red-50 !bg-red-50/30 opacity-0 group-hover:opacity-100 transition-opacity"
          >
            移除剧本
          </van-button>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="cases.length === 0" class="py-32 text-center flex flex-col items-center">
        <div class="w-24 h-24 bg-gray-50 rounded-[2.5rem] flex items-center justify-center mb-6 border border-dashed border-gray-200">
            <van-icon name="plus" size="30" class="text-gray-200" />
        </div>
        <h3 class="text-gray-400 font-bold mb-2">暂无剧本数据</h3>
        <p class="text-gray-300 text-xs italic max-w-xs mx-auto">点击右上角“录入新案件”，通过 AI 指导快速生成专业训练剧本。</p>
    </div>

    <!-- Step-by-Step Creation Modal -->
    <van-popup 
      v-model:show="showAdd" 
      position="right" 
      :style="{ width: '600px', height: '100%' }"
      class="flex flex-col"
    >
      <div class="h-16 border-b border-gray-100 flex items-center justify-between px-6 flex-shrink-0 bg-white z-10">
        <h3 class="font-bold text-gray-700">录入新警情剧本</h3>
        <van-icon name="cross" class="cursor-pointer text-gray-400" @click="showAdd = false"/>
      </div>

      <!-- Step Indicator -->
      <div class="px-8 py-6 bg-gray-50/50 flex-shrink-0">
        <van-steps :active="currentStep" active-color="#1D3557">
          <van-step>基础录入</van-step>
          <van-step>AI结构化</van-step>
          <van-step>场景生成</van-step>
        </van-steps>
      </div>

      <div class="flex-1 overflow-y-auto p-8">
        <!-- Step 1: Basic Info -->
        <div v-if="currentStep === 0" class="space-y-6">
          <div class="p-4 bg-blue-50 rounded-lg text-blue-700 text-sm flex items-start leading-relaxed">
            <van-icon name="info" class="mr-2 mt-0.5" />
            您可以手动输入关键信息，或上传一段原始警情描述，让系统为您自动提取。
          </div>
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-bold text-gray-700 mb-2">案件标题</label>
              <input v-model="form.title" type="text" placeholder="例如：某社区邻里纠纷调解" class="w-full px-4 py-2 bg-white border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all outline-none" />
            </div>
            <div>
              <label class="block text-sm font-bold text-gray-700 mb-2">原始描述 / 文本输入</label>
              <textarea v-model="form.rawText" rows="10" placeholder="请在这里粘贴案件原文、审讯笔录或执法记录摘要..." class="w-full px-4 py-3 bg-white border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all outline-none resize-none"></textarea>
            </div>
          </div>
        </div>

        <!-- Step 2: AI Parsing Preview -->
        <div v-if="currentStep === 1" class="space-y-6">
          <div v-if="parsing" class="flex flex-col items-center justify-center py-20 space-y-4">
            <van-loading color="#1D3557" vertical>正在进行AI解析...</van-loading>
            <p class="text-sm text-gray-400">正在提取实体、矛盾冲突及背景信息</p>
          </div>
          <div v-else class="space-y-6 animate-in fade-in duration-500">
            <div class="bg-indigo-50/50 border border-indigo-100 rounded-xl p-5 space-y-4">
              <div class="flex justify-between items-center pb-3 border-b border-indigo-100/50">
                <span class="font-bold text-indigo-900 flex items-center">
                  <van-icon name="award-o" class="mr-2" /> AI 解析结果预览
                </span>
                <van-button size="mini" plain @click="reparse">重新解析</van-button>
              </div>
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <p class="text-xs text-indigo-400 uppercase font-bold">案件类型</p>
                  <p class="text-gray-700 font-medium">{{ aiParsedData.case_type || '-' }}</p>
                </div>
                <div>
                  <p class="text-xs text-indigo-400 uppercase font-bold">涉及人物</p>
                  <div class="flex flex-wrap gap-1 mt-1">
                    <span v-for="p in aiParsedData.persons" :key="p.name" class="px-2 py-0.5 bg-white text-xs rounded border border-indigo-100">
                      {{ p.name }} ({{ p.role }})
                    </span>
                  </div>
                </div>
              </div>
              <div>
                <p class="text-xs text-indigo-400 uppercase font-bold mb-1">冲突焦点</p>
                <ul class="text-sm text-gray-600 list-disc list-inside space-y-1">
                  <li v-for="c in aiParsedData.conflict_points" :key="c">{{ c }}</li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        <!-- Step 3: Scene Generation -->
        <div v-if="currentStep === 2" class="space-y-6">
           <div v-if="generating" class="flex flex-col items-center justify-center py-20 space-y-4">
            <van-loading color="#1D3557" vertical>AI专家正在生成训练场景...</van-loading>
          </div>
          <div v-else class="space-y-4">
             <div v-for="(s, idx) in generatedScenes" :key="idx" class="border border-gray-100 rounded-xl p-4 bg-gray-50">
                <div class="flex justify-between items-start mb-2">
                   <h4 class="font-bold text-gray-700">{{ s.scene_name }}</h4>
                   <van-tag type="primary" plain>{{ s.difficulty }}</van-tag>
                </div>
                <p class="text-sm text-gray-500 mb-2">{{ s.scene_description }}</p>
                <div class="flex gap-2">
                   <span v-for="st in s.stages" :key="st.stage_name" class="px-2 py-0.5 bg-gray-200 text-[10px] rounded text-gray-500">{{ st.stage_name }}</span>
                </div>
             </div>
          </div>
        </div>
      </div>

      <!-- Footer Buttons -->
      <div class="h-20 border-t border-gray-100 px-8 flex items-center justify-between bg-white flex-shrink-0">
        <van-button 
          v-show="currentStep > 0" 
          plain 
          class="!border-gray-200 !text-gray-500 px-8"
          @click="currentStep--"
        >
          上一步
        </van-button>
        <div v-show="currentStep === 0"></div>
        
        <van-button 
          type="primary" 
          class="!bg-[#1D3557] !border-none px-12"
          @click="handleNext"
          :loading="parsing || generating"
        >
          {{ currentStep === 2 ? '完成并发布' : '下一步' }}
        </van-button>
      </div>
    </van-popup>

    <!-- Case Detail Modal -->
    <van-popup 
      v-model:show="showDetail" 
      position="right" 
      :style="{ width: '800px', height: '100%' }"
      class="flex flex-col"
    >
      <div class="h-16 border-b border-gray-100 flex items-center justify-between px-6 flex-shrink-0 bg-white z-10">
        <h3 class="font-bold text-gray-700">案件剧本详细摘要</h3>
        <van-icon name="cross" class="cursor-pointer text-gray-400" @click="showDetail = false"/>
      </div>

      <div class="flex-1 overflow-y-auto p-8 bg-[#F8F9FA]">
        <div class="max-w-3xl mx-auto space-y-10 pb-20">
          <!-- Main Title & Meta -->
          <div>
            <div class="flex items-center space-x-3 mb-4">
              <van-tag type="primary" size="large" round>{{ selectedCase?.case_type }}</van-tag>
              <span class="text-xs text-gray-400 font-bold uppercase tracking-widest">ID: #{{ selectedCase?.id }}</span>
            </div>
            <h1 class="text-3xl font-black text-gray-800 leading-tight">{{ selectedCase?.title }}</h1>
          </div>

          <!-- Section: Background -->
          <section class="space-y-4">
            <h4 class="text-xs font-black text-[#1D3557] uppercase tracking-[0.2em] flex items-center leading-none">
              <span class="w-8 h-px bg-[#1D3557]/20 mr-3"></span>  案件背景 (Abstract)
            </h4>
            <div class="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm leading-relaxed text-gray-600 italic">
              "{{ selectedCase?.background }}"
            </div>
          </section>

          <!-- Section: Original Text -->
          <section class="space-y-4">
            <h4 class="text-xs font-black text-gray-400 uppercase tracking-[0.2em] flex items-center leading-none">
              <span class="w-8 h-px bg-gray-200 mr-3"></span> 案件信息原文 (Original Source)
            </h4>
            <div class="bg-gray-100/50 p-6 rounded-2xl border border-gray-100 leading-relaxed text-gray-500 text-sm whitespace-pre-wrap original-source-kaiti">
              {{ getRawText(selectedCase) }}
            </div>
          </section>

          <van-divider />

          <!-- Section: Entities & AI Persona -->
          <section class="space-y-6">
             <h4 class="text-xs font-black text-[#1D3557] uppercase tracking-[0.2em] flex items-center leading-none">
              <span class="w-8 h-px bg-[#1D3557]/20 mr-3"></span>  AI 角色建模 (Personas)
            </h4>
            <div class="grid grid-cols-1 gap-4">
               <div v-for="role in (getStructuredData(selectedCase).persons || [])" :key="role.name" class="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm group">
                  <div class="flex justify-between items-start mb-4">
                     <div class="flex items-center space-x-3">
                        <div class="w-10 h-10 bg-indigo-50 rounded-xl flex items-center justify-center text-indigo-600 font-bold">
                           {{ role.name[0] }}
                        </div>
                        <div>
                           <div class="font-bold text-gray-800">{{ role.name }}</div>
                           <div class="text-[10px] text-gray-400 uppercase font-black">{{ role.role }}</div>
                        </div>
                     </div>
                     <van-tag plain type="primary">{{ role.role_type || '配合型' }}</van-tag>
                  </div>
                  <div class="space-y-3">
                     <p class="text-xs text-gray-500 leading-relaxed">
                        <span class="font-bold text-gray-700">性格：</span> {{ role.personality }}
                     </p>
                     <div class="flex items-center space-x-4">
                        <div class="flex-1">
                           <div class="flex justify-between text-[9px] font-black text-gray-400 uppercase mb-1">
                              <span>初始情绪</span>
                              <span>{{ role.init_emotion }}%</span>
                           </div>
                           <van-progress :percentage="role.init_emotion" stroke-width="3" :show-pivot="false" color="#f87171" track-color="#fee2e2" />
                        </div>
                        <div class="flex-1">
                           <div class="flex justify-between text-[9px] font-black text-gray-400 uppercase mb-1">
                              <span>初始信任</span>
                              <span>{{ role.init_trust }}%</span>
                           </div>
                           <van-progress :percentage="role.init_trust" stroke-width="3" :show-pivot="false" color="#60a5fa" track-color="#dbeafe" />
                        </div>
                     </div>
                  </div>
               </div>
            </div>
          </section>

          <!-- Section: Training Scenes -->
          <section class="space-y-6">
             <h4 class="text-xs font-black text-[#1D3557] uppercase tracking-[0.2em] flex items-center leading-none">
              <span class="w-8 h-px bg-[#1D3557]/20 mr-3"></span>  内置训练场景 (Scenarios)
            </h4>
            <div class="space-y-4">
               <div v-for="scene in selectedCase?.scenes" :key="scene.id" class="bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
                  <div class="flex justify-between items-center mb-4">
                     <h5 class="font-bold text-gray-800 flex items-center">
                        <van-icon name="play-circle-o" class="mr-2 text-blue-500" /> {{ scene.name }}
                     </h5>
                     <van-tag type="warning" plain size="medium">{{ scene.difficulty }}</van-tag>
                  </div>
                  <p class="text-sm text-gray-500 mb-6 leading-relaxed">{{ scene.description }}</p>
                  <div class="space-y-3">
                     <div v-for="(stage, sidx) in parseStages(scene.stages)" :key="sidx" class="flex items-start space-x-3">
                        <div class="flex flex-col items-center">
                           <div class="w-5 h-5 rounded-full bg-[#1D3557] text-white text-[10px] flex items-center justify-center font-bold">{{ Number(sidx) + 1 }}</div>
                           <div v-if="Number(sidx) < parseStages(scene.stages).length - 1" class="w-px h-8 bg-gray-100 my-1"></div>
                        </div>
                        <div class="flex-1 pt-0.5">
                           <div class="text-xs font-bold text-gray-700">{{ stage.stage_name }}</div>
                           <div class="text-[10px] text-gray-400 mt-1">{{ stage.stage_goal }}</div>
                        </div>
                     </div>
                  </div>
               </div>
            </div>
          </section>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import request from '../utils/request'
import { showToast, showConfirmDialog } from 'vant'

const cases = ref<any[]>([])
const showAdd = ref(false)
const currentStep = ref(0)
const parsing = ref(false)
const generating = ref(false)

const form = reactive({
  title: '',
  rawText: ''
})

const aiParsedData = ref<any>({})
const generatedScenes = ref<any[]>([])

const showDetail = ref(false)
const selectedCase = ref<any>(null)

const fetchCases = async () => {
  try {
    const res: any = await request.get('/cases/')
    cases.value = res
  } catch (e) {
    console.error('Fetch error:', e)
  }
}

const openAddModal = () => {
  showAdd.value = true
  currentStep.value = 0
  form.title = ''
  form.rawText = ''
}

const handleNext = async () => {
  if (currentStep.value === 0) {
    if (!form.title || !form.rawText) return showToast('请填写完整')
    currentStep.value = 1
    startParsing()
  } else if (currentStep.value === 1) {
    currentStep.value = 2
    startGenerating()
  } else {
    submitFinal()
  }
}

const startParsing = async () => {
  parsing.value = true
  try {
    const res: any = await request.post('/cases/parse', { text: form.rawText })
    aiParsedData.value = res
  } catch (e) {
    showToast('AI解析失败')
  } finally {
    parsing.value = false
  }
}

const startGenerating = async () => {
  generating.value = true
  try {
    const res: any = await request.post('/cases/generate-scenes', { case_info: aiParsedData.value })
    generatedScenes.value = res.scenes
  } catch (e) {
    showToast('场景生成失败')
  } finally {
    generating.value = false
  }
}

const submitFinal = async () => {
  try {
    await request.post('/cases/full-create', {
      case: { 
        ...form, 
        ...aiParsedData.value,
        original_content: form.rawText // 显式传递原文
      },
      scenes: generatedScenes.value
    })
    showToast({ type: 'success', message: '发布成功' })
    showAdd.value = false
    fetchCases()
  } catch (e) {
    showToast('发布失败')
  }
}

const getTagType = (type: string) => {
  if (type === '纠纷' || type === '邻里纠纷') return 'success'
  if (type === '打架' || type === '打架斗殴') return 'danger'
  if (type === '盗窃') return 'warning'
  return 'primary'
}

const reparse = () => {
  startParsing()
}

const editCase = (c: any) => {
  selectedCase.value = c
  showDetail.value = true
}

const deleteCase = (c: any) => {
  showConfirmDialog({
    title: '确认删除',
    message: `确定要删除剧本《${c.title}》吗？此操作不可撤销。`,
  }).then(async () => {
    try {
      await request.delete(`/cases/${c.id}`)
      showToast({ type: 'success', message: '剧本已移除' })
      fetchCases()
    } catch (e) {
      showToast('删除失败')
    }
  }).catch(() => {})
}

const getStructuredData = (c: any) => {
  if (!c || !c.structured_data) return {}
  try {
    return typeof c.structured_data === 'string' ? JSON.parse(c.structured_data) : c.structured_data
  } catch (e) {
    return {}
  }
}

const getRawText = (c: any) => {
  if (c && c.original_content) return c.original_content
  const data = getStructuredData(c)
  return data.rawText || '未记录原文'
}

const parseStages = (stagesStr: string) => {
  if (!stagesStr) return []
  try {
    return typeof stagesStr === 'string' ? JSON.parse(stagesStr) : stagesStr
  } catch (e) {
    return []
  }
}



onMounted(fetchCases)
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.original-source-kaiti {
  font-family: "PingFang SC", "Microsoft YaHei", "Heiti SC", "SimHei", sans-serif;
  font-size: 17px;
  line-height: 2.02;
  letter-spacing: 0.02em;
}
</style>
