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

      <div class="panel-section briefing-section">
        <h3 class="panel-title">
          <van-icon name="notes-o" />
          接警与现场
        </h3>
        <div class="briefing-card briefing-card--dispatch">
          <span class="briefing-label">110 简报</span>
          <p>{{ compactDispatchBrief }}</p>
        </div>
        <div v-if="!isIntakeScene" class="briefing-grid">
          <div class="briefing-mini">
            <span>第一印象</span>
            <p>{{ compactFirstImpression }}</p>
          </div>
          <div class="briefing-mini">
            <span>案件背景</span>
            <p>{{ compactCaseBackground }}</p>
          </div>
        </div>
        <van-button block plain type="primary" size="mini" class="brief-btn" @click="showCaseBrief = true">
          查看完整接警简报
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
          <div v-if="stageMissing.length" class="left-gap-row">
            <span v-for="item in stageMissing.slice(0, 3)" :key="item" class="left-gap-chip">{{ item }}</span>
          </div>
          <div v-if="leftSuggestedQuestions.length" class="left-suggestion-list">
            <button
              v-for="item in leftSuggestedQuestions"
              :key="item.text"
              type="button"
              class="left-suggestion"
              :disabled="isLoading"
              @click="applySuggestedQuestion(item)"
            >
              <span>{{ item.category || '追问' }}</span>
              {{ item.text }}
            </button>
          </div>
        </div>
      </div>

      <div class="panel-section progress-section">
        <h3 class="panel-title">
          <van-icon name="chart-trending-o" />
          询问进度
          <span class="progress-percent">{{ assessmentProgressPercent }}%</span>
        </h3>
        <div class="inquiry-progress">
          <div class="inquiry-progress__head">
            <span>必考点完成</span>
            <strong>{{ progressSummary.earnedWeight }} / {{ progressSummary.totalWeight }}</strong>
          </div>
          <div class="inquiry-progress__track">
            <div class="inquiry-progress__fill" :style="{ width: `${assessmentProgressPercent}%` }"></div>
          </div>
          <div class="inquiry-progress__meta">
            <span>已完成 {{ progressSummary.completedCount }}</span>
            <span>待补齐 {{ progressSummary.missingCount }}</span>
          </div>
          <div v-if="progressMissingLabels.length" class="progress-missing-list">
            <span v-for="item in progressMissingLabels" :key="item" class="progress-missing-chip">{{ item }}</span>
          </div>
          <p v-else class="progress-ready-text">本阶段关键询问已基本覆盖，可视情况继续追问或结束训练。</p>
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
            v-for="role in visibleSceneRoles"
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
              :size="26"
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
        <button
          v-if="hiddenSceneRoleCount > 0"
          type="button"
          class="scene-role-toggle"
          @click="showAllRoles = !showAllRoles"
        >
          {{ showAllRoles ? '收起角色' : `展开其余 ${hiddenSceneRoleCount} 个角色` }}
        </button>
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
    </div>
    </template>

    <van-popup
      v-model:show="showCaseBrief"
      position="center"
      class="case-brief-popup"
      :style="{ width: 'min(1440px, 98vw)', maxWidth: '98vw' }"
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
              <div class="brief-hero__meta">
                <span class="brief-type-pill">{{ caseInfo.caseType || '训练案件' }}</span>
                <span>案件编号：#{{ route.params.id || '—' }}</span>
              </div>
              <div>
                <h1>{{ caseInfo.title }}</h1>
                <p>{{ caseInfo.sceneName || '接警简报与现场信息' }}</p>
              </div>
            </section>
          </div>

          <div class="brief-layout">
            <aside class="brief-card brief-overview">
              <h2>案件概览</h2>
              <div v-for="item in briefOverviewItems" :key="item.label" class="brief-overview__item">
                <span class="brief-overview__icon"><van-icon :name="item.icon" /></span>
                <div>
                  <label>{{ item.label }}</label>
                  <strong>{{ item.value }}</strong>
                </div>
              </div>
            </aside>

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
                  <strong>当前阶段建议</strong>
                  <ol>
                    <li v-for="tip in (isIntakeScene ? intakeBriefTips : defaultBriefTips)" :key="tip">{{ tip }}</li>
                  </ol>
                </div>
              </section>
            </main>

            <aside class="brief-side">
              <section class="brief-card brief-roles">
                <h2>涉及角色</h2>
                <div class="brief-role-list">
                  <div v-for="role in briefRoleItems" :key="role.id || role.name" class="brief-role">
                    <RoleSpeakingAvatar :name="role.name" :primary="role.is_primary" :risk="(role.risk ?? 0) >= 70" :size="40" />
                    <div>
                      <strong>{{ role.name }}</strong>
                      <span>{{ role.role_type || '相关人员' }}</span>
                      <p>情绪值：{{ role.emotion ?? '--' }}</p>
                      <p>关系：{{ role.state_label || '现场相关人员' }}</p>
                    </div>
                  </div>
                </div>
              </section>

              <section class="brief-card brief-goals">
                <h2>训练目标</h2>
                <ul>
                  <li v-for="goal in briefTrainingGoals" :key="goal">
                    <van-icon name="checked" />
                    <span>{{ goal }}</span>
                  </li>
                </ul>
              </section>
            </aside>
          </div>

          <div class="brief-bottom">
            <section class="brief-warm-tip">
              <strong><van-icon name="info-o" />温馨提示</strong>
              <span>{{ isIntakeScene ? '请确认已进入110接警状态，随后报警人将先开口说明情况；你再按规范顺序展开问询。' : '请仔细阅读以上案件简报和现场信息，确认后进入对话训练环节。训练过程中将根据你的提问与选择推进剧情发展。' }}</span>
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
const isSessionBooting = ref(true)
const trainingLoadError = ref('')
const isPlayingReplies = ref(false)
const speakingRoleName = ref('')
const showCaseBrief = ref(false)
const suppressedBriefThisSession = ref(false)
const isReturningToHall = ref(false)

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
  state_label?: string
  affect_label?: string
  is_active?: boolean
  is_targeted?: boolean
}
const sceneRoles = ref<SceneRoleBrief[]>([])
const showAllRoles = ref(false)
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
const assessmentProgress = ref<any>(null)
const completedPointIds = ref<string[]>([])
const completedActionIds = ref<string[]>([])
const autoFinishReady = ref(false)

const revealedInfo = ref<string[]>([])
const currentState = ref({ emotion: 50, trust: 30, risk: 50, clarity: 50 })
const chatHistory = ref<
  Array<{ id: number; role: string; content: string; speakerName?: string; inputSource?: 'voice' | 'text' }>
>([])

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



const META_QUESTION_PATTERN = /先围绕|把最关键|这一点|训练已恢复|补齐这些关键项/

const compactText = (value: string, maxLength = 72, fallback = '暂无信息') => {
  const text = String(value || '').replace(/\s+/g, ' ').trim()
  if (!text) return fallback
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text
}

const compactDispatchBrief = computed(() => {
  if (isIntakeScene.value) {
    return compactText(caseInfo.dispatchBrief, 92, '110 有新报警来电，等待接听。')
  }
  return compactText(caseInfo.dispatchBrief, 92, '指挥中心暂未下发更详细的接警简报。')
})
const compactFirstImpression = computed(() => {
  if (isIntakeScene.value) return '接警阶段尚未到场，暂无现场观察信息。'
  return compactText(caseInfo.firstImpression, 54, '到场后先观察人员、环境和风险。')
})
const compactCaseBackground = computed(() =>
  compactText(caseInfo.caseBackground || caseInfo.caseOriginalContent, 64, '案件背景待在对话中进一步核实。')
)
const structuredTimeline = computed(() => {
  const data = caseInfo.structuredData || {}
  return Array.isArray(data.timeline) ? data.timeline.map((item: any) => String(item)).filter(Boolean) : []
})
const structuredEvidence = computed(() => {
  const data = caseInfo.structuredData || {}
  return Array.isArray(data.evidence_points) ? data.evidence_points.map((item: any) => String(item)).filter(Boolean) : []
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
const briefRoleItems = computed(() => orderedSceneRoles.value.slice(0, 3))
const briefTrainingGoals = computed(() => {
  const goals = [
    caseInfo.currentStageGoal,
    ...stageMissing.value.slice(0, 3),
    ...structuredEvidence.value.slice(0, 2).map((item: string) => `固定${item}`),
  ]
    .map((item) => String(item || '').trim())
    .filter(Boolean)
  const fallback = ['控制现场，防止事态扩大', '了解事件经过，固定证据', '依法调查取证，明确责任', '妥善处置，恢复现场秩序']
  return Array.from(new Set(goals.length ? goals : fallback)).slice(0, 4)
})
const briefOverviewItems = computed(() => {
  if (isIntakeScene.value) {
    return [
      { label: '接警电话', value: '110', icon: 'phone-o' },
      { label: '当前状态', value: '等待接听', icon: 'phone-circle-o' },
      { label: '当前场景', value: caseInfo.sceneName || '接警研判', icon: 'manager-o' },
      { label: '训练难度', value: normalizeDifficulty(caseInfo.difficulty), icon: 'bar-chart-o' },
      { label: '对话模式', value: '报警人先开口', icon: 'chat-o' },
      { label: '推荐角色', value: briefRoleItems.value.map((role) => role.name).join('、') || roleInfo.name, icon: 'friends-o' },
    ]
  }
  return [
    { label: '接警电话', value: '110', icon: 'phone-o' },
    { label: '接警时间', value: briefCaseTime.value, icon: 'clock-o' },
    { label: '接警地点', value: briefCaseLocation.value, icon: 'location-o' },
    { label: '案件类型', value: caseInfo.caseType || '未分类', icon: 'description' },
    { label: '当前场景', value: caseInfo.sceneName || '训练场景', icon: 'manager-o' },
    { label: '训练难度', value: normalizeDifficulty(caseInfo.difficulty), icon: 'bar-chart-o' },
    { label: '预计时长', value: '20 分钟', icon: 'underway-o' },
    { label: '推荐角色', value: briefRoleItems.value.map((role) => role.name).join('、') || roleInfo.name, icon: 'friends-o' },
  ]
})
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
const leftSuggestedQuestions = computed(() => suggestedQuestionItems.value.slice(0, 2))
const progressSummary = computed(() => {
  const progress = assessmentProgress.value || {}
  const summary = progress.summary || {}
  const points = Array.isArray(progress.points) ? progress.points : []
  const totalWeight = Number(summary.total_weight ?? summary.totalWeight ?? 0)
  const earnedWeight = Number(summary.earned_weight ?? summary.earnedWeight ?? 0)
  const completedFromSummary = Array.isArray(summary.completed_point_ids) ? summary.completed_point_ids.length : 0
  const completedCount = completedFromSummary || points.filter((item: any) => item?.status === 'hit').length
  const missingFromSummary = Array.isArray(summary.missing) ? summary.missing.length : 0
  const missingCount = missingFromSummary || points.filter((item: any) => item?.status !== 'hit' && item?.required !== false).length
  return {
    totalWeight,
    earnedWeight,
    completedCount,
    missingCount,
  }
})
const assessmentProgressPercent = computed(() => {
  const total = progressSummary.value.totalWeight
  const earned = progressSummary.value.earnedWeight
  if (total > 0) return Math.max(0, Math.min(100, Math.round((earned / total) * 100)))
  const requirements = Array.isArray(assessmentProgress.value?.summary?.requirements)
    ? assessmentProgress.value.summary.requirements.length
    : stageMissing.value.length + (Array.isArray(assessmentProgress.value?.summary?.satisfied) ? assessmentProgress.value.summary.satisfied.length : 0)
  const satisfied = Array.isArray(assessmentProgress.value?.summary?.satisfied)
    ? assessmentProgress.value.summary.satisfied.length
    : 0
  if (requirements > 0) return Math.max(0, Math.min(100, Math.round((satisfied / requirements) * 100)))
  return stageMissing.value.length ? 0 : 100
})
const progressMissingLabels = computed(() => {
  const summaryMissing = assessmentProgress.value?.summary?.missing
  const progress = assessmentProgress.value || {}
  const points = Array.isArray(progress.points) ? progress.points : []
  const labels = Array.isArray(summaryMissing) && summaryMissing.length
    ? summaryMissing
    : points
      .filter((item: any) => item?.status !== 'hit' && item?.required !== false)
      .map((item: any) => item?.label)
  return labels
    .map((item: any) => String(item || '').trim())
    .filter(Boolean)
    .slice(0, 4)
})

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
  assessmentProgress.value = res?.assessment_progress || null
  completedPointIds.value = Array.isArray(res?.completed_point_ids) ? res.completed_point_ids : []
  completedActionIds.value = Array.isArray(res?.completed_action_ids) ? res.completed_action_ids : []
  autoFinishReady.value = Boolean(res?.auto_finish_ready)
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
  background: #f0f4f8;
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
  background: #f0f4f8;
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

.progress-section {
  border-left: 3px solid var(--police-primary, #003087);
}

.progress-percent {
  margin-left: auto;
  min-width: 42px;
  text-align: right;
  font-size: 13px;
  font-weight: 800;
  color: var(--police-primary, #003087);
}

.inquiry-progress {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.inquiry-progress__head,
.inquiry-progress__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  color: #475569;
}

.inquiry-progress__head strong {
  font-size: 13px;
  color: #0f172a;
}

.inquiry-progress__track {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: #e2e8f0;
}

.inquiry-progress__fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #003087, #0ea5e9);
  transition: width 0.2s ease;
}

.progress-missing-list {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.progress-missing-chip {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  border-radius: 999px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 700;
  color: #1d4ed8;
}

.progress-ready-text {
  margin: 0;
  border-radius: 6px;
  background: #ecfdf5;
  padding: 6px 8px;
  font-size: 12px;
  line-height: 1.5;
  color: #047857;
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

.training-page {
  flex-direction: column;
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
  font-size: 15px;
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
  border-right-color: #e2e8f0;
  overflow-y: auto;
  scrollbar-width: thin;
}

.info-panel > .panel-section:first-child {
  display: none;
}

.panel-section {
  position: relative;
  padding: 9px 12px;
  border-bottom-color: #e2e8f0;
}

.panel-section::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 2px;
  border-radius: 0 2px 2px 0;
  background: var(--police-primary);
  opacity: 0;
  transition: opacity 0.2s ease;
}

.panel-section:hover::before {
  opacity: 1;
}

.panel-title {
  gap: 6px;
  margin-bottom: 6px;
  font-size: 11px;
  line-height: 1.2;
  color: #64748b;
}

.info-item {
  margin-bottom: 5px;
  font-size: 11px;
  line-height: 1.35;
}

.info-label {
  color: var(--police-text-muted);
}

.info-value {
  color: #1e293b;
  font-weight: 600;
}

.brief-btn {
  height: 26px;
  border-radius: 6px;
  margin-top: 6px;
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
  border-radius: 0;
}

.brief-dialog {
  height: min(760px, 94vh);
  overflow: hidden;
  background: #f4f8ff;
  border-radius: 0;
  border: 1px solid rgba(14, 38, 79, 0.08);
  box-shadow: 0 28px 80px rgba(8, 25, 55, 0.28);
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
  height: 100%;
  overflow: hidden;
  padding: 14px 26px 14px;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: 12px;
}

.brief-head {
  display: grid;
  grid-template-columns: 210px 1fr;
  gap: 18px;
  align-items: end;
}

.brief-bottom {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: center;
}

.brief-back-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: none;
  background: transparent;
  color: #334155;
  font-size: 15px;
  cursor: pointer;
  margin-bottom: 10px;
}

.brief-back-link:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.brief-hero {
  max-width: none;
  margin: 0;
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: end;
  gap: 12px 28px;
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
  display: grid;
  grid-template-columns: 300px minmax(420px, 1fr) 340px;
  gap: 14px;
  align-items: stretch;
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
  padding: 14px 18px 12px;
  overflow: hidden;
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
  align-items: center;
  gap: 12px;
  max-width: none;
  margin: 0;
  padding: 10px 14px;
  border: 1px solid #cfe0f7;
  border-radius: 8px;
  background: #f8fbff;
  color: #475569;
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
  justify-content: center;
  align-items: center;
  gap: 18px;
  padding-bottom: 0;
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
    padding: 24px 14px;
  }

  .brief-hero {
    margin-bottom: 24px;
  }

  .brief-hero h1 {
    font-size: 28px;
  }

  .brief-actions {
    flex-direction: column;
  }

  .brief-head,
  .brief-bottom {
    grid-template-columns: 1fr;
  }

  .brief-remember,
  .brief-start-btn {
    width: 100%;
    min-width: 0;
  }
}

.stage-card {
  border: 1px solid var(--police-border-light);
  border-radius: 7px;
  background: #f8fafc;
  padding: 8px 10px;
}

.stage-tag {
  padding: 2px 8px;
  background: #eff6ff;
  color: #2563eb;
}

.stage-name-text {
  margin-top: 5px;
  font-size: 12px;
  color: #1e293b;
}

.goal-label {
  margin-top: 6px;
  font-size: 10px;
  color: var(--police-text-muted);
}

.goal-text {
  font-size: 11px;
  line-height: 1.45;
  color: #64748b;
}

.left-gap-row {
  display: none;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 7px;
}

.left-gap-chip {
  padding: 2px 7px;
  border-radius: 999px;
  background: #fff7ed;
  color: #c2410c;
  font-size: 10px;
  font-weight: 700;
}

.left-suggestion-list {
  display: none;
  gap: 4px;
  margin-top: 7px;
}

.left-suggestion {
  width: 100%;
  border: 1px solid #dbeafe;
  border-radius: 6px;
  background: #fff;
  color: #334155;
  padding: 5px 7px;
  font-size: 11px;
  line-height: 1.35;
  text-align: left;
  cursor: pointer;
}

.left-suggestion span {
  display: inline-block;
  margin-right: 5px;
  color: #2563eb;
  font-size: 10px;
  font-weight: 700;
}

.left-suggestion:hover:not(:disabled) {
  border-color: #2563eb;
  background: #eff6ff;
}

.scene-role-hint {
  display: none;
}

.scene-role-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.scene-role-card {
  max-width: none;
  min-width: 0;
  width: 100%;
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) auto;
  align-items: center;
  gap: 5px;
  border-color: var(--police-border);
  border-radius: 6px;
  padding: 5px 7px;
  text-align: left;
}

.scene-role-card:hover:not(:disabled) {
  background: var(--police-primary-light);
  border-color: #93c5fd;
  box-shadow: var(--police-shadow-sm);
  transform: translateX(2px);
}

.scene-role-card--selected {
  border-color: #93c5fd;
  background: #eff6ff;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
}

.scene-role-card__name,
.scene-role-card__meta {
  grid-column: 2;
}

.scene-role-card__badge {
  grid-column: 3;
  grid-row: 1 / span 2;
  align-self: center;
  white-space: nowrap;
}

.scene-role-toggle {
  width: 100%;
  margin-top: 5px;
  border: 1px dashed #bfdbfe;
  border-radius: 6px;
  background: #f8fbff;
  color: #2563eb;
  padding: 5px 8px;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}

.scene-role-toggle:hover {
  background: #eff6ff;
}

.state-bar + .state-bar {
  margin-top: 7px;
}

.state-header {
  margin-bottom: 3px;
  font-size: 11px;
}

.progress-track {
  height: 4px;
  border-radius: 3px;
  background: #e2e8f0;
}

.fact-list {
  gap: 3px;
  max-height: 88px;
  overflow: auto;
}

.fact-empty {
  font-size: 11px;
  color: var(--police-text-muted);
}

.fact-item {
  gap: 5px;
  font-size: 11px;
  line-height: 1.35;
  color: #475569;
}

.panel-actions {
  padding: 7px 12px;
  border-top: 1px solid var(--police-border);
}

.finish-btn {
  height: 30px;
  border-radius: 8px;
  background: #0f1e3c !important;
  border-color: #0f1e3c !important;
}

.chat-area {
  flex: 1 1 66.667%;
  width: 66.667%;
  min-width: 0;
  background: #f0f4f8;
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
  gap: 8px;
  align-items: flex-end;
}

.avatar {
  width: 32px;
  height: 32px;
}

.avatar-ai {
  background: #e2e8f0;
  color: #64748b;
}

.avatar-human {
  background: #1e3a6e;
  border: 2px solid #2563eb;
}

.msg-body {
  max-width: min(680px, 62%);
}

.msg-bubble {
  padding: 9px 13px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.65;
  transition: box-shadow 0.2s ease, transform 0.2s ease;
}

.msg-bubble:hover {
  transform: translateY(-1px);
}

.bubble-ai {
  border: 1px solid var(--police-border-light);
  border-radius: 4px 12px 12px 12px;
  color: #1e293b;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}

.bubble-human {
  border-radius: 12px 4px 12px 12px;
  background: #2563eb;
}

.bubble-human:hover {
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
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
    height: auto;
  }

  .training-body {
    flex-direction: column;
    overflow: visible;
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
