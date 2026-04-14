<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { showToast } from 'vant'

const route = useRoute()
const router = useRouter()

const sessionId = ref(route.params.id)
const inputMessage = ref('')
const isLoading = ref(false)

const chatHistory = ref([
  { id: 1, role: 'system', content: '您已进入东二环路口打架纠纷现场，本次对象为报警人（情绪激动），请开始您的问话。' }
])

const currentState = ref({
  emotion: 80,
  trust: 20
})

// 发送消息
const sendMessage = async () => {
  if (!inputMessage.value.trim()) return
  
  const msg = inputMessage.value
  chatHistory.value.push({ id: Date.now(), role: 'human', content: msg })
  inputMessage.value = ''
  isLoading.value = true
  
  scrollToBottom()
  
  try {
    // 调用后端 FastAPI 接口
    const res = await axios.post(`http://127.0.0.1:8000/training/chat/${sessionId.value}`, {
      role: 'human',
      content: msg
    })
    
    // 假设 AI 引擎连通，现在先用模拟延迟返回
    if (res.data && !res.data.error) {
       chatHistory.value.push({
         id: Date.now(),
         role: 'ai',
         content: res.data.response || "我不听！你们警察就是不想管事对吧！"
       })
       currentState.value.emotion = res.data.updated_emotion || currentState.value.emotion
       currentState.value.trust = res.data.updated_trust || currentState.value.trust
       
       if (res.data.new_fact_revealed) {
         showToast({ message: "获得新线索！", icon: "success" })
         chatHistory.value.push({ id: Date.now(), role: 'system', content: `[破冰] 获得关键线索：${res.data.new_fact_revealed}` })
       }
    }
  } catch (e) {
    // 接口未就绪时的兜底
    setTimeout(() => {
      chatHistory.value.push({ id: Date.now(), role: 'ai', content: '别问了，我什么都不想说，你们到底行不行啊！' })
      isLoading.value = false
      scrollToBottom()
    }, 1500)
  } finally {
    isLoading.value = false
    scrollToBottom()
  }
}

const finishTraining = async () => {
  isLoading.value = true
  try {
    const res = await axios.post(`http://127.0.0.1:8000/training/finish/${sessionId.value}`)
    localStorage.setItem('last_evaluation_report', JSON.stringify(res.data))
    router.push('/evaluation')
  } catch (e) {
    showToast('评估生成失败，请稍后重试')
  } finally {
    isLoading.value = false
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

onMounted(() => {
  // 可以调用 /training/start 启动真实会话
})
</script>

<template>
  <div class="h-screen bg-slate-900 flex flex-col relative">
    
    <!-- 顶部状态导航栏 (按照草图还原) -->
    <div class="flex justify-between items-center p-4 bg-slate-900/80 backdrop-blur-md sticky top-0 z-20">
      <div class="w-10 h-10 rounded-full border border-slate-600 flex items-center justify-center text-slate-300" @click="router.back()">
        <van-icon name="wap-nav" size="20" />
      </div>
      
      <!-- 情绪与信任胶囊 -->
      <div class="bg-slate-800 border border-slate-700 rounded-full px-3 py-1.5 flex items-center space-x-3 shadow-lg">
        <div class="flex items-center space-x-1">
          <van-icon name="fire" :class="currentState.emotion > 70 ? 'text-red-500' : 'text-orange-400'" />
          <span class="text-xs text-slate-300 font-bold">{{ currentState.emotion }}</span>
        </div>
        <div class="w-px h-3 bg-slate-600"></div>
        <div class="flex items-center space-x-1">
          <van-icon name="good-job" :class="currentState.trust < 30 ? 'text-slate-500' : 'text-green-400'" />
          <span class="text-xs text-slate-300 font-bold">{{ currentState.trust }}</span>
        </div>
      </div>

      <!-- 结束按钮 -->
      <van-button size="small" round class="!bg-red-500/20 !border-red-500/50 !text-red-400" @click="finishTraining">
        结束
      </van-button>
    </div>
    
    <!-- 中间：案件标签与聊天列表 -->
    <div class="flex-1 overflow-y-auto px-4 pb-4" ref="chatContainer">
      <div class="flex justify-center space-x-4 py-4">
        <div class="px-4 py-2 bg-indigo-900/40 border border-indigo-500/30 text-indigo-200 text-sm rounded-lg shadow-inner">
          案件类型
        </div>
        <div class="px-4 py-2 bg-purple-900/40 border border-purple-500/30 text-purple-200 text-sm rounded-lg shadow-inner">
          人物设定
        </div>
      </div>
      
      <!-- 对话消息列表 -->
      <div class="space-y-4">
        <div v-for="msg in chatHistory" :key="msg.id" class="flex flex-col">
          <div v-if="msg.role === 'system'" class="self-center my-2 text-xs text-slate-500 bg-slate-800/50 px-3 py-1 rounded-full text-center">
            {{ msg.content }}
          </div>
          
          <div v-else-if="msg.role === 'ai'" class="flex self-start max-w-[85%] mt-2">
            <div class="w-8 h-8 rounded-full bg-red-900/50 flex-shrink-0 flex items-center justify-center border border-red-700/50 text-red-300">
              <van-icon name="contact" />
            </div>
            <div class="ml-2 px-4 py-2 bg-slate-800 text-white rounded-2xl rounded-tl-none border border-slate-700 shadow-sm text-sm leading-relaxed">
              {{ msg.content }}
            </div>
          </div>
          
          <div v-else class="flex self-end max-w-[85%] mt-2">
            <div class="mr-2 px-4 py-2 bg-blue-600 text-white rounded-2xl rounded-tr-none shadow-md text-sm leading-relaxed">
              {{ msg.content }}
            </div>
            <div class="w-8 h-8 rounded-full bg-blue-900 flex-shrink-0 flex items-center justify-center border border-blue-400 text-blue-200">
              <van-icon name="friends-o" />
            </div>
          </div>
        </div>
        
        <!-- Loading 状态 -->
        <div v-if="isLoading" class="flex self-start max-w-[85%] mt-2">
           <div class="w-8 h-8 rounded-full bg-red-900/50 flex-shrink-0 flex items-center justify-center border border-red-700/50 text-red-300">
              <van-icon name="contact" />
            </div>
            <div class="ml-2 px-4 py-2 bg-slate-800 text-slate-400 rounded-2xl rounded-tl-none border border-slate-700 flex items-center space-x-1">
              <div class="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce"></div>
              <div class="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce" style="animation-delay: 0.1s"></div>
              <div class="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
            </div>
        </div>
      </div>
    </div>
    
    <!-- 底部输入框 (完美还原草图) -->
    <div class="p-3 bg-slate-900 border-t border-slate-800 flex items-center space-x-2">
      <div class="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-slate-400 flex-shrink-0">
        <van-icon name="play-circle-o" size="22" class="transform rotate-90"/> <!-- Mictophone placeholder -->
      </div>
      
      <div class="flex-1 bg-slate-800 rounded-full border border-slate-700 overflow-hidden flex items-center relative">
        <input 
          v-model="inputMessage" 
          @keyup.enter="sendMessage"
          type="text" 
          class="w-full bg-transparent text-white px-4 py-2.5 outline-none placeholder-slate-500 text-sm"
          placeholder="请输入问话..."
        />
        <div class="absolute right-2 top-1.5 w-7 h-7 rounded-full bg-slate-700 flex items-center justify-center text-slate-300" v-if="!inputMessage">
          <van-icon name="plus" />
        </div>
      </div>
      
      <div class="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center text-white flex-shrink-0 shadow-lg shadow-blue-500/30" @click="sendMessage">
        <van-icon name="send-gift-o" size="20" class="transform -rotate-45 ml-0.5 mt-0.5"/>
      </div>
    </div>
    
  </div>
</template>
