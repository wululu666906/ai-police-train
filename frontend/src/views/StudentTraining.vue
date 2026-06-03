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
            class="scene-role-card"
            :class="{
              'scene-role-card--selected': targetRoleName === role.name,
              'scene-role-card--speaking': isRoleAvatarSpeaking(role.name),
              'scene-role-card--thinking': isRoleAvatarThinking(role.name),
            }"
            :disabled="!role.speakable || isLoading || isPlayingReplies"
            @click="toggleTargetRole(role)"
          >
            <RoleSpeakingAvatar
              :name="role.name"
              :speaking="isRoleAvatarSpeaking(role.name)"
              :thinking="isRoleAvatarThinking(role.name)"
              :primary="role.is_primary"
              :risk="(role.risk ?? 0) >= 70"
              :size="48"
            />
            <span class="scene-role-card__name">{{ role.name }}</span>
            <span class="scene-role-card__meta">
              {{ role.state_label || role.role_type || '角色' }}
              <template v-if="role.emotion != null"> · 情绪{{ role.emotion }}</template>
            </span>
            <span v-if="isRoleAvatarSpeaking(role.name)" class="scene-role-card__badge">正在说话</span>
            <span v-else-if="isRoleAvatarThinking(role.name)" class="scene-role-card__badge scene-role-card__badge--think">
              准备发言
            </span>
          </button>
        </div>
      </div>

      <div v-if="showStateDebug && stateDebug.contract" class="panel-section state-debug-panel">
        <h3 class="panel-title">
          <van-icon name="setting-o" />
          状态契约（管理员）
        </h3>
        <div class="state-debug-tags">
          <span class="state-debug-tag">{{ stateDebug.contract?.primary_affect || '—' }}</span>
          <span v-if="stateInfluenceMetrics.consistency_rate != null" class="state-debug-tag">
            一致率 {{ Math.round((stateInfluenceMetrics.consistency_rate || 0) * 100) }}%
          </span>
          <span v-if="stateInfluenceMetrics.stage_requirement_hit_rate != null" class="state-debug-tag">
            阶段命中 {{ Math.round((stateInfluenceMetrics.stage_requirement_hit_rate || 0) * 100) }}%
          </span>
        </div>
        <p class="state-debug-hint">{{ stateDebug.contract?.tone_hint || '' }}</p>
        <p v-if="stateDebug.postcheck?.validation" class="state-debug-meta">
          后验：{{ stateDebug.postcheck.validation.ok ? '通过' : '未通过' }}
          （{{ stateDebug.postcheck.validation.score }}）
        </p>
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
            <div class="avatar avatar-ai" :title="msg.speakerName || roleInfo.name">
              <span class="avatar-initial">{{ (msg.speakerName || roleInfo.name).slice(0, 1) }}</span>
            </div>
            <div class="msg-body">
              <span class="msg-sender">{{ msg.speakerName || roleInfo.name }}</span>
              <div class="msg-bubble bubble-ai">{{ msg.content }}</div>
            </div>
          </div>

          <div v-else class="msg-row msg-human">
            <div class="msg-body">
              <span class="msg-sender">
                执法民警
                <span v-if="msg.inputSource === 'voice'" class="msg-source-tag">语音</span>
              </span>
              <div class="msg-bubble bubble-human">{{ msg.content }}</div>
            </div>
            <div class="avatar avatar-human">
              <van-icon name="friends-o" size="20" />
            </div>
          </div>
        </div>

        <div v-if="isLoading && !isPlayingReplies" class="msg-row msg-ai">
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
          @send="sendMessage()"
          @voice-send="sendVoiceMessage"
        />
      </div>
    </div>

    <van-popup
      v-model:show="showCaseBrief"
      position="center"
      class="case-brief-popup"
      :style="{ width: '936px', maxWidth: '94vw' }"
      :overlay="true"
      :close-on-click-overlay="false"
      :duration="0"
    >
      <div class="brief-dialog">
        <div class="brief-dialog__header">
          <div class="brief-dialog__title">接警简报与现场信息</div>
          <button type="button" class="brief-dialog__close" aria-label="关闭" @click="showCaseBrief = false">×</button>
        </div>

        <div class="brief-dialog__body">
          <div class="brief-dialog__intro">
            <span class="brief-dialog__case-title">{{ caseInfo.title }}</span>
          </div>

          <div class="brief-dialog__scroll">
            <div class="brief-dialog__section">
              <div class="brief-dialog__section-title">110 接警简报</div>
              <div class="brief-dialog__paragraph brief-dialog__paragraph--quote">
                {{ caseInfo.dispatchBrief || '指挥中心暂未下发更详细的接警简报。' }}
              </div>
            </div>

            <div class="brief-dialog__section">
              <div class="brief-dialog__section-title">现场第一印象</div>
              <div class="brief-dialog__paragraph">
                {{ caseInfo.firstImpression || '你已到达现场，暂未发现特别明显的异常情况。' }}
              </div>
            </div>

            <div class="brief-dialog__section">
              <div class="brief-dialog__section-title">执法提示</div>
              <ol class="brief-dialog__list">
                <li>先核实对话对象身份与所处位置。</li>
                <li>结合场景目标围绕时间、地点、人物、经过展开询问。</li>
                <li>注意控制现场情绪，避免冲突升级。</li>
                <li>留意对方表述中的矛盾点、隐瞒点和风险点。</li>
              </ol>
            </div>
          </div>
        </div>

        <div class="brief-dialog__footer">
          <label class="brief-dialog__suppress">
            <input
              class="brief-dialog__checkbox"
              type="checkbox"
              :checked="suppressedBriefThisSession"
              @change="onSuppressCheckboxChange"
            />
            <span class="brief-dialog__suppress-text">今日不再提示</span>
          </label>

          <div class="brief-dialog__actions">
            <button type="button" class="brief-dialog__btn brief-dialog__btn--ghost" @click="showCaseBrief = false">
              取消
            </button>
            <button type="button" class="brief-dialog__btn brief-dialog__btn--primary" @click="handleBriefStartTraining">
              开始训练
            </button>
          </div>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showLoadingToast, showToast } from 'vant'
import request from '../utils/request'
import TrainingInputBar from '../components/TrainingInputBar.vue'
import RoleSpeakingAvatar from '../components/RoleSpeakingAvatar.vue'

const route = useRoute()
const router = useRouter()

const sessionId = ref(route.params.id)
const inputMessage = ref('')
const isLoading = ref(false)
const isPlayingReplies = ref(false)
const speakingRoleName = ref('')
const showCaseBrief = ref(false)
const suppressedBriefThisSession = ref(false)

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
  affect_label?: string
  is_active?: boolean
  is_targeted?: boolean
}
const sceneRoles = ref<SceneRoleBrief[]>([])
const isAdminUser = computed(() => localStorage.getItem('role') === 'admin')
const showStateDebug = computed(() => isAdminUser.value)
const stateDebug = ref<{ contract?: Record<string, unknown>; postcheck?: { validation?: { ok?: boolean; score?: number } } }>({})
const stateInfluenceMetrics = ref<{
  consistency_rate?: number
  stage_requirement_hit_rate?: number
  turn_count?: number
}>({})
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
const chatHistory = ref<
  Array<{ id: number; role: string; content: string; speakerName?: string; inputSource?: 'voice' | 'text' }>
>([])



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

const SPEAK_MS_PER_CHAR = 42
const SPEAK_MIN_MS = 850
const SPEAK_MAX_MS = 4500
const REPLY_GAP_MS = 260

const sleep = (ms: number) => new Promise<void>((resolve) => {
  window.setTimeout(resolve, ms)
})

const estimateSpeakDuration = (text: string) => {
  const len = String(text || '').trim().length
  return Math.min(SPEAK_MAX_MS, Math.max(SPEAK_MIN_MS, len * SPEAK_MS_PER_CHAR))
}

const guessThinkingRoleName = () => {
  if (targetRoleName.value) return targetRoleName.value
  const primary = sceneRoles.value.find((role) => role.is_primary)
  if (primary?.name) return primary.name
  const first = sceneRoles.value.find((role) => role.speakable !== false && role.name)
  return first?.name || roleInfo.name
}

const thinkingRoleLabel = computed(() => guessThinkingRoleName())

const isRoleAvatarSpeaking = (roleName: string) => speakingRoleName.value === roleName

const isRoleAvatarThinking = (roleName: string) => {
  if (speakingRoleName.value) return false
  if (!isLoading.value || isPlayingReplies.value) return false
  return roleName === thinkingRoleLabel.value
}

const collectAssistantReplyTurns = (res: any) => {
  const turns = Array.isArray(res?.reply_turns) ? res.reply_turns : []
  if (turns.length) {
    return turns
      .filter((item: any) => String(item?.content || '').trim())
      .map((item: any) => ({
        content: String(item.content),
        speakerName: String(item.speaker_name || item.speakerName || roleInfo.name).trim() || roleInfo.name,
      }))
  }
  const sequence =
    Array.isArray(res?.reply_sequence) && res.reply_sequence.length
      ? res.reply_sequence
      : [res?.response].filter(Boolean)
  return sequence
    .filter((item: string) => String(item || '').trim())
    .map((content: string) => ({
      content: String(content),
      speakerName: roleInfo.name,
    }))
}

const playAssistantReplies = async (res: any, baseId: number) => {
  const items = collectAssistantReplyTurns(res)
  if (!items.length) return false

  isPlayingReplies.value = true
  try {
    for (let index = 0; index < items.length; index += 1) {
      const item = items[index]
      speakingRoleName.value = item.speakerName
      chatHistory.value.push({
        id: baseId + index,
        role: 'assistant',
        content: item.content,
        speakerName: item.speakerName,
      })
      await nextTick()
      scrollToBottom()
      await sleep(estimateSpeakDuration(item.content))
      if (index < items.length - 1) {
        await sleep(REPLY_GAP_MS)
      }
    }
  } finally {
    speakingRoleName.value = ''
    isPlayingReplies.value = false
  }
  return true
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

const normalizeDifficulty = (value: string) => {
  const text = String(value || '').trim()
  if (['简单', '低'].includes(text)) return '低'
  if (['困难', '高'].includes(text)) return '高'
  return text || '中等'
}

const resolveRequestErrorMessage = (error: any, fallback: string) => {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail.trim()
  if (Array.isArray(detail) && detail.length) {
    return detail.map((item: any) => item?.msg || item?.message || String(item)).filter(Boolean).join('；')
  }
  if (!error?.response) {
    return '无法连接后端，请确认已运行 backend\\start.ps1（http://127.0.0.1:8000）'
  }
  return fallback
}

const fetchSessionData = async () => {
  if (!sessionId.value) {
    showToast('训练会话无效，请从训练大厅重新进入')
    router.replace('/student/hall')
    return
  }
  try {
    const res: any = await request.get(`/training/session/${sessionId.value}`, { _skipErrorToast: true } as any)
    caseInfo.title = res.case_title
    caseInfo.sceneName = res.scene_name
    caseInfo.difficulty = normalizeDifficulty(res.difficulty || '中等')
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

    // 进入对话即展示案件信息（学员若选择“本次不再提示”则本会话内不再自动弹出）
    suppressedBriefThisSession.value = isBriefSuppressedInSession()
    if (!suppressedBriefThisSession.value) {
      showCaseBrief.value = true
    }
  } catch (error: any) {
    showToast(resolveRequestErrorMessage(error, '获取训练数据失败'))
    if (error?.response?.status === 404) {
      setTimeout(() => router.replace('/student/hall'), 1500)
    }
  }
}

const getBriefSuppressKey = () => `student_training_brief_suppressed_${String(sessionId.value || '')}`

const isBriefSuppressedInSession = () => {
  try {
    return sessionStorage.getItem(getBriefSuppressKey()) === '1'
  } catch {
    return false
  }
}

const suppressBriefInSession = () => {
  suppressedBriefThisSession.value = true
  try {
    sessionStorage.setItem(getBriefSuppressKey(), '1')
  } catch {
    // ignore
  }
}

const clearBriefSuppressedInSession = () => {
  suppressedBriefThisSession.value = false
  try {
    sessionStorage.removeItem(getBriefSuppressKey())
  } catch {
    // ignore
  }
}

const onSuppressCheckboxChange = (event: Event) => {
  const checked = Boolean((event.target as HTMLInputElement | null)?.checked)
  if (checked) suppressBriefInSession()
  else clearBriefSuppressedInSession()
}

const handleBriefStartTraining = () => {
  showCaseBrief.value = false
}

const sendVoiceMessage = (transcript: string) => {
  void sendMessage(transcript, 'voice')
}

const sendMessage = async (content?: string, inputSource: 'voice' | 'text' = 'text') => {
  const msg = String(content ?? inputMessage.value).trim()
  if (!msg || isLoading.value) return

  syncTargetFromMessage(msg)
  const pendingId = Date.now()
  chatHistory.value.push({ id: pendingId, role: 'human', content: msg, inputSource })
  if (inputSource === 'text') {
    inputMessage.value = ''
  }
  isLoading.value = true
  scrollToBottom()

  try {
    const res: any = await request.post(`/training/chat/${sessionId.value}`, {
      role: 'user',
      content: msg,
      target_role_name: targetRoleName.value || undefined,
    })

    const hasAssistantReply = await playAssistantReplies(res, Date.now() + 1)

    if (Array.isArray(res.scene_roles) && res.scene_roles.length) {
      sceneRoles.value = res.scene_roles
    }
    routingSummary.value = String(res.routing_summary || '').trim()
    addressingWarning.value = String(res.addressing_warning || '').trim()
    applyGuidancePayload(res)
    if (isAdminUser.value) {
      stateDebug.value = {
        contract: res.state_contract,
        postcheck: res.last_postcheck,
      }
      stateInfluenceMetrics.value = res.state_influence_metrics || {}
    }
    currentState.value.emotion = res.updated_emotion
    currentState.value.trust = res.updated_trust
    currentState.value.risk = res.updated_risk ?? currentState.value.risk
    currentState.value.clarity = res.updated_clarity ?? currentState.value.clarity

    if (hasAssistantReply) {
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
    } else {
      showToast('AI 回复出错，请稍后重试')
    }
  } catch (error) {
    chatHistory.value = chatHistory.value.filter((item) => item.id !== pendingId)
    if (inputSource === 'text') {
      inputMessage.value = msg
    }
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
  const normalized = normalizeDifficulty(diff)
  if (normalized === '低') return '#00B42A'
  if (normalized === '高') return '#F53F3F'
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
:global(html),
:global(body) {
  height: 100%;
  background: #f7f8fa;
}

.scene-role-hint {
  margin: 0 0 10px;
  font-size: 12px;
  color: #86909c;
  line-height: 1.5;
}

.scene-role-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.scene-role-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  border: 1px solid #e5e6eb;
  background: #fff;
  border-radius: 12px;
  padding: 10px 10px;
  cursor: pointer;
  text-align: center;
  min-width: 96px;
  max-width: 108px;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.scene-role-card--selected {
  border-color: #165dff;
  background: #f7fbff;
  box-shadow: 0 2px 10px rgba(22, 93, 255, 0.12);
}

.scene-role-card--speaking {
  border-color: #8aa3c4;
  background: #f6f8fb;
  box-shadow: 0 2px 10px rgba(90, 127, 168, 0.15);
}

.scene-role-card--thinking {
  border-color: #b8c9de;
  background: #f8fafc;
}

.scene-role-card:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.scene-role-card__name {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #1d2129;
  line-height: 1.2;
}

.scene-role-card__meta {
  display: block;
  font-size: 10px;
  color: #86909c;
  line-height: 1.35;
  min-height: 26px;
}

.scene-role-card__badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  color: #3d5268;
  background: #e2e8f0;
  letter-spacing: 0.04em;
}

.scene-role-card__badge--think {
  color: #5a6f86;
  background: #edf1f5;
}

.state-debug-panel {
  border: 1px dashed #c9d4e3;
  background: #f8fafc;
}

.state-debug-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.state-debug-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: #e8f0fe;
  color: #1d3557;
  font-weight: 600;
}

.state-debug-hint {
  font-size: 11px;
  color: #64748b;
  line-height: 1.45;
  margin: 0;
}

.state-debug-meta {
  font-size: 10px;
  color: #94a3b8;
  margin: 6px 0 0;
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
  height: 100vh;
  overflow: hidden;
  overflow-x: hidden;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Inter', sans-serif;
  background: #f7f8fa;
}

.info-panel {
  width: 296px;
  background: white;
  border-right: 1px solid #e5e6eb;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  overflow-x: hidden;
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
  overflow-x: hidden;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  overflow-x: hidden;
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

.avatar-initial {
  font-size: 15px;
  font-weight: 700;
  color: #165dff;
  line-height: 1;
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
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.msg-source-tag {
  font-size: 10px;
  font-weight: 700;
  color: #165dff;
  background: rgba(22, 93, 255, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
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
  overflow-x: hidden;
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

.case-brief-popup {
  background: transparent;
  border-radius: 10px;
}

.brief-dialog {
  background: #fff;
  border-radius: 13px;
  border: 1px solid #e5e6eb;
  box-shadow: 0 20px 52px rgba(15, 23, 42, 0.16);
  overflow: hidden;
}

.brief-dialog__header {
  height: 73px;
  padding: 0 23px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #eef0f4;
}

.brief-dialog__title {
  font-size: 24px;
  font-weight: 800;
  color: #0f1419;
}

.brief-dialog__close {
  width: 43px;
  height: 43px;
  border: none;
  background: transparent;
  color: #86909c;
  font-size: 26px;
  line-height: 1;
  cursor: pointer;
}

.brief-dialog__body {
  padding: 18px 23px 0;
}

.brief-dialog__intro {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 13px;
}

.brief-dialog__case-title {
  font-size: 19px;
  font-weight: 800;
  color: #0f1419;
}

.brief-dialog__scroll {
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  padding: 16px 17px;
  height: 390px;
  overflow: auto;
  background: #fff;
}

.brief-dialog__section + .brief-dialog__section {
  margin-top: 16px;
}

.brief-dialog__section-title {
  font-size: 16px;
  font-weight: 800;
  color: #0f1419;
  margin-bottom: 10px;
}

.brief-dialog__paragraph {
  font-size: 16px;
  line-height: 1.8;
  font-weight: 500;
  color: #1a1f26;
}

.brief-dialog__paragraph--quote {
  background: #f0f2f5;
  border-left: 5px solid #165dff;
  border-radius: 8px;
  padding: 13px 14px;
  color: #14181f;
  font-weight: 600;
}

.brief-dialog__list {
  margin: 0;
  padding-left: 22px;
  font-size: 16px;
  line-height: 1.8;
  font-weight: 500;
  color: #1a1f26;
}

.brief-dialog__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 23px;
  border-top: 1px solid #eef0f4;
  margin-top: 18px;
}

.brief-dialog__suppress {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  user-select: none;
  cursor: pointer;
}

.brief-dialog__checkbox {
  width: 19px;
  height: 19px;
}

.brief-dialog__suppress-text {
  font-size: 17px;
  font-weight: 700;
  color: #2b2f36;
}

.brief-dialog__actions {
  display: inline-flex;
  align-items: center;
  gap: 14px;
}

.brief-dialog__btn {
  min-width: 114px;
  height: 44px;
  padding: 0 17px;
  border-radius: 8px;
  font-size: 17px;
  font-weight: 700;
  cursor: pointer;
  border: 1px solid transparent;
}

.brief-dialog__btn--ghost {
  background: #f6f7f9;
  border-color: #e5e6eb;
  color: #1d2129;
}

.brief-dialog__btn--primary {
  background: #4f8ef7;
  border-color: #4f8ef7;
  color: #fff;
}

.brief-meta {
  display: flex;
  align-items: center;
  gap: 10px;
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
  background: #f6f7f9;
  border-left: 4px solid #165dff;
}

.brief-paragraph--plain {
  border: none;
  padding: 6px 0 0;
  background: transparent;
}

.brief-paragraph--highlight {
  border-radius: 14px;
}

.brief-tip-block {
  padding: 14px 16px;
}

.brief-tip-list {
  margin: 10px 0 0;
  padding-left: 18px;
  color: #4e5969;
  font-size: 13px;
  line-height: 1.85;
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
