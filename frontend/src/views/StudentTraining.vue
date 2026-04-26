<template>
  <div class="training-page">
    <!-- Left Sidebar: Case Info Panel -->
    <aside class="info-panel">
      <div class="panel-section">
        <h3 class="panel-title">
          <van-icon name="description" />
          案件信息
        </h3>
        <div class="info-item">
          <span class="info-label">案件名称</span>
          <span class="info-value">{{ caseInfo.title }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">当前场景</span>
          <span class="info-value">{{ caseInfo.sceneName }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">难度等级</span>
          <van-tag :color="getDifficultyColor(caseInfo.difficulty)" plain size="medium">
            {{ caseInfo.difficulty }}
          </van-tag>
        </div>
        <van-button 
          block 
          plain 
          type="primary" 
          size="mini" 
          style="margin-top: 10px; border-radius: 4px;"
          @click="showCaseBrief = true"
        >
          查看接警记录与现场
        </van-button>
      </div>

      <!-- NEW: Training Phase & Goal -->
      <div class="panel-section stage-section">
        <h3 class="panel-title">
          <van-icon name="send-gift-o" />
          训练阶段
        </h3>
        <div class="stage-card">
          <div class="stage-name-box">
            <span class="stage-tag">当前阶段</span>
            <span class="stage-name-text">{{ caseInfo.currentStage }}</span>
          </div>
          <div class="stage-goal-box">
            <div class="goal-label">本阶段目标：</div>
            <div class="goal-text">{{ caseInfo.currentStageGoal || '请开始与对方交流获取信息' }}</div>
          </div>
        </div>
      </div>

      <!-- State Indicators -->
      <div class="panel-section">
        <h3 class="panel-title">
          <van-icon name="chart-trending-o" />
          实时状态
        </h3>
        <div class="state-bar">
          <div class="state-header">
            <span class="state-label">情绪值</span>
            <span class="state-num" :style="{ color: currentState.emotion > 70 ? '#F53F3F' : '#FF7D00' }">
              {{ currentState.emotion }}
            </span>
          </div>
          <div class="progress-track">
            <div 
              class="progress-fill emotion-fill"
              :style="{ width: currentState.emotion + '%' }"
            ></div>
          </div>
        </div>
        <div class="state-bar">
          <div class="state-header">
            <span class="state-label">信任度</span>
            <span class="state-num" style="color: #165DFF;">{{ currentState.trust }}</span>
          </div>
          <div class="progress-track">
            <div 
              class="progress-fill trust-fill"
              :style="{ width: currentState.trust + '%' }"
            ></div>
          </div>
        </div>
      </div>

      <!-- Revealed Info -->
      <div class="panel-section facts-section">
        <h3 class="panel-title">
          <van-icon name="bookmark-o" />
          已获取信息
          <span class="fact-count">{{ revealedInfo.length }}</span>
        </h3>
        <div class="fact-list">
          <div v-if="revealedInfo.length === 0" class="fact-empty">
            暂未获取关键信息
          </div>
          <div v-for="(info, idx) in revealedInfo" :key="idx" class="fact-item">
            <van-icon name="success" color="#00B42A" />
            <span>{{ info }}</span>
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="panel-actions">
        <van-button 
          block 
          type="danger" 
          size="small"
          class="finish-btn"
          @click="finishTraining"
        >
          <van-icon name="flag-o" /> 结束训练并评分
        </van-button>
      </div>
    </aside>

    <!-- Right: Chat Area -->
    <div class="chat-area">
      <!-- Chat Messages -->
      <div class="chat-messages" ref="chatContainer">
        <div v-for="msg in chatHistory" :key="msg.id" class="msg-wrapper">
          <!-- System Message -->
          <div v-if="msg.role === 'system'" class="msg-system">
            <span>{{ msg.content }}</span>
          </div>

          <!-- AI (Role) Message -->
          <div v-else-if="msg.role === 'assistant'" class="msg-row msg-ai">
            <div class="avatar avatar-ai">
              <van-icon name="contact" size="20" />
            </div>
            <div class="msg-body">
              <span class="msg-sender">{{ roleInfo.name }}</span>
              <div class="msg-bubble bubble-ai">{{ msg.content }}</div>
            </div>
          </div>

          <!-- Human (Student) Message -->
          <div v-else class="msg-row msg-human">
            <div class="msg-body">
              <span class="msg-sender">执法警员</span>
              <div class="msg-bubble bubble-human">{{ msg.content }}</div>
            </div>
            <div class="avatar avatar-human">
              <van-icon name="friends-o" size="20" />
            </div>
          </div>
        </div>

        <!-- Typing Indicator -->
        <div v-if="isLoading" class="msg-row msg-ai">
          <div class="avatar avatar-ai">
            <van-icon name="contact" size="20" />
          </div>
          <div class="msg-bubble bubble-ai typing-indicator">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>

      <!-- Input Area -->
      <div class="chat-input-area">
        <div class="input-wrapper">
          <textarea 
            v-model="inputMessage" 
            rows="2"
            class="chat-input"
            placeholder="请输入执法话术或提问..."
            @keyup.enter.exact.prevent="sendMessage"
          ></textarea>
        </div>
        <van-button 
          type="primary"
          class="send-btn"
          :loading="isLoading"
          :disabled="!inputMessage.trim()"
          @click="sendMessage"
        >
          发送
        </van-button>
      </div>
    </div>

    <!-- Case Brief Modal (Fullscreen) -->
    <van-popup
      v-model:show="showCaseBrief"
      position="right"
      class="case-brief-popup"
      :style="{ width: '100%', height: '100%' }"
    >
      <div class="popup-header">
        <van-nav-bar
          title="警情与现场初查"
          left-text="返回训练"
          left-arrow
          @click-left="showCaseBrief = false"
        />
      </div>
      <div class="popup-content">
        <div class="brief-container">
          <!-- Main Header -->
          <div class="brief-header">
            <div class="flex items-center space-x-2 mb-2">
              <van-tag type="primary" size="large" round>{{ caseInfo.caseType || '其他' }}</van-tag>
              <span class="text-xs text-gray-400 font-bold tracking-widest">ID: #{{ sessionId }}</span>
            </div>
            <h2 class="brief-main-title">{{ caseInfo.title }}</h2>
          </div>

          <!-- Section: Dispatch Brief -->
          <div class="brief-section">
            <h4 class="brief-label">
              <span class="label-line"></span> 110 接警简报 (DISPATCH)
            </h4>
            <div class="abstract-box" style="background-color: #f2f3f5; color: #1d2129; border-left: 4px solid #165dff;">
              "{{ caseInfo.dispatchBrief || '（指挥中心暂无详细指令下发）' }}"
            </div>
          </div>
          
          <!-- Section: First Impression -->
          <div class="brief-section">
            <h4 class="brief-label">
              <span class="label-line grey"></span> 现场第一印象 (OBSERVATION)
            </h4>
            <div class="original-source-box" style="font-family: inherit; font-size: 14px;">
              {{ caseInfo.firstImpression || '（你到达了现场，暂未发现明显异常景象）' }}
            </div>
          </div>

          <!-- Section: Standard Operating Procedure (SOP) -->
          <div class="brief-section">
            <van-divider dashed />
            <h4 class="brief-label">
              <span class="label-line blue"></span> 执法操作指引 (SOP)
            </h4>
            <div class="structured-grid">
               <div class="sub-section">
                  <span class="sub-title">当前阶段建议</span>
                  <div style="font-size: 13px; color: #4e5969; margin-top: 8px; line-height: 1.6;">
                    1. 核实对话人员身份信息。<br/>
                    2. 控制现场情绪，避免冲突升级。<br/>
                    3. 针对接警简报中的核心问题进行初步询问。<br/>
                    4. 留意对方神态，判断是否有所隐瞒。
                  </div>
               </div>
            </div>
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
import { showToast, showLoadingToast } from 'vant'

const route = useRoute()
const router = useRouter()

const sessionId = ref(route.params.id)
const inputMessage = ref('')
const isLoading = ref(false)
const showCaseBrief = ref(false)

const caseInfo = reactive({ 
  title: '加载中...', 
  sceneName: '', 
  difficulty: '中等',
  currentStage: '',
  currentStageGoal: '',
  caseBackground: '',
  caseOriginalContent: '',
  dispatchBrief: '',
  firstImpression: '',
  caseType: '',
  roleStatus: '正常',
  structuredData: null as any
})
const roleInfo = reactive({ name: '对话对象' })
const revealedInfo = ref<string[]>([])
const currentState = ref({ emotion: 50, trust: 30 })
const chatHistory = ref<any[]>([])

const fetchSessionData = async () => {
  try {
    const res: any = await request.get(`/training/session/${sessionId.value}`)
    caseInfo.title = res.case_title
    caseInfo.sceneName = res.scene_name
    caseInfo.currentStage = res.current_stage
    caseInfo.currentStageGoal = res.current_stage_goal
    caseInfo.caseBackground = res.case_background
    caseInfo.caseOriginalContent = res.case_original_content
    caseInfo.dispatchBrief = res.dispatch_brief
    caseInfo.firstImpression = res.first_impression
    caseInfo.caseType = res.case_type
    caseInfo.roleStatus = res.role_status
    caseInfo.structuredData = res.structured_data ? JSON.parse(res.structured_data) : null
    roleInfo.name = res.role_name
    currentState.value.emotion = res.current_emotion
    currentState.value.trust = res.current_trust
    revealedInfo.value = JSON.parse(res.revealed_info || '[]')
    
    chatHistory.value = [
      { id: 0, role: 'system', content: `训练已开始，场景：${res.scene_name || '现场'}，对话对象：${res.role_name}` },
      ...res.messages.map((m: any) => ({
        id: m.id,
        role: m.role === 'user' ? 'human' : 'assistant',
        content: m.content
      }))
    ]
    scrollToBottom()
  } catch (e) {
    showToast('获取训练数据失败')
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
        revealedInfo.value.push(res.new_fact_revealed)
        chatHistory.value.push({ 
          id: Date.now(), 
          role: 'system', 
          content: `[关键事实获取] ${res.new_fact_revealed}` 
        })
      }

      // 检查阶段流转
      if (res.is_stage_completed) {
        // 重新获取会话信息以拉取最新阶段目标
        const updatedRes: any = await request.get(`/training/session/${sessionId.value}`)
        if (updatedRes.current_stage !== caseInfo.currentStage) {
          const oldStage = caseInfo.currentStage
          caseInfo.currentStage = updatedRes.current_stage
          caseInfo.currentStageGoal = updatedRes.current_stage_goal
          chatHistory.value.push({
            id: Date.now() + 1,
            role: 'system',
            content: `【阶段切换】由于表现出色，已由 [${oldStage}] 进入到 [${caseInfo.currentStage}] 阶段。`
          })
        }
      }
    }
  } catch (e) {
    showToast('AI响应异常，请重试')
  } finally {
    isLoading.value = false
    scrollToBottom()
  }
}

const finishTraining = async () => {
  const loader = showLoadingToast({ message: '正在生成评分报告...', forbidClick: true })
  try {
    const res = await request.post(`/training/finish/${sessionId.value}`)
    localStorage.setItem('last_evaluation', JSON.stringify(res))
    loader.close()
    router.push('/student/evaluation')
  } catch (e) {
    loader.close()
    showToast('报告生成失败')
  }
}

const getDifficultyColor = (diff: string) => {
  if (diff === '简单') return '#00B42A'
  if (diff === '困难') return '#F53F3F'
  return '#FF7D00'
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
.training-page {
  display: flex;
  height: calc(100vh - 56px);
  overflow: hidden;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Inter', sans-serif;
}

/* Left Panel */
.info-panel {
  width: 280px;
  background: white;
  border-right: 1px solid #E5E6EB;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  flex-shrink: 0;
}

.panel-section {
  padding: 20px;
  border-bottom: 1px solid #F2F3F5;
}

.panel-title {
  font-size: 13px;
  font-weight: 600;
  color: #1D2129;
  margin: 0 0 14px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.fact-count {
  background: #165DFF;
  color: white;
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 10px;
  margin-left: auto;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
}

.info-item + .info-item {
  border-top: 1px dashed #F2F3F5;
}

.info-label {
  font-size: 13px;
  color: #86909C;
}

.info-value {
  font-size: 13px;
  color: #1D2129;
  font-weight: 500;
  max-width: 150px;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* State Bars */
.state-bar {
  margin-bottom: 14px;
}

.state-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.state-label {
  font-size: 12px;
  color: #86909C;
}

.state-num {
  font-size: 14px;
  font-weight: 700;
}

.progress-track {
  height: 6px;
  background: #F2F3F5;
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.8s ease;
}

.emotion-fill {
  background: linear-gradient(90deg, #FF7D00, #F53F3F);
}

.trust-fill {
  background: linear-gradient(90deg, #86909C, #165DFF);
}

/* Facts */
.facts-section {
  flex: 1;
  overflow-y: auto;
}

.fact-empty {
  font-size: 12px;
  color: #C9CDD4;
  text-align: center;
  padding: 20px 0;
}

.fact-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 0;
  font-size: 12px;
  color: #4E5969;
  line-height: 1.5;
}

.fact-item + .fact-item {
  border-top: 1px dashed #F2F3F5;
}

/* Stage Section */
.stage-section {
  background: #fdfdfd;
}

.stage-card {
  background: #F2F3F5;
  border-radius: 8px;
  padding: 12px;
}

.stage-name-box {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.stage-tag {
  background: #165DFF;
  color: white;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
}

.stage-name-text {
  font-size: 14px;
  font-weight: 700;
  color: #1D2129;
}

.stage-goal-box {
  background: white;
  padding: 10px;
  border-radius: 4px;
  border-left: 3px solid #165DFF;
}

.goal-label {
  font-size: 11px;
  color: #86909C;
  margin-bottom: 4px;
}

.goal-text {
  font-size: 12px;
  color: #4E5969;
  line-height: 1.6;
}

.panel-actions {
  padding: 16px 20px;
  border-top: 1px solid #F2F3F5;
}

.finish-btn {
  border-radius: 4px !important;
  font-size: 13px !important;
}

/* Chat Area */
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #F7F8FA;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
}

.msg-wrapper + .msg-wrapper {
  margin-top: 16px;
}

/* System Message */
.msg-system {
  text-align: center;
}

.msg-system span {
  display: inline-block;
  padding: 4px 16px;
  background: #E5E6EB;
  border-radius: 12px;
  font-size: 12px;
  color: #86909C;
}

/* Message Row */
.msg-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.msg-human {
  justify-content: flex-end;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.avatar-ai {
  background: #F2F3F5;
  color: #4E5969;
  border: 1px solid #E5E6EB;
}

.avatar-human {
  background: #165DFF;
  color: white;
}

.msg-body {
  max-width: 65%;
}

.msg-sender {
  display: block;
  font-size: 12px;
  color: #86909C;
  margin-bottom: 4px;
}

.msg-human .msg-sender {
  text-align: right;
}

/* Bubble - follows UI doc specs */
.msg-bubble {
  padding: 10px 14px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.bubble-ai {
  background: white;
  color: #1D2129;
  border-radius: 2px 12px 12px 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.bubble-human {
  background: #165DFF;
  color: white;
  border-radius: 12px 2px 12px 12px;
  box-shadow: 0 1px 4px rgba(22, 93, 255, 0.2);
}

/* Typing indicator */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 14px 18px;
}

.typing-indicator span {
  width: 6px;
  height: 6px;
  background: #C9CDD4;
  border-radius: 50%;
  animation: blink 1.2s infinite;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes blink {
  0%, 80%, 100% { opacity: 0.3; }
  40% { opacity: 1; }
}

/* Input Area */
.chat-input-area {
  padding: 16px 32px;
  background: white;
  border-top: 1px solid #E5E6EB;
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.input-wrapper {
  flex: 1;
}

.chat-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #C9CDD4;
  border-radius: 4px;
  font-size: 14px;
  font-family: inherit;
  resize: none;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.chat-input:focus {
  border-color: #165DFF;
}

.send-btn {
  background: #165DFF !important;
  border: none !important;
  border-radius: 4px !important;
  height: 42px !important;
  padding: 0 24px !important;
}

/* Scrollbar */
.chat-messages::-webkit-scrollbar { width: 4px; }
.chat-messages::-webkit-scrollbar-thumb { background: #C9CDD4; border-radius: 2px; }
.info-panel::-webkit-scrollbar { width: 3px; }
.info-panel::-webkit-scrollbar-thumb { background: #E5E6EB; border-radius: 2px; }

/* Popup Styling Re-design */
.popup-content {
  padding: 32px 24px;
  background: #F8F9FA;
  height: calc(100vh - 46px);
  overflow-y: auto;
}

.brief-container {
  max-width: 800px;
  margin: 0 auto;
}

.brief-header {
  margin-bottom: 48px;
}

.brief-main-title {
  font-size: 32px;
  font-weight: 800;
  color: #1D2129;
  letter-spacing: -0.5px;
}

.brief-section {
  margin-bottom: 40px;
}

.brief-label {
  font-size: 13px;
  font-weight: 900;
  color: #86909C;
  letter-spacing: 0.2em;
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}

.label-line {
  width: 40px;
  height: 1px;
  background: #E5E6EB;
  margin-right: 12px;
}

.label-line.blue { background: #165DFF; opacity: 0.3; }

.abstract-box {
  background: white;
  padding: 24px 32px;
  border-radius: 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
  line-height: 1.8;
  color: #4E5969;
  font-style: italic;
  font-size: 15px;
}

.original-source-box {
  background: #F2F3F5;
  padding: 32px;
  border-radius: 16px;
  line-height: 1.9;
  color: #1D2129;
  font-size: 17px;
  white-space: pre-wrap;
  font-family: "PingFang SC", "Microsoft YaHei", "Heiti SC", "SimHei", sans-serif;
  letter-spacing: 0.02em;
  border: 1px solid #E5E6EB;
}

.sub-section {
  margin-top: 16px;
}

.sub-title {
  display: block;
  font-size: 12px;
  font-weight: bold;
  color: #4E5969;
  margin-bottom: 8px;
}

.tag-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.fact-dots {
  padding-left: 20px;
  color: #4E5969;
}

.fact-dots li {
  margin-bottom: 10px;
  font-size: 14px;
  list-style-type: square;
}
</style>
