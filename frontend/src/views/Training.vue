<template>
  <div class="h-screen bg-[#F2F3F5] flex flex-col font-sans">
    <!-- Header: Case Info & Indicators -->
    <header class="bg-[#1D3557] text-white p-4 shadow-lg flex-shrink-0 z-10">
      <div class="flex justify-between items-center mb-4">
        <div class="flex items-center">
          <van-icon name="arrow-left" class="mr-4 cursor-pointer text-blue-200" @click="router.back()" />
          <div>
            <h2 class="font-bold text-lg leading-tight">{{ caseInfo.title }}</h2>
            <p class="text-[10px] text-blue-300 uppercase tracking-widest mt-0.5">Session ID: #{{ sessionId }}</p>
          </div>
        </div>
        <van-button 
          size="small" 
          plain 
          class="!border-red-400 !text-red-400 !bg-transparent hover:!bg-red-500/10"
          @click="finishTraining"
        >
          结束并评分
        </van-button>
      </div>

      <!-- State Indicators -->
      <div class="grid grid-cols-2 gap-4 bg-white/5 rounded-xl p-3 border border-white/10">
        <div class="space-y-1">
          <div class="flex justify-between items-center">
            <span class="text-[10px] text-blue-200 flex items-center"><van-icon name="fire" class="mr-1" /> AI 情绪值</span>
            <span class="text-xs font-bold">{{ currentState.emotion }}%</span>
          </div>
          <div class="h-1.5 bg-white/10 rounded-full overflow-hidden">
            <div 
              class="h-full transition-all duration-500" 
              :class="currentState.emotion > 70 ? 'bg-red-500' : 'bg-orange-400'"
              :style="{ width: currentState.emotion + '%' }"
            ></div>
          </div>
        </div>
        <div class="space-y-1">
           <div class="flex justify-between items-center">
            <span class="text-[10px] text-blue-200 flex items-center"><van-icon name="shield-reveal-o" class="mr-1" /> 训练信任度</span>
            <span class="text-xs font-bold">{{ currentState.trust }}%</span>
          </div>
          <div class="h-1.5 bg-white/10 rounded-full overflow-hidden">
            <div 
              class="h-full bg-green-400 transition-all duration-500"
              :style="{ width: currentState.trust + '%' }"
            ></div>
          </div>
        </div>
      </div>
    </header>

    <!-- Chat History -->
    <div class="flex-1 overflow-y-auto p-6 space-y-6" ref="chatContainer">
      <div v-for="msg in chatHistory" :key="msg.id">
        <!-- System Message -->
        <div v-if="msg.role === 'system'" class="flex justify-center">
          <span class="px-4 py-1 bg-gray-200/80 text-[11px] text-gray-500 rounded-full border border-gray-300/50 italic">
            {{ msg.content }}
          </span>
        </div>

        <!-- AI Bubble -->
        <div v-else-if="msg.role === 'assistant'" class="flex items-start max-w-[85%] space-x-3 group animate-in slide-in-from-left duration-300">
          <div class="w-10 h-10 rounded-full bg-white border border-gray-200 shadow-sm flex-shrink-0 flex items-center justify-center overflow-hidden">
            <van-icon name="contact" class="text-xl text-[#457B9D]" />
          </div>
          <div class="space-y-1">
            <p class="text-[10px] text-gray-400 font-bold uppercase ml-1">{{ roleInfo.name }}</p>
            <div class="bg-white px-4 py-3 rounded-2xl rounded-tl-none shadow-sm border border-gray-200 text-gray-800 text-sm leading-relaxed relative">
               {{ msg.content }}
               <!-- Bubble tail decoration -->
               <div class="absolute -left-[6px] top-0 w-3 h-3 bg-white border-l border-t border-gray-200 transform -rotate-45"></div>
            </div>
          </div>
        </div>

        <!-- Human Bubble -->
        <div v-else class="flex flex-row-reverse items-start space-x-3 space-x-reverse animate-in slide-in-from-right duration-300">
           <div class="w-10 h-10 rounded-full bg-[#1D3557] border border-blue-400 shadow-md flex-shrink-0 flex items-center justify-center overflow-hidden">
            <van-icon name="friends-o" class="text-xl text-white" />
          </div>
          <div class="space-y-1 flex flex-col items-end">
            <p class="text-[10px] text-gray-400 font-bold uppercase mr-1">训练警员</p>
            <div class="bg-[#457B9D] px-4 py-3 rounded-2xl rounded-tr-none shadow-lg text-white text-sm leading-relaxed relative">
               {{ msg.content }}
               <div class="absolute -right-[6px] top-0 w-3 h-3 bg-[#457B9D] transform rotate-45"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- AI Typing Indicator -->
      <div v-if="isLoading" class="flex items-start max-w-[85%] space-x-3">
         <div class="w-10 h-10 rounded-full bg-white border border-gray-200 shadow-sm flex-shrink-0 flex items-center justify-center">
            <van-icon name="contact" class="text-xl text-[#457B9D]" />
          </div>
          <div class="bg-white px-4 py-3 rounded-2xl rounded-tl-none border border-gray-200 flex items-center space-x-1 shadow-sm">
            <div class="w-1.5 h-1.5 bg-gray-300 rounded-full animate-bounce"></div>
            <div class="w-1.5 h-1.5 bg-gray-300 rounded-full animate-bounce delay-75"></div>
            <div class="w-1.5 h-1.5 bg-gray-300 rounded-full animate-bounce delay-150"></div>
          </div>
      </div>
    </div>

    <!-- Info Progress Drawer Button -->
    <div class="absolute right-6 bottom-28 group">
       <div class="bg-white p-3 rounded-full shadow-xl border border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors" @click="showInfoList = true">
          <van-icon name="notes-o" class="text-xl text-[#1D3557]" />
       </div>
       <div class="absolute right-full mr-3 top-2 bg-gray-800 text-white text-[10px] px-2 py-1 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity">
          已获知关键信息巡查
       </div>
    </div>

    <!-- Input Area -->
    <div class="p-6 bg-white border-t border-gray-200 flex items-center space-x-4 flex-shrink-0">
      <div class="flex-1 bg-gray-100 rounded-xl flex items-center px-4 border border-gray-200 focus-within:border-[#457B9D] focus-within:bg-white transition-all shadow-inner">
        <textarea 
          v-model="inputMessage" 
          rows="1" 
          class="flex-1 bg-transparent py-3 text-gray-700 outline-none text-sm resize-none"
          placeholder="请输入执法话术或提问..."
          @keyup.enter.exact.prevent="sendMessage"
        ></textarea>
      </div>
      <van-button 
        round 
        type="primary" 
        size="normal"
        icon="share-o"
        class="!bg-[#1D3557] !border-none !h-12 !w-12 !min-w-[48px] shadow-lg shadow-blue-900/10 transform rotate-[-45deg]" 
        @click="sendMessage"
        :loading="isLoading"
      />
    </div>

    <!-- Information List Popup -->
    <van-popup v-model:show="showInfoList" position="bottom" round closeable>
      <div class="p-6">
         <h3 class="font-bold text-gray-700 mb-4 border-b pb-2">已查明关键事实</h3>
         <div v-if="revealedInfo.length === 0" class="py-10 text-center text-gray-400 text-sm">
            暂未获取隐藏信息，请尝试通过引导与提问降低对方抵触情绪。
         </div>
         <div v-else class="space-y-3 pb-4">
            <div v-for="(info, index) in revealedInfo" :key="index" class="p-3 bg-green-50 border border-green-100 rounded-lg flex items-start">
               <van-icon name="certificate" class="text-green-500 mr-2 mt-0.5" />
               <span class="text-sm text-green-800">{{ info }}</span>
            </div>
         </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '../utils/request'
import { showToast } from 'vant'

const route = useRoute()
const router = useRouter()

const sessionId = ref(route.params.id)
const inputMessage = ref('')
const isLoading = ref(false)
const showInfoList = ref(false)

const caseInfo = reactive({ title: '加载中...', background: '' })
const roleInfo = reactive({ name: '警情对象' })
const revealedInfo = ref<string[]>([])

const chatHistory = ref<any[]>([
  { id: Date.now(), role: 'system', content: '连接训练引擎中...' }
])

const currentState = ref({
  emotion: 50,
  trust: 30
})

const fetchSessionData = async () => {
  try {
    const res: any = await request.get(`/training/session/${sessionId.value}`)
    caseInfo.title = res.case_title
    caseInfo.background = res.case_background
    roleInfo.name = res.role_name
    currentState.value.emotion = res.current_emotion
    currentState.value.trust = res.current_trust
    revealedInfo.value = JSON.parse(res.revealed_info || '[]')
    
    chatHistory.value = [
      { id: Date.now(), role: 'system', content: `演练已开始。环境：${res.scene_name || '警情现场'}。涉及人员：${res.role_name}。` },
      ...res.messages.map((m: any) => ({
        id: m.id,
        role: m.role === 'user' ? 'human' : 'assistant',
        content: m.content
      }))
    ]
    scrollToBottom()
  } catch (e) {
    showToast('获取训练状态失败')
  }
}

const sendMessage = async () => {
  if (!inputMessage.value.trim() || isLoading.value) return
  
  const msg = inputMessage.value
  chatHistory.value.push({ id: Date.now(), role: 'human', content: msg })
  inputMessage.value = ''
  isLoading.value = true
  
  scrollToBottom()
  
  try {
    const res: any = await request.post(`/training/chat/${sessionId.value}`, {
      role: 'user',
      content: msg
    })
    
    if (res && res.response) {
       chatHistory.value.push({
         id: Date.now(),
         role: 'assistant',
         content: res.response
       })
       currentState.value.emotion = res.updated_emotion
       currentState.value.trust = res.updated_trust
       
       if (res.new_fact_revealed && res.new_fact_revealed !== 'null') {
         showToast({ message: "获得新线索！", icon: "success" })
         revealedInfo.value.push(res.new_fact_revealed)
         chatHistory.value.push({ id: Date.now(), role: 'system', content: `[关键事实获取] ${res.new_fact_revealed}` })
       }
    }
  } catch (e) {
    showToast('AI响应超时')
    chatHistory.value.push({ id: Date.now(), role: 'system', content: '通讯故障，请重试' })
  } finally {
    isLoading.value = false
    scrollToBottom()
  }
}

const finishTraining = async () => {
  try {
    const res = await request.post(`/training/finish/${sessionId.value}`)
    localStorage.setItem('last_evaluation', JSON.stringify(res))
    router.push('/admin/evaluation') // Redirect to evaluation report
  } catch (e) {
    showToast('生成报告失败')
  }
}

const chatContainer = ref<HTMLElement | null>(null)
const scrollToBottom = () => {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

onMounted(fetchSessionData)
</script>

<style scoped>
.延时渲染 {
  animation: fadeIn 0.5s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* Scrollbar styling */
::-webkit-scrollbar {
  width: 4px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
</style>
