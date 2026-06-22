<template>
  <div class="training-page">
    <div v-if="isSessionBooting" class="training-status-panel">
      <van-loading color="#2563eb" vertical>正在加载训练会话...</van-loading>
    </div>

    <div v-else-if="trainingLoadError" class="training-status-panel training-status-panel--error">
      <van-icon name="warning-o" size="44" color="#f59e0b" />
      <h2>训练会话加载失败</h2>
      <p>{{ trainingLoadError }}</p>
      <div class="training-status-actions">
        <van-button plain size="small" @click="fetchSessionData">重新加载</van-button>
        <van-button type="primary" size="small" @click="router.replace('/student/hall')">返回训练大厅</van-button>
      </div>
    </div>

    <template v-else>
    <header class="training-header">
      <div class="training-header__case">
        <span class="training-header__label">案件名称</span>
        <div class="training-header__title-row">
          <span class="training-header__title">{{ caseInfo.title }}</span>
          <span class="training-header__badge">{{ normalizeDifficulty(caseInfo.difficulty) }}难度</span>
        </div>
      </div>
      <div class="training-header__right">
        <span>当前对话</span>
        <span class="training-header__target">{{ targetRoleName || roleInfo.name }}</span>
      </div>
    </header>

    <div class="training-body">
    <aside class="info-panel">
      <div class="panel-scroll">
        <div class="panel-section panel-section--tertiary case-info-section">
          <h3 class="panel-title">
            <van-icon name="description" />
            案件信息
          </h3>
          <div class="case-ref-card">
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
            <button type="button" class="brief-link" @click="showCaseBrief = true">
              查看训练简报
              <van-icon name="arrow" />
            </button>
          </div>
        </div>

        <div class="panel-section panel-section--primary stage-section">
          <h3 class="panel-title">
            <van-icon name="send-gift-o" />
            训练阶段
          </h3>
          <div class="stage-hero">
            <span class="stage-tag">当前阶段</span>
            <div class="stage-name-text">{{ caseInfo.currentStage }}</div>
            <div class="goal-label">本阶段目标</div>
            <div class="goal-text">{{ caseInfo.currentStageGoal || '请开始与对方交流，获取关键事实。' }}</div>
          </div>
        </div>

        <div v-if="sceneRoles.length" class="panel-section panel-section--primary scene-roles-section">
          <h3 class="panel-title">
            <van-icon name="friends-o" />
            现场角色
          </h3>
          <p class="scene-role-hint">点击角色，或在输入框写「姓名，」指定对话对象</p>
          <div class="scene-role-list">
            <div
              v-for="role in visibleSceneRoles"
              :key="role.id"
              class="scene-role-stack"
            >
              <button
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
                  :avatar-url="role.avatar_url"
                  :avatar-id="role.avatar_id"
                  :speaking="isRoleAvatarSpeaking(role.name)"
                  :thinking="isRoleAvatarThinking(role.name)"
                  :primary="role.is_primary"
                  :risk="(role.risk ?? 0) >= 70"
                  :size="28"
                />
                <span class="scene-role-card__body">
                  <span class="scene-role-card__name">{{ role.name }}</span>
                  <span class="scene-role-card__meta">
                    {{ role.state_label || role.role_type || '角色' }}
                    <template v-if="role.emotion != null"> · 情绪{{ role.emotion }}</template>
                  </span>
                </span>
                <span v-if="isRoleAvatarSpeaking(role.name)" class="scene-role-card__badge">正在说话</span>
                <span v-else-if="isRoleAvatarThinking(role.name)" class="scene-role-card__badge scene-role-card__badge--think">
                  准备发言
                </span>
              </button>

              <div class="role-state-table">
                <div v-for="axis in roleStateAxes" :key="axis.key" class="role-state-axis">
                  <div class="role-state-axis__head">
                    <span>{{ axis.label }}</span>
                    <span class="role-state-axis__values">
                      <strong :style="{ color: axisColor(axis.key, axisValue(role, axis.key)) }">
                        {{ axisValue(role, axis.key) }}
                      </strong>
                      <span class="role-state-delta" :class="deltaClass(axisDelta(role, axis.key))">
                        {{ formatDelta(axisDelta(role, axis.key)) }}
                      </span>
                    </span>
                  </div>
                  <div class="role-state-track">
                    <div
                      class="role-state-fill"
                      :class="axis.fillClass"
                      :style="{ width: axisValue(role, axis.key) + '%' }"
                    ></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <button
            v-if="hiddenSceneRoleCount > 0"
            type="button"
            class="scene-role-toggle"
            @click="showAllRoles = !showAllRoles"
          >
            {{ showAllRoles ? '收起角色' : `展开其余 ${hiddenSceneRoleCount} 个角色` }}
          </button>
        </div>

        <div class="panel-section panel-section--secondary facts-section">
          <h3 class="panel-title">
            <van-icon name="bookmark-o" />
            已获取信息
            <span class="fact-count">{{ revealedInfo.length }}</span>
          </h3>
          <div class="fact-list">
            <div v-if="revealedInfo.length === 0" class="fact-empty">
              <van-icon name="info-o" size="20" color="#C9CDD4" />
              <span>暂未获取关键线索</span>
            </div>
            <div v-for="(info, idx) in revealedInfo" :key="idx" class="fact-item">
              <van-icon name="success" color="#00B42A" />
              <span>{{ info }}</span>
            </div>
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
      <TrainingFaceGuard
        v-if="sessionId"
        ref="faceGuardRef"
        class="training-face-guard"
        :session-id="sessionId"
        :mode="faceVerified ? 'monitor' : 'gate'"
        @verified="handleFaceVerified"
        @failed="handleFaceFailed"
        @terminated="handleFaceTerminated"
      />
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
            <div
              class="avatar avatar-ai"
              :title="msg.speakerName || roleInfo.name"
              :style="{ background: getAvatarBg(msg.avatarId), border: 'none' }"
            >
              <img
                v-if="msg.avatarUrl"
                :src="msg.avatarUrl"
                :alt="msg.speakerName || roleInfo.name"
                class="avatar-img"
              />
              <span v-else class="avatar-initial">{{ (msg.speakerName || roleInfo.name).slice(0, 1) }}</span>
            </div>
            <div class="msg-body">
              <span class="msg-sender" :style="{ color: getAvatarBg(msg.avatarId) }">
                {{ msg.speakerName || roleInfo.name }}
              </span>
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
          :disabled="isLoading || !faceVerified || faceTerminated"
          @send="sendMessage()"
          @voice-send="sendVoiceMessage"
          @voice-event="recordVoiceMetric"
        />
      </div>
    </div>
    </div>
    </template>

    <van-popup
      v-model:show="showCaseBrief"
      position="center"
      class="case-brief-popup"
      :style="{ width: 'min(720px, 96vw)', maxWidth: '96vw' }"
      :overlay="true"
      :close-on-click-overlay="false"
      :duration="0"
    >
      <div class="brief-dialog">
        <div class="brief-page">
          <div class="brief-head">
            <button type="button" class="brief-back-link" :disabled="isReturningToHall" @click="handleBriefReturnToHall">
              <van-icon name="arrow-left" />
              {{ isReturningToHall ? '正在返回...' : '返回训练大厅' }}
            </button>

            <section class="brief-hero">
              <span class="brief-type-pill">{{ caseInfo.caseType || '训练案件' }}</span>
              <h1>{{ caseInfo.title }}</h1>
              <p>{{ caseInfo.sceneName || '训练场景' }}</p>
            </section>
          </div>

          <div class="brief-layout brief-layout--single">
            <main class="brief-card brief-main">
              <section class="brief-info-section">
                <h2>{{ isIntakeScene ? '110 接警状态' : '110 接警简报' }}</h2>
                <div class="brief-text-box">
                  <p>{{ caseInfo.dispatchBrief || (isIntakeScene ? '110 有新报警来电，等待接听。' : '指挥中心暂未下发更详细的接警简报。') }}</p>
                  <template v-if="!isIntakeScene">
                    <p>时间：{{ briefCaseTime }}</p>
                    <p>地点：{{ briefCaseLocation }}</p>
                  </template>
                </div>
              </section>

              <section v-if="!isIntakeScene" class="brief-info-section">
                <h2>现场第一印象</h2>
                <div class="brief-text-box brief-text-box--plain">
                  {{ caseInfo.firstImpression || '你已到达现场，暂未发现特别明显的异常情况。' }}
                </div>
              </section>

              <section class="brief-info-section">
                <h2>执法提示</h2>
                <div class="brief-text-box">
                  <ol>
                    <li v-for="tip in (isIntakeScene ? intakeBriefTips : defaultBriefTips)" :key="tip">{{ tip }}</li>
                  </ol>
                </div>
              </section>
            </main>
          </div>

          <div class="brief-bottom">
            <section class="brief-warm-tip">
              <strong><van-icon name="info-o" /> 温馨提示</strong>
              <span>{{ isIntakeScene ? '请确认已进入110接警状态，随后报警人将先开口说明情况；你再按规范顺序展开问询。' : '请阅读以上简报与现场信息，确认后进入对话训练。' }}</span>
            </section>

            <footer class="brief-actions">
              <label class="brief-remember">
                <input type="checkbox" :checked="suppressedBriefThisSession" @change="onSuppressCheckboxChange" />
                <span>不再提示</span>
              </label>
              <button type="button" class="brief-start-btn" @click="handleBriefStartTraining">
                确认，进入对话训练
                <van-icon name="arrow" />
              </button>
            </footer>
          </div>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showLoadingToast, showToast } from 'vant'
import request from '../utils/request'
import TrainingInputBar from '../components/TrainingInputBar.vue'
import RoleSpeakingAvatar from '../components/RoleSpeakingAvatar.vue'
import TrainingFaceGuard from '../components/TrainingFaceGuard.vue'

const AVATAR_PALETTE = [
  '#4F46E5', '#0891B2', '#059669', '#D97706', '#DC2626',
  '#7C3AED', '#0E7490', '#047857', '#B45309', '#BE123C',
  '#6366F1', '#0284C7', '#16A34A', '#D97706', '#E11D48',
  '#8B5CF6', '#0EA5E9', '#22C55E', '#F59E0B', '#EF4444',
]

function getAvatarBg(avatarId?: number | null): string {
  if (avatarId != null && avatarId >= 1 && avatarId <= AVATAR_PALETTE.length) {
    return AVATAR_PALETTE[avatarId - 1]
  }
  return '#e2e8f0'
}

const route = useRoute()
const router = useRouter()

const sessionId = ref(String(route.params.id || ''))
const inputMessage = ref('')
const isLoading = ref(false)
const isSessionBooting = ref(true)
const trainingLoadError = ref('')
const isPlayingReplies = ref(false)
const speakingRoleName = ref('')
const showCaseBrief = ref(false)
const suppressedBriefThisSession = ref(false)
const isReturningToHall = ref(false)
const faceVerified = ref(false)
const faceTerminated = ref(false)
const faceGuardRef = ref<InstanceType<typeof TrainingFaceGuard> | null>(null)
let multimodalFrameTimer: number | null = null

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
  sceneKind: 'generic',
  dialogueMode: 'officer_led',
  structuredData: null as any
})

const isIntakeScene = computed(() => caseInfo.sceneKind === 'intake' || caseInfo.dialogueMode === 'caller_first')

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
  emotion_delta?: number
  cooperation_delta?: number
  risk_delta?: number
  clarity_delta?: number
  state_label?: string
  affect_label?: string
  is_active?: boolean
  is_targeted?: boolean
  avatar_id?: number
  avatar_url?: string
}

interface SuggestedQuestionItem {
  text: string
  category?: string
  target_role_name?: string | null
}

const sceneRoles = ref<SceneRoleBrief[]>([])
const showAllRoles = ref(false)
const routingSummary = ref('')
const addressingWarning = ref('')
const targetRoleName = ref('')
const communicationFeedback = ref<{ level?: string; message?: string }>({ message: '' })
const stageMissing = ref<string[]>([])
const suggestedQuestionItems = ref<SuggestedQuestionItem[]>([])
const assessmentProgress = ref<any>(null)
const completedPointIds = ref<string[]>([])
const completedActionIds = ref<string[]>([])
const autoFinishReady = ref(false)

const revealedInfo = ref<string[]>([])
const chatHistory = ref<
  Array<{ id: number; role: string; content: string; speakerName?: string; inputSource?: 'voice' | 'text'; avatarUrl?: string; avatarId?: number }>
>([])

type RoleStateAxisKey = 'emotion' | 'cooperation' | 'risk' | 'clarity'

const roleStateAxes: Array<{ key: RoleStateAxisKey; label: string; fillClass: string }> = [
  { key: 'emotion', label: '情绪值', fillClass: 'emotion-fill' },
  { key: 'cooperation', label: '配合度', fillClass: 'trust-fill' },
  { key: 'risk', label: '失控风险', fillClass: 'risk-fill' },
  { key: 'clarity', label: '表达清晰度', fillClass: 'clarity-fill' },
]

const clampStateValue = (value: unknown, fallback = 50) => {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return fallback
  return Math.max(0, Math.min(100, Math.round(numeric)))
}

const roleAxisFallback: Record<RoleStateAxisKey, number> = {
  emotion: 50,
  cooperation: 30,
  risk: 50,
  clarity: 50,
}

const roleDeltaField: Record<RoleStateAxisKey, keyof SceneRoleBrief> = {
  emotion: 'emotion_delta',
  cooperation: 'cooperation_delta',
  risk: 'risk_delta',
  clarity: 'clarity_delta',
}

const axisValue = (role: SceneRoleBrief, key: RoleStateAxisKey) =>
  clampStateValue(role[key], roleAxisFallback[key])

const axisDelta = (role: SceneRoleBrief, key: RoleStateAxisKey) => {
  const numeric = Number(role[roleDeltaField[key]] ?? 0)
  return Number.isFinite(numeric) ? Math.round(numeric) : 0
}

const formatDelta = (value: number) => (value > 0 ? `+${value}` : value < 0 ? `${value}` : '0')

const deltaClass = (value: number) => ({
  'role-state-delta--up': value > 0,
  'role-state-delta--down': value < 0,
  'role-state-delta--flat': value === 0,
})

const axisColor = (key: RoleStateAxisKey, value: number) => {
  if (key === 'emotion') return value > 70 ? '#F53F3F' : '#FF7D00'
  if (key === 'cooperation') return '#165DFF'
  if (key === 'risk') return value > 70 ? '#C2410C' : '#EA580C'
  return value < 40 ? '#7C3AED' : '#0F766E'
}

const orderedSceneRoles = computed(() =>
  [...sceneRoles.value].sort((a, b) => {
    const score = (role: SceneRoleBrief) => {
      if (targetRoleName.value && role.name === targetRoleName.value) return 0
      if (role.is_primary) return 1
      if (role.speakable !== false) return 2
      return 3
    }
    return score(a) - score(b)
  })
)
const visibleSceneRoles = computed(() => (showAllRoles.value ? orderedSceneRoles.value : orderedSceneRoles.value.slice(0, 3)))
const hiddenSceneRoleCount = computed(() => Math.max(0, orderedSceneRoles.value.length - 3))



const structuredTimeline = computed(() => {
  const data = caseInfo.structuredData || {}
  return Array.isArray(data.timeline) ? data.timeline.map((item: any) => String(item)).filter(Boolean) : []
})
const extractBriefValue = (patterns: RegExp[], fallback: string) => {
  const source = [caseInfo.dispatchBrief, caseInfo.caseBackground, caseInfo.caseOriginalContent, structuredTimeline.value.join('；')]
    .filter(Boolean)
    .join('；')
  for (const pattern of patterns) {
    const match = source.match(pattern)
    if (match?.[1]) return match[1].trim()
  }
  return fallback
}
const briefCaseTime = computed(() =>
  extractBriefValue(
    [
      /(\d{4}年\d{1,2}月\d{1,2}日\d{1,2}时\d{1,2}分?)/,
      /(\d{4}-\d{1,2}-\d{1,2}\s*\d{1,2}:\d{1,2})/,
      /(\d{1,2}:\d{2})/,
    ],
    '训练中核实',
  )
)
const briefCaseLocation = computed(() =>
  extractBriefValue(
    [
      /(?:地点|位于|发生在|称)(?:：|:)?([^，。,；;]{4,28}(?:区域|路口|门口|小区|店|所|街|路|现场))/,
      /([\u4e00-\u9fa5A-Za-z0-9]{2,16}(?:路|街|小区|夜市|商场|医院|学校|停车场|派出所)[^，。,；;]{0,18})/,
    ],
    '现场待核实',
  )
)
const intakeBriefTips = [
  '先听报警人说明出了什么事，不要急于追问时间、地点或联系方式。',
  '确认报警人是否安全、是否需要救助，再展开结构化问询。',
  '保持安抚语气，引导对方按“事件—安全—地点—时间—身份”顺序补充信息。',
  '留意对方表述中的风险信号、情绪变化和矛盾点。',
]
const defaultBriefTips = [
  '先核实对话对象身份与所处位置。',
  '结合场景目标围绕时间、地点、人物、经过展开询问。',
  '注意控制现场情绪，避免冲突升级。',
  '留意对方表述中的矛盾点、隐瞒点和风险点。',
]
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
  assessmentProgress.value = res?.assessment_progress || null
  completedPointIds.value = Array.isArray(res?.completed_point_ids) ? res.completed_point_ids : []
  completedActionIds.value = Array.isArray(res?.completed_action_ids) ? res.completed_action_ids : []
  autoFinishReady.value = Boolean(res?.auto_finish_ready)
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
      // Find avatar data for this speaker from scene roles
      const speakerRole = sceneRoles.value.find((r) => r.name === item.speakerName)
      chatHistory.value.push({
        id: baseId + index,
        role: 'assistant',
        content: item.content,
        speakerName: item.speakerName,
        avatarUrl: speakerRole?.avatar_url,
        avatarId: speakerRole?.avatar_id,
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
  if (isIntakeScene.value) {
    return `110 已接通，当前场景：${sceneName || '接警研判'}。请等待报警人先说明情况，${cast}。`
  }
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
    const apiHost = typeof window !== 'undefined' && window.location.hostname ? window.location.hostname : '127.0.0.1'
    return `无法连接后端，请确认已运行 backend\\start.ps1（${window.location.protocol}//${apiHost}:8000）`
  }
  return fallback
}

const fetchSessionData = async () => {
  if (!sessionId.value) {
    trainingLoadError.value = '训练会话无效，请从训练大厅重新进入。'
    isSessionBooting.value = false
    setTimeout(() => router.replace('/student/hall'), 1200)
    return
  }
  isSessionBooting.value = true
  trainingLoadError.value = ''
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
    caseInfo.sceneKind = res.scene_kind || 'generic'
    caseInfo.dialogueMode = res.dialogue_mode || 'officer_led'
    caseInfo.structuredData = safeParse(res.structured_data, null)
    roleInfo.name = res.role_name
    sceneRoles.value = Array.isArray(res.scene_roles) ? res.scene_roles : []
    showAllRoles.value = false
    applyGuidancePayload(res)
    revealedInfo.value = safeParse<string[]>(res.revealed_info, [])

    chatHistory.value = [
      {
        id: 0,
        role: 'system',
        content: buildSystemIntro(res.scene_name, res.role_name, sceneRoles.value),
      },
      ...(res.messages || []).map((message: any) => {
        const speaker = message.role === 'assistant' ? sceneRoles.value.find((r) => r.name === (message.speaker_name || '')) : null
        return {
          id: message.id,
          role: message.role === 'user' ? 'human' : message.role === 'system' ? 'system' : 'assistant',
          content: message.content,
          speakerName: message.speaker_name || undefined,
          avatarUrl: speaker?.avatar_url,
          avatarId: speaker?.avatar_id,
        }
      })
    ]
    scrollToBottom()

    // 进入对话即展示案件信息（学员若选择“本次不再提示”则本会话内不再自动弹出）
    suppressedBriefThisSession.value = isBriefSuppressedInSession()
    if (!suppressedBriefThisSession.value) {
      showCaseBrief.value = true
    }
  } catch (error: any) {
    const message = resolveRequestErrorMessage(error, '获取训练数据失败')
    trainingLoadError.value = error?.response?.status === 404
      ? '该训练会话不存在，或不属于当前登录账号。请从训练大厅重新进入。'
      : message
    showToast(trainingLoadError.value)
    if (error?.response?.status === 404) {
      setTimeout(() => router.replace('/student/hall'), 1800)
    }
  } finally {
    isSessionBooting.value = false
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

const handleBriefReturnToHall = async () => {
  if (isReturningToHall.value) return
  isReturningToHall.value = true
  try {
    await request.delete(`/training/session/${sessionId.value}`, { _skipErrorToast: true } as any)
    showToast({ type: 'success', message: '已退出本次训练' })
  } catch (error: any) {
    const status = error?.response?.status
    if (status !== 404) {
      showToast(error?.response?.data?.detail || '退出训练失败，已返回大厅')
    }
  } finally {
    isReturningToHall.value = false
    showCaseBrief.value = false
    router.replace('/student/hall')
  }
}

const sendVoiceMessage = (transcript: string) => {
  void sendMessage(transcript, 'voice')
}

const sendMessage = async (content?: string, inputSource: 'voice' | 'text' = 'text') => {
  const msg = String(content ?? inputMessage.value).trim()
  if (!msg || isLoading.value) return
  if (faceTerminated.value) {
    showToast('人脸异常次数已达上限，本次训练已中断')
    return
  }
  if (!faceVerified.value) {
    showToast('请先完成人脸身份验证')
    return
  }

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
        if (Array.isArray(updatedRes.scene_roles) && updatedRes.scene_roles.length) {
          sceneRoles.value = updatedRes.scene_roles
        }
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

const stopMultimodalSampling = () => {
  if (multimodalFrameTimer != null) {
    window.clearInterval(multimodalFrameTimer)
    multimodalFrameTimer = null
  }
}

const postMultimodalFrame = async () => {
  if (!faceVerified.value || faceTerminated.value || !sessionId.value) return
  const frame = faceGuardRef.value?.captureMultimodalFrame?.()
  if (!frame) return
  try {
    const res: any = await request.post(`/multimodal/session/${sessionId.value}/frame`, { frame }, { _skipErrorToast: true } as any)
    const detected = Boolean(res?.face?.present)
    if (!detected) return
  } catch {
    // Multimodal analysis is an enhancement layer and must not interrupt training.
  }
}

const startMultimodalSampling = () => {
  if (multimodalFrameTimer != null || !sessionId.value) return
  void postMultimodalFrame()
  multimodalFrameTimer = window.setInterval(() => {
    void postMultimodalFrame()
  }, 3000)
}

const recordVoiceMetric = (payload: {
  event_type: string
  transcript?: string
  duration_ms?: number
  audio_level?: number
  repeated?: boolean
}) => {
  if (!sessionId.value) return
  void request.post(`/multimodal/session/${sessionId.value}/voice-event`, payload, { _skipErrorToast: true } as any).catch(() => {
    // Voice metrics are best-effort and should not block the conversation loop.
  })
}

const handleFaceVerified = () => {
  if (!faceVerified.value) {
    showToast({ type: 'success', message: '身份验证通过，可以开始训练' })
  }
  faceVerified.value = true
  faceTerminated.value = false
  startMultimodalSampling()
}

const handleFaceFailed = (message: string) => {
  if (!faceVerified.value && message) {
    showToast(message)
  }
}

const handleFaceTerminated = (payload?: any) => {
  faceVerified.value = false
  faceTerminated.value = true
  stopMultimodalSampling()
  const maxFailures = Number(payload?.max_failures || 5)
  showToast(`人脸异常连续达到 ${maxFailures} 次，训练已自动中断`)
  setTimeout(() => {
    router.replace(`/student/evaluation?session_id=${sessionId.value}`)
  }, 900)
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
onBeforeUnmount(stopMultimodalSampling)
</script>

<style scoped>
:global(html),
:global(body) {
  height: 100%;
  background: #f0f4f8;
}

/* scene-role styles consolidated in sidebar block below */

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

.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  background: #f7f8fa;
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
  width: 40px;
  height: 40px;
  box-sizing: border-box;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.avatar-ai {
  background: #e8f3ff;
  color: #165dff;
  border: none;
  overflow: hidden;
}

.avatar-initial {
  font-size: 17px;
  font-weight: 700;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.12);
  line-height: 1;
}

.avatar-img {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
  display: block;
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

.msg-ai .msg-body {
  align-items: flex-start;
}

.msg-human .msg-body {
  align-items: flex-end;
}

.msg-sender {
  font-size: 13px;
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
  border-radius: 12px;
}

.bubble-human {
  background: #165dff;
  color: white;
  border-radius: 12px;
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

.training-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Inter', sans-serif;
  background: var(--police-bg);
}

.training-header {
  height: 48px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  box-shadow: none;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 20px;
  flex-shrink: 0;
}

.training-header__case {
  min-width: 0;
}

.training-header__label {
  display: block;
  font-size: 10px;
  line-height: 1.2;
  color: var(--police-text-muted);
}

.training-header__title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.training-header__title {
  max-width: min(58vw, 760px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
}

.training-header__badge {
  flex-shrink: 0;
  padding: 2px 8px;
  border-radius: 4px;
  background: #dcfce7;
  color: #16a34a;
  font-size: 11px;
  font-weight: 600;
}

.training-header__right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--police-text-muted);
  font-size: 12px;
}

.training-header__target {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 3px 12px;
  border: 1px solid #bfdbfe;
  border-radius: 20px;
  background: #eff6ff;
  color: #2563eb;
  font-weight: 700;
}

.training-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.info-panel {
  flex: 0 0 33.333%;
  width: 33.333%;
  min-width: 320px;
  max-width: none;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-right: 1px solid #e2e8f0;
  overflow: hidden;
  flex-shrink: 0;
}

.panel-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
}

.panel-section {
  margin: 10px 12px 0;
  padding: 14px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
  box-shadow: 0 0 12px rgb(0 0 0 / 4%);
}

.panel-section:last-child {
  margin-bottom: 10px;
}

.panel-section--primary {
  padding-top: 16px;
}

.panel-section--secondary {
  background: #fafbfc;
}

.panel-section--tertiary {
  background: #f8fafc;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 10px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.3;
  color: #64748b;
}

.stage-hero {
  border-left: 3px solid #082a63;
  border-radius: 0 10px 10px 0;
  background: #e8eef7;
  padding: 12px 14px;
}

.stage-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  background: #e8eef7;
  color: #082a63;
  font-size: 12px;
  font-weight: 600;
}

.stage-name-text {
  margin-top: 8px;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.4;
  color: #1e293b;
}

.goal-label {
  margin-top: 12px;
  font-size: 12px;
  color: #94a3b8;
}

.goal-text {
  margin-top: 4px;
  font-size: 13px;
  line-height: 1.6;
  color: #475569;
}

.left-suggestion-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 10px;
}

.left-suggestion {
  width: 100%;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #fff;
  color: #334155;
  padding: 8px 10px;
  font-size: 12px;
  line-height: 1.45;
  text-align: left;
  cursor: pointer;
}

.left-suggestion span {
  display: inline-block;
  margin-right: 6px;
  color: #2563eb;
  font-size: 11px;
  font-weight: 700;
}

.left-suggestion:hover:not(:disabled) {
  border-color: #2563eb;
  background: #eff6ff;
}

.scene-role-hint {
  margin: 0 0 8px;
  font-size: 12px;
  line-height: 1.5;
  color: #94a3b8;
}

.scene-role-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scene-role-stack {
  border: 1px solid var(--police-border);
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

.scene-role-card {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  width: 100%;
  padding: 8px 10px;
  border: 0;
  border-radius: 0;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
}

.scene-role-card:hover:not(:disabled) {
  background: var(--police-primary-light);
}

.scene-role-card--selected {
  background: #eff6ff;
  box-shadow: inset 3px 0 0 #2563eb;
}

.scene-role-card--speaking {
  background: #f0f9ff;
}

.scene-role-card--thinking {
  background: #f8fafc;
}

.scene-role-card:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.scene-role-card__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.scene-role-card__name {
  font-size: 14px;
  font-weight: 700;
  line-height: 1.3;
  color: #1e293b;
}

.scene-role-card__meta {
  font-size: 12px;
  line-height: 1.35;
  color: #94a3b8;
}

.scene-role-card__badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  color: #1d4ed8;
  background: #dbeafe;
  white-space: nowrap;
}

.scene-role-card__badge--think {
  color: #475569;
  background: #e2e8f0;
}

.role-state-table {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border-top: 1px solid #eef2f7;
  background: #f8fafc;
}

.role-state-axis {
  min-width: 0;
  padding: 8px 10px;
}

.role-state-axis:nth-child(odd) {
  border-right: 1px solid #e5eaf2;
}

.role-state-axis:nth-child(n + 3) {
  border-top: 1px solid #e5eaf2;
}

.role-state-axis__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 3px;
  font-size: 11px;
  line-height: 1.25;
  color: #64748b;
}

.role-state-axis__head > span:first-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.role-state-axis__values {
  display: inline-flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: 4px;
  flex: 0 0 auto;
  font-variant-numeric: tabular-nums;
}

.role-state-axis__head strong {
  font-size: 11px;
  line-height: 1;
}

.role-state-track {
  height: 5px;
  border-radius: 999px;
  background: #e2e8f0;
  overflow: hidden;
}

.role-state-fill {
  height: 100%;
  border-radius: inherit;
  transition: width 0.24s ease;
}

.role-state-delta {
  min-width: 20px;
  font-size: 11px;
  font-weight: 800;
  line-height: 1;
  text-align: right;
}

.role-state-delta--up {
  color: #16a34a;
}

.role-state-delta--down {
  color: #dc2626;
}

.role-state-delta--flat {
  color: #94a3b8;
}

.scene-role-toggle {
  width: 100%;
  margin-top: 8px;
  padding: 6px 10px;
  border: 1px dashed #bfdbfe;
  border-radius: 8px;
  background: #f8fbff;
  color: #2563eb;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.scene-role-toggle:hover {
  background: #eff6ff;
}

.fact-count {
  margin-left: auto;
  min-width: 22px;
  padding: 0 7px;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  text-align: center;
}

.fact-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 140px;
  overflow-y: auto;
}

.fact-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 12px 8px;
  font-size: 13px;
  color: #94a3b8;
  text-align: center;
}

.fact-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  line-height: 1.55;
  color: #475569;
}

.case-ref-card {
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.info-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
  font-size: 13px;
}

.info-item:last-of-type {
  margin-bottom: 10px;
}

.info-label {
  color: #94a3b8;
  flex-shrink: 0;
}

.info-value {
  color: #1e293b;
  font-weight: 600;
  text-align: right;
}

.brief-link {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
  padding: 8px 0;
  border: none;
  border-top: 1px solid #eef2f7;
  background: transparent;
  color: #2563eb;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.brief-link:hover {
  color: #1d4ed8;
}

.panel-actions {
  flex-shrink: 0;
  padding: 12px 16px;
  border-top: 1px solid #e2e8f0;
  background: #fff;
}

.finish-btn {
  height: 36px;
  border-radius: 8px;
  background: #0f1e3c !important;
  border-color: #0f1e3c !important;
  font-size: 13px;
}

.briefing-section {
  display: grid;
  gap: 6px;
}

.briefing-card,
.briefing-mini {
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  border-radius: 7px;
  padding: 7px 8px;
}

.briefing-card--dispatch {
  border-left: 3px solid #2563eb;
  background: #f8fbff;
}

.briefing-label,
.briefing-mini span {
  display: block;
  margin-bottom: 3px;
  font-size: 10px;
  font-weight: 700;
  color: #2563eb;
}

.briefing-card p,
.briefing-mini p {
  margin: 0;
  color: #334155;
  font-size: 11px;
  line-height: 1.45;
}

.briefing-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}

.case-brief-popup {
  background: transparent;
  border-radius: 12px;
}

.brief-dialog {
  max-height: min(680px, 92vh);
  overflow: hidden;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.18);
}

.brief-topbar {
  height: 64px;
  padding: 0 34px;
  display: grid;
  grid-template-columns: 280px 1fr 180px;
  align-items: center;
  background: linear-gradient(90deg, #08275c 0%, #063b82 54%, #08275c 100%);
  color: #fff;
}

.brief-brand,
.brief-nav,
.brief-return {
  display: inline-flex;
  align-items: center;
}

.brief-brand {
  gap: 12px;
  font-size: 20px;
}

.brief-brand__mark {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(22, 119, 255, 0.22);
  border: 1px solid rgba(191, 219, 254, 0.42);
}

.brief-nav {
  justify-content: center;
  gap: 18px;
  font-size: 15px;
}

.brief-nav span,
.brief-nav strong {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.brief-nav strong {
  padding: 9px 24px;
  border-radius: 999px;
  background: #1677ff;
  box-shadow: 0 8px 18px rgba(22, 119, 255, 0.34);
}

.brief-return {
  justify-self: end;
  gap: 8px;
  height: 36px;
  padding: 0 18px;
  border: none;
  border-radius: 999px;
  color: #eaf2ff;
  background: rgba(255, 255, 255, 0.12);
  font-weight: 700;
  cursor: pointer;
}

.brief-page {
  max-height: min(680px, 92vh);
  overflow: hidden;
  padding: 20px 24px 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.brief-head {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.brief-bottom {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.brief-back-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  align-self: flex-start;
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 14px;
  cursor: pointer;
  padding: 0;
}

.brief-back-link:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.brief-hero {
  margin: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}

.brief-hero__meta {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 0;
  color: #64748b;
  font-weight: 700;
}

.brief-type-pill {
  padding: 6px 14px;
  border-radius: 999px;
  background: #1677ff;
  color: #fff;
}

.brief-hero h1 {
  margin: 0;
  color: #08224c;
  font-size: 26px;
  line-height: 1.2;
  font-weight: 900;
}

.brief-hero p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 14px;
  font-weight: 700;
}

.brief-layout {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}

.brief-layout--single {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.brief-card {
  background: #fff;
  border: 1px solid #e6edf7;
  border-radius: 8px;
  box-shadow: 0 12px 30px rgba(8, 35, 78, 0.06);
  min-height: 0;
}

.brief-card h2,
.brief-info-section h2 {
  margin: 0 0 12px;
  color: #08224c;
  font-size: 17px;
  font-weight: 900;
}

.brief-overview {
  padding: 14px 18px 10px;
  overflow: hidden;
}

.brief-overview__item {
  display: grid;
  grid-template-columns: 32px 1fr;
  gap: 10px;
  align-items: center;
  padding: 6px 0;
}

.brief-overview__icon {
  width: 30px;
  height: 30px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #f1f6ff;
  color: #1d4ed8;
  font-size: 17px;
}

.brief-overview label {
  display: block;
  color: #64748b;
  font-size: 13px;
}

.brief-overview strong {
  display: block;
  margin-top: 2px;
  color: #172554;
  font-size: 14px;
  line-height: 1.35;
}

.brief-main {
  padding: 16px 18px;
  max-height: 100%;
  overflow-y: auto;
}

.brief-info-section + .brief-info-section {
  margin-top: 12px;
}

.brief-info-section h2 {
  position: relative;
  padding-left: 18px;
}

.brief-info-section h2::before {
  content: '';
  position: absolute;
  left: 0;
  top: 3px;
  width: 4px;
  height: 18px;
  border-radius: 999px;
  background: #1677ff;
}

.brief-text-box {
  border: 1px solid #cfe0f7;
  border-radius: 8px;
  padding: 10px 12px;
  background: #f8fbff;
  color: #0f2a52;
  font-size: 14px;
  line-height: 1.55;
  font-weight: 700;
}

.brief-text-box p {
  margin: 0;
}

.brief-text-box p + p {
  margin-top: 4px;
}

.brief-text-box--plain {
  background: #fff;
}

.brief-text-box ol {
  margin: 6px 0 0;
  padding-left: 20px;
}

.brief-side {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  gap: 14px;
  min-height: 0;
}

.brief-roles,
.brief-goals {
  padding: 14px 18px;
  overflow: hidden;
}

.brief-role-list {
  display: grid;
  gap: 8px;
}

.brief-role {
  display: grid;
  grid-template-columns: 44px 1fr;
  gap: 10px;
  align-items: center;
  min-height: 60px;
  padding: 8px 10px;
  border: 1px solid #e5eef8;
  border-radius: 8px;
  background: #fff;
}

.brief-role strong,
.brief-role span,
.brief-role p {
  display: block;
}

.brief-role strong {
  color: #08224c;
  font-size: 14px;
}

.brief-role span {
  width: fit-content;
  margin: 3px 0 4px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #eaf2ff;
  color: #1677ff;
  font-size: 12px;
  font-weight: 800;
}

.brief-role p {
  margin: 0;
  color: #334155;
  font-size: 13px;
  line-height: 1.35;
}

.brief-goals ul {
  display: grid;
  gap: 7px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.brief-goals li {
  display: grid;
  grid-template-columns: 20px 1fr;
  gap: 10px;
  align-items: start;
  color: #0f2a52;
  font-size: 14px;
  font-weight: 700;
}

.brief-goals .van-icon {
  color: #1677ff;
  font-size: 18px;
  margin-top: 2px;
}

.brief-warm-tip {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin: 0;
  padding: 12px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  color: #475569;
  font-size: 14px;
  line-height: 1.55;
}

.brief-warm-tip strong {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #1677ff;
  font-size: 16px;
}

.brief-warm-tip span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.brief-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex: 0 0 auto;
}

.brief-remember {
  width: 136px;
  height: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 1px solid #cfe0f7;
  border-radius: 8px;
  background: #fff;
  color: #1677ff;
  font-weight: 800;
}

.brief-remember input {
  width: 16px;
  height: 16px;
}

.brief-start-btn {
  min-width: 286px;
  height: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: none;
  border-radius: 8px;
  background: #1677ff;
  color: #fff;
  font-size: 16px;
  font-weight: 900;
  box-shadow: 0 12px 24px rgba(22, 119, 255, 0.24);
  cursor: pointer;
}

@media (max-width: 1180px) {
  .brief-topbar,
  .brief-layout {
    grid-template-columns: 1fr;
  }

  .brief-topbar {
    height: auto;
    gap: 14px;
    padding: 18px;
  }

  .brief-nav,
  .brief-return {
    justify-self: start;
  }

  .brief-dialog {
    height: 96vh;
  }
}

@media (max-width: 720px) {
  .brief-page {
    padding: 16px 14px 14px;
  }

  .brief-hero h1 {
    font-size: 22px;
  }

  .brief-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .brief-remember,
  .brief-start-btn {
    width: 100%;
    min-width: 0;
  }
}

.chat-area {
  position: relative;
  flex: 1;
  min-width: 0;
  background: #f0f4f8;
}

.training-face-guard {
  margin: 14px 18px 10px;
  flex-shrink: 0;
}

.training-face-guard.face-guard--monitor {
  position: absolute;
  top: 14px;
  right: 18px;
  z-index: 5;
  width: 260px;
  height: 112px;
  margin: 0;
  overflow: hidden;
}

.scene-session-bar {
  padding: 6px 18px;
  background: #f8fafc;
  border-bottom-color: #e2e8f0;
}

.chat-messages {
  padding: 16px 20px;
}

.msg-row {
  gap: 10px;
  align-items: flex-start;
}

.avatar {
  width: 40px;
  height: 40px;
  box-sizing: border-box;
}

.avatar-ai {
  border: none;
  overflow: hidden;
}

.avatar-img {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
  display: block;
}

.avatar-human {
  background: #1e3a6e;
  border: 2px solid #2563eb;
}

.msg-body {
  max-width: min(680px, 62%);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.msg-ai .msg-body {
  align-items: flex-start;
}

.msg-human .msg-body {
  align-items: flex-end;
}

.msg-sender {
  font-size: 13px;
}

.msg-bubble {
  padding: 12px 17px;
  border-radius: 12px;
  font-size: 17px;
  line-height: 1.7;
}

.bubble-ai {
  background: #fff;
  color: #1e293b;
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.bubble-human {
  background: #2563eb;
  color: #fff;
  border-radius: 12px;
}

.chat-input-area {
  padding: 7px 16px 8px;
  background: #fff;
  border-top-color: #e2e8f0;
}

.coach-feedback {
  border-radius: 6px;
  margin-bottom: 5px;
  padding: 6px 10px;
  font-size: 11px;
}

.coach-feedback--info {
  background: #eff6ff;
}

.coach-feedback--good {
  background: #f0fdf4;
}

.coach-feedback--warning {
  background: #fff7ed;
}

.stage-missing__tag,
.suggested-question-chip {
  border-color: var(--police-border);
}

.stage-missing {
  margin-bottom: 5px;
  gap: 5px;
}

.suggested-questions {
  gap: 5px;
  margin-bottom: 6px;
}

.suggested-questions__head {
  line-height: 1.2;
}

.suggested-question-chip {
  padding: 5px 9px;
  font-size: 11px;
}

.suggested-question-chip:hover:not(:disabled) {
  border-color: var(--police-primary);
  background: var(--police-primary-light);
}

.training-status-panel {
  min-height: calc(100vh - 52px);
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 24px;
  background: #f0f4f8;
  text-align: center;
  color: #64748b;
}

.training-status-panel--error {
  background: #f0f4f8;
}

.training-status-panel h2 {
  margin: 4px 0 0;
  font-size: 18px;
  color: #0f172a;
}

.training-status-panel p {
  max-width: 440px;
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
}

.training-status-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-top: 8px;
  flex-wrap: wrap;
}

@media (max-width: 960px) {
  .training-page {
    flex-direction: column;
    height: 100vh;
  }

  .training-body {
    flex-direction: column;
    overflow: hidden;
  }

  .info-panel {
    flex: none;
    width: 100%;
    max-height: none;
    border-right: none;
    border-bottom: 1px solid #e5e6eb;
  }

  .panel-scroll {
    max-height: none;
  }

  .msg-body {
    max-width: 84%;
  }
}
</style>
