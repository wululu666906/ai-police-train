<template>
  <div class="dialogue-record-page" :class="{ 'dialogue-record-page--admin': isAdminView }">
    <header class="record-topbar">
      <button type="button" class="back-button" @click="goBack">
        <van-icon name="arrow-left" />
        {{ isAdminView ? '返回普通训练' : '返回训练历史' }}
      </button>

      <div class="record-heading">
        <span class="record-kicker">聊天记录</span>
        <h1>{{ sessionMeta.caseTitle }}</h1>
        <p>{{ sessionMeta.sceneName }} · {{ statusLabel }} · 共 {{ dialogueMessages.length }} 条对话</p>
      </div>

      <div class="record-actions">
        <button
          v-if="sessionDetail?.status === 'finished'"
          type="button"
          class="action-button action-button--primary"
          @click="openReport"
        >
          查看报告
        </button>
        <button
          v-else-if="sessionDetail?.status === 'active' && !isAdminView"
          type="button"
          class="action-button action-button--primary"
          @click="router.push(`/student/training/${sessionId}`)"
        >
          继续训练
        </button>
      </div>
    </header>

    <main ref="scrollContainer" class="record-scroll">
      <div v-if="loading" class="state-panel">
        <van-loading color="#2563eb" vertical>正在加载对话记录...</van-loading>
      </div>

      <div v-else-if="loadError" class="state-panel">
        <van-icon name="warning-o" size="44" color="#f59e0b" />
        <h2>对话记录加载失败</h2>
        <p>{{ loadError }}</p>
        <button type="button" class="action-button action-button--primary" @click="fetchSessionDetail">
          重新加载
        </button>
      </div>

      <section v-else class="forward-record">
        <div class="forward-record__cover">
          <span class="forward-record__label">合并转发</span>
          <h2>{{ sessionMeta.caseTitle }}的聊天记录</h2>
          <p>{{ sessionMeta.sceneName || '训练场景' }}</p>
        </div>

        <div v-if="dialogueMessages.length === 0" class="empty-dialogue">
          <van-icon name="chat-o" size="42" color="#cbd5e1" />
          <strong>暂无对话记录</strong>
          <span>这条训练会话还没有产生有效问答内容。</span>
        </div>

        <div v-else class="message-list">
          <template v-for="(message, index) in dialogueMessages" :key="message.key">
            <div v-if="shouldShowDateDivider(index)" class="date-divider">
              <span>{{ formatDateDivider(message.createdAt) }}</span>
            </div>

            <div v-if="message.role === 'system'" class="system-message">
              <span>{{ message.content }}</span>
            </div>

            <article
              v-else
              class="message-row"
              :class="message.role === 'human' ? 'message-row--human' : 'message-row--assistant'"
            >
              <div v-if="message.role === 'assistant'" class="avatar" :style="{ background: getAvatarColor(message) }">
                <img
                  v-if="shouldShowMessageAvatar(message)"
                  :src="resolveAvatarUrl(message.avatarUrl)"
                  :alt="message.speakerName"
                  @error="markAvatarFailed(message.avatarUrl)"
                />
                <span v-else>{{ getInitial(message.speakerName) }}</span>
              </div>

              <div class="message-body">
                <div class="speaker-line">
                  <span>{{ message.speakerName }}</span>
                  <time v-if="message.createdAt">{{ formatMessageTime(message.createdAt) }}</time>
                </div>
                <div class="message-bubble">{{ message.content }}</div>
              </div>

              <div v-if="message.role === 'human'" class="avatar avatar--human">
                <van-icon name="friends-o" />
              </div>
            </article>
          </template>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import request from '../utils/request'
import { resolveMediaUrl } from '../utils/media'
import { isInternalPromptMessage } from '../utils/dialogueMessage'

type DialogueRole = 'assistant' | 'human' | 'system'

interface SceneRoleBrief {
  id: number
  name: string
  avatar_id?: number | null
  avatar_url?: string | null
}

interface DialogueMessage {
  key: string
  id: number
  role: DialogueRole
  content: string
  speakerName: string
  avatarUrl?: string | null
  avatarId?: number | null
  createdAt?: string
}

const AVATAR_PALETTE = [
  '#4F46E5', '#0891B2', '#059669', '#D97706', '#DC2626',
  '#7C3AED', '#0E7490', '#047857', '#B45309', '#BE123C',
  '#6366F1', '#0284C7', '#16A34A', '#D97706', '#E11D48',
  '#8B5CF6', '#0EA5E9', '#22C55E', '#F59E0B', '#EF4444',
]

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const loadError = ref('')
const sessionDetail = ref<any>(null)
const scrollContainer = ref<HTMLElement | null>(null)
const failedAvatarUrls = ref<Set<string>>(new Set())

const isAdminView = computed(() => route.path.includes('/admin/text-sessions'))

const sessionId = computed(() => {
  const raw = route.params.sessionId ?? route.params.id
  const value = Number(Array.isArray(raw) ? raw[0] : raw)
  return Number.isFinite(value) && value > 0 ? value : null
})

const sceneRoles = computed<SceneRoleBrief[]>(() =>
  Array.isArray(sessionDetail.value?.scene_roles) ? sessionDetail.value.scene_roles : [],
)

const sessionMeta = computed(() => ({
  caseTitle: sessionDetail.value?.case_title || '未命名案件',
  sceneName: sessionDetail.value?.scene_name || '训练场景',
}))

const statusLabel = computed(() => {
  if (sessionDetail.value?.status === 'finished') return '已完成'
  if (sessionDetail.value?.status === 'active') return '进行中'
  return '训练记录'
})

const dialogueMessages = computed<DialogueMessage[]>(() => {
  const messages = (Array.isArray(sessionDetail.value?.messages) ? sessionDetail.value.messages : []).filter((message: any) => !isInternalPromptMessage(message))
  return messages
    .map((message: any, index: number) => {
      const role = normalizeRole(message?.role)
      const content = String(message?.content || '').trim()
      if (!content) return null

      const speaker = role === 'assistant'
        ? resolveAssistantSpeaker(message)
        : null

      return {
        key: `${message?.id || index}-${role}`,
        id: Number(message?.id || index),
        role,
        content,
        speakerName: role === 'human' ? '执法民警' : role === 'system' ? '系统提示' : speaker?.name || sessionDetail.value?.role_name || '对话对象',
        avatarUrl: speaker?.avatar_url,
        avatarId: speaker?.avatar_id,
        createdAt: message?.created_at,
      }
    })
    .filter(Boolean) as DialogueMessage[]
})

const normalizeRole = (value: unknown): DialogueRole => {
  if (value === 'user' || value === 'human') return 'human'
  if (value === 'system') return 'system'
  return 'assistant'
}

const resolveAssistantSpeaker = (message: any) => {
  const speakerName = String(message?.speaker_name || '').trim()
  if (speakerName) {
    const matched = sceneRoles.value.find((role) => role.name === speakerName)
    if (matched) return matched
    return { name: speakerName, avatar_id: null, avatar_url: null }
  }
  const primary = sceneRoles.value.find((role: any) => role.is_primary)
  return primary || sceneRoles.value[0] || null
}

const fetchSessionDetail = async () => {
  if (!sessionId.value) {
    loadError.value = '训练记录编号无效，请从训练历史重新进入。'
    loading.value = false
    return
  }

  loading.value = true
  loadError.value = ''
  try {
    const res: any = await request.get(`/training/session/${sessionId.value}`, { _skipErrorToast: true } as any)
    sessionDetail.value = res || null
    await nextTick()
    scrollContainer.value?.scrollTo({ top: 0 })
  } catch (error: any) {
    loadError.value = error?.response?.status === 404
      ? '该训练记录不存在，或不属于当前登录账号。'
      : error?.response?.data?.detail || '获取对话记录失败'
    showToast(loadError.value)
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  router.push(isAdminView.value ? '/admin/text-sessions' : '/student/history')
}

const openReport = () => {
  if (!sessionId.value) return
  if (isAdminView.value) {
    router.push(`/admin/text-sessions/${sessionId.value}/report`)
    return
  }
  router.push(`/student/evaluation?session_id=${sessionId.value}`)
}

const getInitial = (name: string) => {
  const text = String(name || '').trim()
  return text ? text.slice(0, 1) : '?'
}

const resolveAvatarUrl = (value: unknown) => resolveMediaUrl(value)

const shouldShowMessageAvatar = (message: { avatarUrl?: string | null }) => {
  const url = resolveAvatarUrl(message.avatarUrl)
  return Boolean(url && !failedAvatarUrls.value.has(url))
}

const markAvatarFailed = (value: unknown) => {
  const url = resolveAvatarUrl(value)
  if (!url) return
  failedAvatarUrls.value = new Set([...failedAvatarUrls.value, url])
}

const getAvatarColor = (message: DialogueMessage) => {
  const avatarId = Number(message.avatarId)
  if (Number.isInteger(avatarId) && avatarId >= 1 && avatarId <= AVATAR_PALETTE.length) {
    return AVATAR_PALETTE[avatarId - 1]
  }
  const seed = message.speakerName.split('').reduce((sum, char) => sum + char.charCodeAt(0), 0)
  return AVATAR_PALETTE[seed % AVATAR_PALETTE.length]
}

const parseDate = (value?: string) => {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

const pad = (value: number) => String(value).padStart(2, '0')

const formatDateKey = (value?: string) => {
  const date = parseDate(value)
  if (!date) return ''
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

const shouldShowDateDivider = (index: number) => {
  const current = dialogueMessages.value[index]
  if (!current?.createdAt) return index === 0
  const previous = dialogueMessages.value[index - 1]
  return index === 0 || formatDateKey(current.createdAt) !== formatDateKey(previous?.createdAt)
}

const formatDateDivider = (value?: string) => {
  const date = parseDate(value)
  if (!date) return '对话记录'
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`
}

const formatMessageTime = (value?: string) => {
  const date = parseDate(value)
  if (!date) return ''
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

onMounted(fetchSessionDetail)
</script>

<style scoped>
.dialogue-record-page {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #f1f5f9;
  color: #0f172a;
}

.dialogue-record-page--admin {
  width: 100%;
  height: 100%;
  min-height: calc(100vh - 140px);
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.record-topbar {
  min-height: 76px;
  flex-shrink: 0;
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr) 180px;
  align-items: center;
  gap: 18px;
  padding: 12px 24px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  box-shadow: 0 1px 8px rgba(15, 23, 42, 0.04);
}

.back-button,
.action-button {
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #fff;
  color: #334155;
  cursor: pointer;
  font-size: 14px;
  font-weight: 700;
}

.back-button {
  justify-self: start;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 38px;
  padding: 0 14px;
}

.back-button:hover,
.action-button:hover {
  border-color: #2563eb;
  color: #2563eb;
}

.record-heading {
  min-width: 0;
  text-align: center;
}

.record-kicker {
  display: block;
  margin-bottom: 2px;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.record-heading h1 {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
  line-height: 1.35;
  font-weight: 900;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-heading p {
  margin: 3px 0 0;
  color: #64748b;
  font-size: 13px;
}

.record-actions {
  display: flex;
  justify-content: flex-end;
}

.action-button {
  min-width: 96px;
  height: 36px;
  padding: 0 14px;
}

.action-button--primary {
  border-color: #2563eb;
  background: #2563eb;
  color: #fff;
}

.action-button--primary:hover {
  border-color: #1d4ed8;
  background: #1d4ed8;
  color: #fff;
}

.record-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 22px;
}

.state-panel {
  min-height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  text-align: center;
  color: #64748b;
}

.state-panel h2 {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
}

.state-panel p {
  margin: 0;
  max-width: 420px;
  font-size: 14px;
  line-height: 1.7;
}

.forward-record {
  max-width: 860px;
  min-height: calc(100vh - 120px);
  margin: 0 auto;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 14px 40px rgba(15, 23, 42, 0.08);
}

.forward-record__cover {
  padding: 24px 28px 20px;
  border-bottom: 1px solid #eef2f7;
  background: #fff;
  text-align: center;
}

.forward-record__label {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
}

.forward-record__cover h2 {
  margin: 12px 0 5px;
  color: #111827;
  font-size: 22px;
  line-height: 1.35;
  font-weight: 900;
}

.forward-record__cover p {
  margin: 0;
  color: #64748b;
  font-size: 14px;
}

.empty-dialogue {
  min-height: 360px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #94a3b8;
}

.empty-dialogue strong {
  color: #475569;
  font-size: 16px;
}

.empty-dialogue span {
  font-size: 14px;
}

.message-list {
  padding: 20px 30px 32px;
  background: #fff;
}

.date-divider,
.system-message {
  display: flex;
  justify-content: center;
}

.date-divider {
  margin: 8px 0 20px;
}

.date-divider span,
.system-message span {
  max-width: 78%;
  border-radius: 999px;
  background: #f1f5f9;
  color: #64748b;
  font-size: 12px;
  line-height: 1.45;
}

.date-divider span {
  padding: 5px 12px;
}

.system-message {
  margin: 14px 0;
}

.system-message span {
  padding: 7px 12px;
}

.message-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 18px;
}

.message-row--human {
  justify-content: flex-end;
}

.avatar {
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 50%;
  color: #fff;
  font-size: 17px;
  font-weight: 800;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.14);
}

.avatar img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.avatar--human {
  background: #123b76;
  font-size: 20px;
}

.message-body {
  max-width: min(620px, 72%);
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.message-row--human .message-body {
  align-items: flex-end;
}

.speaker-line {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.2;
}

.message-row--human .speaker-line {
  flex-direction: row-reverse;
}

.speaker-line span {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 700;
}

.speaker-line time {
  color: #94a3b8;
  font-size: 12px;
}

.message-bubble {
  position: relative;
  min-height: 42px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 16px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  box-sizing: border-box;
}

.message-row--assistant .message-bubble {
  background: #f8fafc;
  color: #0f172a;
  border: 1px solid #e2e8f0;
}

.message-row--human .message-bubble {
  background: #d9f7be;
  color: #102a18;
  border: 1px solid #b7eb8f;
}

@media (max-width: 720px) {
  .record-topbar {
    grid-template-columns: 1fr;
    gap: 10px;
    padding: 12px 14px;
  }

  .record-heading {
    text-align: left;
  }

  .record-actions,
  .back-button {
    justify-self: stretch;
  }

  .back-button,
  .action-button {
    width: 100%;
    justify-content: center;
  }

  .record-scroll {
    padding: 12px;
  }

  .forward-record {
    min-height: calc(100vh - 176px);
  }

  .forward-record__cover {
    padding: 20px 16px 16px;
  }

  .forward-record__cover h2 {
    font-size: 19px;
  }

  .message-list {
    padding: 16px 12px 24px;
  }

  .message-body {
    max-width: calc(100% - 58px);
  }

  .message-bubble {
    font-size: 15px;
  }
}
</style>
