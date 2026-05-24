<template>
  <div class="training-page">
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
        <van-button block plain type="primary" size="mini" class="brief-btn" @click="showCaseBrief = true">
          查看接警简报与现场信息
        </van-button>
      </div>

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
            <div class="goal-label">本阶段目标</div>
            <div class="goal-text">{{ caseInfo.currentStageGoal || '请开始与对方交流，获取关键事实。' }}</div>
          </div>
        </div>
      </div>


      <div v-if="sceneRoles.length" class="panel-section scene-roles-section">
        <h3 class="panel-title">
          <van-icon name="friends-o" />
          现场角色
        </h3>
        <p class="scene-role-hint">点击或输入里写出角色名即可指定对象；点名多人会依次发言。仅左侧列出的角色能直接对话。</p>
        <div class="scene-role-list">
          <button
            v-for="role in sceneRoles"
            :key="role.id"
            type="button"
            class="scene-role-chip"
            :class="{
              active: targetRoleName === role.name,
              primary: role.is_primary,
              'scene-role-chip--active': role.is_active,
              'scene-role-chip--risk': (role.risk ?? 0) >= 70,
            }"
            :disabled="!role.speakable || isLoading"
            @click="toggleTargetRole(role)"
          >
            <span class="scene-role-chip__name">{{ role.name }}</span>
            <span class="scene-role-chip__meta">
              {{ role.state_label || role.role_type || '角色' }}
              <template v-if="role.emotion != null"> · 情绪{{ role.emotion }}</template>
            </span>
            <span v-if="role.cooperation != null" class="scene-role-chip__bar">
              <span class="scene-role-chip__bar-fill" :style="{ width: `${role.cooperation}%` }"></span>
            </span>
          </button>
        </div>
      </div>

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
            <div class="progress-fill emotion-fill" :style="{ width: currentState.emotion + '%' }"></div>
          </div>
        </div>
        <div class="state-bar">
          <div class="state-header">
            <span class="state-label">信任度</span>
            <span class="state-num" style="color: #165DFF;">{{ currentState.trust }}</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill trust-fill" :style="{ width: currentState.trust + '%' }"></div>
          </div>
        </div>
        <div class="state-bar">
          <div class="state-header">
            <span class="state-label">失控风险</span>
            <span class="state-num" :style="{ color: currentState.risk > 70 ? '#C2410C' : '#EA580C' }">{{ currentState.risk }}</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill risk-fill" :style="{ width: currentState.risk + '%' }"></div>
          </div>
        </div>
        <div class="state-bar">
          <div class="state-header">
            <span class="state-label">表达清晰度</span>
            <span class="state-num" :style="{ color: currentState.clarity < 40 ? '#7C3AED' : '#0F766E' }">{{ currentState.clarity }}</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill clarity-fill" :style="{ width: currentState.clarity + '%' }"></div>
          </div>
        </div>
      </div>

      <div class="panel-section facts-section">
        <h3 class="panel-title">
          <van-icon name="bookmark-o" />
          已获取信息
          <span class="fact-count">{{ revealedInfo.length }}</span>
        </h3>
        <div class="fact-list">
          <div v-if="revealedInfo.length === 0" class="fact-empty">暂未获取关键线索</div>
          <div v-for="(info, idx) in revealedInfo" :key="idx" class="fact-item">
            <van-icon name="success" color="#00B42A" />
            <span>{{ info }}</span>
          </div>
        </div>
      </div>

      <div class="panel-actions">
        <van-button block type="danger" size="small" class="finish-btn" @click="finishTraining">
          <van-icon name="flag-o" /> 结束训练并生成评估
        </van-button>
      </div>
    </aside>

    <div class="chat-area">
      <div v-if="routingSummary || addressingWarning" class="scene-session-bar">
        <span class="scene-session-bar__title">场景会话</span>
        <span v-if="routingSummary" class="scene-session-bar__hint">{{ routingSummary }}</span>
        <span v-if="addressingWarning" class="scene-session-bar__warn">{{ addressingWarning }}</span>
      </div>
      <div ref="chatContainer" class="chat-messages">
        <div v-for="msg in chatHistory" :key="msg.id" class="msg-wrapper">
          <div v-if="msg.role === 'system'" class="msg-system">
            <span>{{ msg.content }}</span>
          </div>

          <div v-else-if="msg.role === 'assistant'" class="msg-row msg-ai">
            <div class="avatar avatar-ai">
              <van-icon name="contact" size="20" />
            </div>
            <div class="msg-body">
              <span class="msg-sender">{{ msg.speakerName || roleInfo.name }}</span>
              <div class="msg-bubble bubble-ai">{{ msg.content }}</div>
            </div>
          </div>

          <div v-else class="msg-row msg-human">
            <div class="msg-body">
              <span class="msg-sender">执法民警</span>
              <div class="msg-bubble bubble-human">{{ msg.content }}</div>
            </div>
            <div class="avatar avatar-human">
              <van-icon name="friends-o" size="20" />
            </div>
          </div>
        </div>

        <div v-if="isLoading" class="msg-row msg-ai">
          <div class="avatar avatar-ai">
            <van-icon name="contact" size="20" />
          </div>
          <div class="msg-bubble bubble-ai typing-indicator">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>

      <div class="chat-input-area">
        <div v-if="communicationFeedback.message" class="coach-feedback" :class="`coach-feedback--${communicationFeedback.level || 'info'}`">
          <span class="coach-feedback__label">问法提示</span>
          <span class="coach-feedback__text">{{ communicationFeedback.message }}</span>
        </div>
        <div v-if="stageMissing.length" class="stage-missing">
          <span class="stage-missing__label">本阶段待补齐</span>
          <span v-for="item in stageMissing" :key="item" class="stage-missing__tag">{{ item }}</span>
        </div>
        <div v-if="suggestedQuestionItems.length" class="suggested-questions">
          <div class="suggested-questions__head">
            <span class="suggested-questions__title">建议追问</span>
            <span class="suggested-questions__hint">点选填入输入框，将自动对准询问对象</span>
          </div>
          <div class="suggested-questions__list">
            <button
              v-for="(item, index) in suggestedQuestionItems"
              :key="`${index}-${item.text}`"
              type="button"
              class="suggested-question-chip"
              :disabled="isLoading"
              @click="applySuggestedQuestion(item)"
            >
              <span class="suggested-question-chip__cat">{{ item.category || '追问' }}</span>
              <span class="suggested-question-chip__text">{{ item.text }}</span>
            </button>
          </div>
          </div>
        <TrainingInputBar
          v-model="inputMessage"
          :loading="isLoading"
          :disabled="isLoading"
          @send="sendMessage"
        />
      </div>
    </div>

    <van-popup
      v-model:show="showCaseBrief"
      position="right"
      class="case-brief-popup"
      :style="{ width: '100%', height: '100%' }"
    >
      <div class="popup-header">
        <van-nav-bar title="接警简报与现场信息" left-text="返回训练" left-arrow @click-left="showCaseBrief = false" />
      </div>
      <div class="popup-content">
        <div class="brief-container">
          <div class="brief-header">
            <div class="brief-meta">
              <van-tag type="primary" size="large" round>{{ caseInfo.caseType || '其他' }}</van-tag>
              <span class="brief-id">会话 #{{ sessionId }}</span>
            </div>
            <h2 class="brief-main-title">{{ caseInfo.title }}</h2>
          </div>

          <div class="brief-section">
            <h4 class="brief-label">
              <span class="label-line"></span> 110 接警简报
            </h4>
            <div class="abstract-box dispatch-box">
              {{ caseInfo.dispatchBrief || '指挥中心暂未下发更详细的接警简报。' }}
            </div>
          </div>

          <div class="brief-section">
            <h4 class="brief-label">
              <span class="label-line grey"></span> 现场第一印象
            </h4>
            <div class="original-source-box">
              {{ caseInfo.firstImpression || '你已到达现场，暂未发现特别明显的异常情况。' }}
            </div>
          </div>

          <div class="brief-section">
            <van-divider dashed />
            <h4 class="brief-label">
              <span class="label-line blue"></span> 执法提示
            </h4>
            <div class="structured-grid">
              <div class="sub-section">
                <span class="sub-title">当前阶段建议</span>
                <div class="sop-text">
                  1. 先核实对话对象身份与所处位置。<br />
                  2. 结合场景目标围绕时间、地点、人物、经过展开询问。<br />
                  3. 注意控制现场情绪，避免冲突升级。<br />
                  4. 留意对方表述中的矛盾点、隐瞒点和风险点。
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
import { nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showLoadingToast, showToast } from 'vant'
import request from '../utils/request'
import TrainingInputBar from '../components/TrainingInputBar.vue'

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
interface SceneRoleBrief {
  id: number
  name: string
  role_type?: string
  is_primary?: boolean
  speakable?: boolean
  emotion?: number
  cooperation?: number
  risk?: number
  clarity?: number
  state_label?: string
  is_active?: boolean
  is_targeted?: boolean
}
const sceneRoles = ref<SceneRoleBrief[]>([])
const routingSummary = ref('')
const addressingWarning = ref('')
const targetRoleName = ref('')
interface SuggestedQuestionItem {
  text: string
  category?: string
  target_role_name?: string | null
}
const suggestedQuestionItems = ref<SuggestedQuestionItem[]>([])
const communicationFeedback = ref<{ level?: string; message?: string }>({ message: '' })
const stageMissing = ref<string[]>([])

const revealedInfo = ref<string[]>([])
const currentState = ref({ emotion: 50, trust: 30, risk: 50, clarity: 50 })
const chatHistory = ref<Array<{ id: number; role: string; content: string; speakerName?: string }>>([])



const META_QUESTION_PATTERN = /先围绕|把最关键|这一点|训练已恢复|补齐这些关键项/

const normalizeSuggestedItems = (payload: unknown): SuggestedQuestionItem[] => {
  if (Array.isArray(payload) && payload.length && typeof payload[0] === 'object') {
    return payload
      .map((item: any) => ({
        text: String(item?.text || '').trim(),
        category: String(item?.category || '追问').trim() || '追问',
        target_role_name: item?.target_role_name || null,
      }))
      .filter((item) => item.text && !META_QUESTION_PATTERN.test(item.text) && item.text.length <= 48)
      .slice(0, 4)
  }
  const list = Array.isArray(payload) ? payload : []
  return list
    .map((item) => String(item || '').trim())
    .filter((item) => item && !META_QUESTION_PATTERN.test(item) && item.length <= 48)
    .slice(0, 4)
    .map((text) => ({ text, category: '追问', target_role_name: null }))
}

const applySuggestedQuestions = (items: unknown, fallbackTexts?: unknown) => {
  const normalized = normalizeSuggestedItems(items)
  if (normalized.length) {
    suggestedQuestionItems.value = normalized
    return
  }
  suggestedQuestionItems.value = normalizeSuggestedItems(fallbackTexts)
}

const applyGuidancePayload = (res: any) => {
  applySuggestedQuestions(res?.recommended_question_items, res?.recommended_questions)
  const feedback = res?.communication_feedback
  communicationFeedback.value = {
    level: feedback?.level || 'info',
    message: feedback?.message || '',
  }
  stageMissing.value = Array.isArray(res?.stage_completion_missing)
    ? res.stage_completion_missing.filter(Boolean)
    : []
}

const applySuggestedQuestion = (item: SuggestedQuestionItem | string) => {
  const payload = typeof item === 'string' ? { text: item } : item
  const text = String(payload?.text || '').trim()
  if (!text || isLoading.value) return
  inputMessage.value = text
  const roleName = String(payload?.target_role_name || '').trim()
  if (roleName) {
    targetRoleName.value = roleName
    return
  }
  const matched = sceneRoles.value.find((role) => text.startsWith(`${role.name}，`))
  if (matched) targetRoleName.value = matched.name
}

const toggleTargetRole = (role: SceneRoleBrief) => {
  if (!role?.speakable) return
  targetRoleName.value = targetRoleName.value === role.name ? '' : role.name
}

/** 从输入文案识别在场角色名，同步询问对象（长名优先，避免短名误匹配）。 */
const syncTargetFromMessage = (msg: string) => {
  const speakable = sceneRoles.value.filter((role) => role.speakable !== false && role.name)
  const matched = speakable
    .filter((role) => msg.includes(role.name))
    .sort((a, b) => b.name.length - a.name.length)
  if (matched.length === 1) {
    targetRoleName.value = matched[0].name
  } else if (matched.length >= 2) {
    targetRoleName.value = ''
  }
}

const appendAssistantReplies = (res: any, baseId: number) => {
  const turns = Array.isArray(res?.reply_turns) ? res.reply_turns : []
  if (turns.length) {
    turns
      .filter((item: any) => String(item?.content || '').trim())
      .forEach((item: any, index: number) => {
        chatHistory.value.push({
          id: baseId + index,
          role: 'assistant',
          content: String(item.content),
          speakerName: item.speaker_name || item.speakerName || roleInfo.name,
        })
      })
    return
  }
  const sequence =
    Array.isArray(res?.reply_sequence) && res.reply_sequence.length
      ? res.reply_sequence
      : [res?.response].filter(Boolean)
  sequence
    .filter((item: string) => String(item || '').trim())
    .forEach((content: string, index: number) => {
      chatHistory.value.push({
        id: baseId + index,
        role: 'assistant',
        content,
        speakerName: roleInfo.name,
      })
    })
}

const buildSystemIntro = (sceneName: string, roleName: string, roles: SceneRoleBrief[] = []) => {
  const names = roles.filter((r) => r.speakable !== false).map((r) => r.name)
  const cast =
    names.length >= 2
      ? `现场角色：${names.join('、')}`
      : `对话对象：${roleName || names[0] || '未指定角色'}`
  return `训练已开始，当前场景：${sceneName || '现场'}，${cast}`
}

const safeParse = <T>(value: any, fallback: T): T => {
  if (value === null || value === undefined || value === '') return fallback
  if (typeof value !== 'string') return value as T
  try {
    return JSON.parse(value) as T
  } catch (error) {
    return fallback
  }
}

const fetchSessionData = async () => {
  try {
    const res: any = await request.get(`/training/session/${sessionId.value}`)
    caseInfo.title = res.case_title
    caseInfo.sceneName = res.scene_name
    caseInfo.difficulty = res.difficulty || '中等'
    caseInfo.currentStage = res.current_stage
    caseInfo.currentStageGoal = res.current_stage_goal
    caseInfo.caseBackground = res.case_background
    caseInfo.caseOriginalContent = res.case_original_content
    caseInfo.dispatchBrief = res.dispatch_brief
    caseInfo.firstImpression = res.first_impression
    caseInfo.caseType = res.case_type
    caseInfo.roleStatus = res.role_status
    caseInfo.structuredData = safeParse(res.structured_data, null)
    roleInfo.name = res.role_name
    sceneRoles.value = Array.isArray(res.scene_roles) ? res.scene_roles : []
    applyGuidancePayload(res)
    currentState.value.emotion = res.current_emotion
    currentState.value.trust = res.current_trust
    currentState.value.risk = res.current_risk ?? 50
    currentState.value.clarity = res.current_clarity ?? 50
    revealedInfo.value = safeParse<string[]>(res.revealed_info, [])

    chatHistory.value = [
      {
        id: 0,
        role: 'system',
        content: buildSystemIntro(res.scene_name, res.role_name, sceneRoles.value),
      },
      ...(res.messages || []).map((message: any) => ({
        id: message.id,
        role: message.role === 'user' ? 'human' : message.role === 'system' ? 'system' : 'assistant',
        content: message.content,
        speakerName: message.speaker_name || undefined,
      }))
    ]
    scrollToBottom()
  } catch (error) {
    showToast('获取训练数据失败')
  }
}

const sendMessage = async () => {
  if (!inputMessage.value.trim() || isLoading.value) return

  const msg = inputMessage.value.trim()
  syncTargetFromMessage(msg)
  chatHistory.value.push({ id: Date.now(), role: 'human', content: msg })
  inputMessage.value = ''
  isLoading.value = true
  scrollToBottom()

  try {
    const res: any = await request.post(`/training/chat/${sessionId.value}`, {
      role: 'user',
      content: msg,
      target_role_name: targetRoleName.value || undefined,
    })

    if (res?.response || (Array.isArray(res?.reply_turns) && res.reply_turns.length)) {
      appendAssistantReplies(res, Date.now() + 1)
      if (Array.isArray(res.scene_roles) && res.scene_roles.length) {
        sceneRoles.value = res.scene_roles
      }
      routingSummary.value = String(res.routing_summary || '').trim()
      addressingWarning.value = String(res.addressing_warning || '').trim()
      applyGuidancePayload(res)
      currentState.value.emotion = res.updated_emotion
      currentState.value.trust = res.updated_trust
      currentState.value.risk = res.updated_risk ?? currentState.value.risk
      currentState.value.clarity = res.updated_clarity ?? currentState.value.clarity

      if (res.new_fact_revealed && res.new_fact_revealed !== 'null' && !revealedInfo.value.includes(res.new_fact_revealed)) {
        revealedInfo.value.push(res.new_fact_revealed)
        chatHistory.value.push({
          id: Date.now() + 2,
          role: 'system',
          content: `[关键线索获取] ${res.new_fact_revealed}`
        })
      }

      if (res.is_stage_completed) {
        const updatedRes: any = await request.get(`/training/session/${sessionId.value}`)
        currentState.value.risk = updatedRes.current_risk ?? currentState.value.risk
        currentState.value.clarity = updatedRes.current_clarity ?? currentState.value.clarity
        if (updatedRes.current_stage !== caseInfo.currentStage) {
          const oldStage = caseInfo.currentStage
          caseInfo.currentStage = updatedRes.current_stage
          caseInfo.currentStageGoal = updatedRes.current_stage_goal
          applyGuidancePayload(updatedRes)
          chatHistory.value.push({
            id: Date.now() + 3,
            role: 'system',
            content: `【阶段切换】已由「${oldStage}」进入「${caseInfo.currentStage}」阶段。`
          })
        }
      }
    }
  } catch (error) {
    showToast('AI 响应异常，请稍后重试')
  } finally {
    isLoading.value = false
    scrollToBottom()
  }
}

const finishTraining = async () => {
  const loader = showLoadingToast({ message: '正在生成评估报告...', forbidClick: true })
  try {
    await request.post(`/training/finish/${sessionId.value}`)
    loader.close()
    router.push(`/student/evaluation?session_id=${sessionId.value}`)
  } catch (error) {
    loader.close()
    showToast('评估报告生成失败')
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
.scene-role-hint {
  margin: 0 0 10px;
  font-size: 12px;
  color: #86909c;
  line-height: 1.5;
}

.scene-role-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.scene-role-chip {
  border: 1px solid #e5e6eb;
  background: #f7f8fa;
  border-radius: 10px;
  padding: 8px 10px;
  cursor: pointer;
  text-align: left;
  min-width: 88px;
}

.scene-role-chip.primary {
  border-color: #bedaff;
}

.scene-role-chip.active {
  border-color: #165dff;
  background: #e8f3ff;
}

.scene-role-chip:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.scene-role-chip__name {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #1d2129;
}

.scene-role-chip__meta {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  color: #86909c;
}

.scene-role-chip--active {
  box-shadow: 0 0 0 1px #ff7d00 inset;
}

.scene-role-chip--risk {
  border-color: #f53f3f;
}

.scene-role-chip__bar {
  display: block;
  margin-top: 6px;
  height: 3px;
  background: #e5e6eb;
  border-radius: 2px;
  overflow: hidden;
}

.scene-role-chip__bar-fill {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #165dff, #4080ff);
  border-radius: 2px;
}

.scene-session-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #f2f3f5;
  border-bottom: 1px solid #e5e6eb;
  flex-shrink: 0;
}

.scene-session-bar__title {
  font-size: 12px;
  font-weight: 600;
  color: #1d2129;
}

.scene-session-bar__hint {
  font-size: 11px;
  color: #86909c;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.scene-session-bar__warn {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  line-height: 1.45;
  color: #b45309;
}

.training-page {
  display: flex;
  height: calc(100vh - 56px);
  overflow: hidden;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Inter', sans-serif;
}

.info-panel {
  width: 296px;
  background: white;
  border-right: 1px solid #e5e6eb;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  flex-shrink: 0;
}

.panel-section {
  padding: 20px;
  border-bottom: 1px solid #f2f3f5;
}

.panel-title {
  font-size: 13px;
  font-weight: 700;
  color: #1d2129;
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 14px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  font-size: 13px;
}

.info-label {
  color: #86909c;
}

.info-value {
  color: #1d2129;
  text-align: right;
  font-weight: 500;
}

.brief-btn {
  margin-top: 10px;
  border-radius: 8px;
}

.stage-card {
  background: #f7f8fa;
  border-radius: 12px;
  padding: 14px;
}

.stage-tag {
  display: inline-block;
  font-size: 11px;
  color: #165dff;
  background: #e8f3ff;
  padding: 4px 8px;
  border-radius: 999px;
}

.stage-name-text {
  display: block;
  margin-top: 10px;
  font-size: 18px;
  font-weight: 700;
  color: #1d2129;
}

.goal-label {
  margin-top: 12px;
  font-size: 12px;
  color: #86909c;
}

.goal-text {
  margin-top: 6px;
  font-size: 13px;
  color: #4e5969;
  line-height: 1.7;
}

.state-bar + .state-bar {
  margin-top: 16px;
}

.state-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
}

.state-label {
  color: #4e5969;
}

.state-num {
  font-weight: 700;
}

.progress-track {
  height: 8px;
  border-radius: 999px;
  background: #f2f3f5;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
}

.emotion-fill {
  background: linear-gradient(90deg, #fb7185 0%, #f97316 100%);
}

.trust-fill {
  background: linear-gradient(90deg, #60a5fa 0%, #2563eb 100%);
}

.risk-fill {
  background: linear-gradient(90deg, #fdba74 0%, #ea580c 100%);
}

.clarity-fill {
  background: linear-gradient(90deg, #5eead4 0%, #0f766e 100%);
}

.fact-count {
  margin-left: auto;
  font-size: 12px;
  color: #165dff;
}

.fact-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.fact-empty {
  font-size: 13px;
  color: #86909c;
}

.fact-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: #4e5969;
}

.panel-actions {
  padding: 20px;
  margin-top: auto;
}

.finish-btn {
  border-radius: 10px;
}

.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #f7f8fa;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.msg-wrapper + .msg-wrapper {
  margin-top: 14px;
}

.msg-system {
  text-align: center;
  color: #86909c;
  font-size: 12px;
}

.msg-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.msg-human {
  justify-content: flex-end;
}

.avatar {
  width: 38px;
  height: 38px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.avatar-ai {
  background: #e8f3ff;
  color: #165dff;
}

.avatar-human {
  background: #1d3557;
  color: white;
}

.msg-body {
  max-width: min(680px, 72%);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.msg-sender {
  font-size: 12px;
  color: #86909c;
}

.msg-bubble {
  padding: 14px 16px;
  border-radius: 16px;
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
}

.bubble-ai {
  background: white;
  color: #1d2129;
  border-top-left-radius: 6px;
}

.bubble-human {
  background: #165dff;
  color: white;
  border-top-right-radius: 6px;
}



.coach-feedback {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
  padding: 8px 12px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 1.5;
}
.coach-feedback--info { background: #e8f3ff; color: #1d2129; }
.coach-feedback--good { background: #e8ffea; color: #1d2129; }
.coach-feedback--warning { background: #fff7e8; color: #1d2129; }
.coach-feedback__label { font-weight: 700; flex-shrink: 0; }
.stage-missing {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}
.stage-missing__label { font-size: 11px; color: #86909c; }
.stage-missing__tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #e5e6eb;
  color: #4e5969;
}
.suggested-question-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 12px;
  padding: 8px 10px;
}
.suggested-question-chip__cat {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 6px;
  background: #e8f3ff;
  color: #165dff;
}
.suggested-question-chip__text { flex: 1; min-width: 0; }

.suggested-questions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 10px;
}

.suggested-questions__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.suggested-questions__title {
  font-size: 12px;
  font-weight: 700;
  color: #4e5969;
}

.suggested-questions__hint {
  font-size: 11px;
  color: #86909c;
}

.suggested-questions__list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.suggested-question-chip {
  max-width: 100%;
  border: 1px solid #d9e8ff;
  background: #fff;
  color: #1d2129;
  border-radius: 999px;
  padding: 8px 12px;
  font-size: 12px;
  line-height: 1.45;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.suggested-question-chip:hover:not(:disabled) {
  border-color: #165dff;
  background: #e8f3ff;
}

.suggested-question-chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-input-area {
  padding: 12px 16px;
  background: #f2f3f5;
  border-top: 1px solid #e5e6eb;
}

.typing-indicator {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.typing-indicator span {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #c9cdd4;
  animation: blink 1.2s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.3s;
}

.brief-container {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px;
}

.brief-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brief-id {
  font-size: 12px;
  color: #86909c;
  font-weight: 700;
}

.brief-main-title {
  margin: 12px 0 0;
  font-size: 28px;
  color: #1d2129;
}

.brief-section {
  margin-top: 24px;
}

.brief-label {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: #1d2129;
  margin-bottom: 12px;
}

.label-line {
  width: 24px;
  height: 2px;
  background: #165dff;
}

.label-line.grey {
  background: #94a3b8;
}

.label-line.blue {
  background: #1d3557;
}

.abstract-box,
.original-source-box,
.structured-grid {
  border-radius: 14px;
  background: white;
  padding: 16px 18px;
  line-height: 1.8;
  color: #4e5969;
  border: 1px solid #e5e6eb;
}

.dispatch-box {
  background: #f2f3f5;
  border-left: 4px solid #165dff;
}

.sub-title {
  font-weight: 700;
  color: #1d3557;
}

.sop-text {
  margin-top: 10px;
  font-size: 13px;
  color: #4e5969;
  line-height: 1.8;
}

@keyframes blink {
  0%, 80%, 100% {
    opacity: 0.35;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-2px);
  }
}

@media (max-width: 960px) {
  .training-page {
    flex-direction: column;
    height: auto;
  }

  .info-panel {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid #e5e6eb;
  }

  .msg-body {
    max-width: 84%;
  }
}
</style>
