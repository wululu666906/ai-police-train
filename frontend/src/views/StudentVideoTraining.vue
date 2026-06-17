<template>
  <div class="video-training-page">

    <!-- 加载中 -->
    <div v-if="loading" class="state-center">
      <el-skeleton :rows="4" animated style="max-width:560px" />
    </div>

    <!-- 视频不存在 -->
    <div v-else-if="!video" class="state-center">
      <el-empty description="视频不存在或暂未开放">
        <el-button @click="router.back()">返回</el-button>
      </el-empty>
    </div>

    <!-- 主体 -->
    <template v-else>

      <!-- 顶部状态栏 -->
      <div class="topbar">
        <el-button :icon="ArrowLeft" text class="topbar__back" @click="confirmExit">返回</el-button>
        <div class="topbar__center">
          <el-tag type="danger" effect="dark" size="small">交互实训</el-tag>
          <span class="topbar__title">{{ video.title }}</span>
        </div>
        <div class="topbar__right">
          <span class="topbar__stat">节点 {{ completedCount }}/{{ video.nodes.length }}</span>
          <el-progress :percentage="nodeProgress" :stroke-width="5" style="width:100px" :show-text="false" color="#3b82f6" />
          <span v-if="sessionId" class="topbar__mode-tag" :class="trainingMode === 'exam' ? 'mode-exam' : 'mode-practice'">
            {{ trainingMode === 'exam' ? '考核模式' : '练习模式' }}
          </span>
        </div>
      </div>

      <!-- 主体区域 -->
      <div class="main-area">

        <!-- 视频区 -->
        <div class="video-wrap" ref="videoWrapRef">
          <video
            ref="videoRef"
            class="main-video"
            :src="video.video_url"
            preload="auto"
            @timeupdate="onTimeUpdate"
            @ended="onVideoEnded"
            @contextmenu.prevent
          />

          <!-- 节点弹窗遮罩 -->
          <transition name="node-fade">
            <div v-if="nodeActive && currentNode" class="node-overlay" @click.stop>
              <div class="node-card">

                <!-- 卡片头 -->
                <div class="node-card__head">
                  <span class="node-card__index">节点 {{ currentNodeIndex + 1 }}/{{ video.nodes.length }}</span>
                  <span class="node-card__title">{{ currentNode.title }}</span>
                  <div class="node-card__timer" :class="{ warn: countdown <= 10 }">
                    <el-icon><Timer /></el-icon>
                    {{ countdown }}s
                  </div>
                </div>

                <!-- 卡片体 -->
                <div class="node-card__body">

                  <!-- 指令引导型 -->
                  <template v-if="currentNode.node_type === 'action'">
                    <p class="node-instruction">{{ currentNode.prompt_content?.instruction }}</p>
                    <div v-if="currentNode.prompt_content?.gesture_hint" class="hint-row hint-row--gesture">
                      <span class="hint-label">标准手势</span>
                      <span class="hint-text">{{ currentNode.prompt_content.gesture_hint }}</span>
                    </div>
                    <div v-if="currentNode.prompt_content?.speech_hint" class="hint-row hint-row--speech">
                      <span class="hint-label">标准话术</span>
                      <span class="hint-text">{{ currentNode.prompt_content.speech_hint }}</span>
                    </div>
                    <!-- 语音识别区 -->
                    <div class="speech-area">
                      <div class="speech-status" :class="speechStatus">
                        <el-icon v-if="speechStatus === 'listening'"><Microphone /></el-icon>
                        <el-icon v-else><Microphone /></el-icon>
                        <span>{{ speechStatusLabel }}</span>
                      </div>
                      <div v-if="interimText || finalText" class="speech-transcript">
                        <span class="interim">{{ interimText }}</span>
                        <span v-if="finalText" class="final">{{ finalText }}</span>
                      </div>
                      <div class="speech-actions">
                        <el-button
                          v-if="speechStatus === 'idle'"
                          type="primary" size="small" :icon="Microphone"
                          @click="startSpeech"
                        >开始说话</el-button>
                        <el-button
                          v-else-if="speechStatus === 'listening'"
                          type="warning" size="small"
                          @click="stopSpeech"
                        >停止录音</el-button>
                        <el-button
                          v-if="finalText"
                          type="success" size="small" :icon="Check"
                          @click="submitActionNode"
                        >确认完成</el-button>
                      </div>
                    </div>
                  </template>

                  <!-- 判断题 -->
                  <template v-else-if="currentNode.node_type === 'judge'">
                    <p class="node-instruction">{{ currentNode.node_config?.question }}</p>
                    <div class="judge-row">
                      <el-button type="success" size="large" @click="submitJudge(true)">✓ 正确</el-button>
                      <el-button type="danger"  size="large" @click="submitJudge(false)">✗ 错误</el-button>
                    </div>
                  </template>

                  <!-- 单选题 -->
                  <template v-else-if="currentNode.node_type === 'choice'">
                    <p class="node-instruction">{{ currentNode.node_config?.question }}</p>
                    <div class="choice-list">
                      <button
                        v-for="(opt, oi) in (currentNode.node_config?.options || [])"
                        :key="oi"
                        class="choice-item"
                        :class="{ selected: choiceSelected === Number(oi) }"
                        @click="choiceSelected = Number(oi)"
                      >
                        <span class="choice-alpha">{{ String.fromCharCode(65 + Number(oi)) }}</span>
                        {{ opt }}
                      </button>
                    </div>
                    <el-button
                      type="primary"
                      :disabled="choiceSelected === null"
                      style="margin-top:12px"
                      @click="submitChoice"
                    >提交答案</el-button>
                  </template>

                  <!-- 语音问答 -->
                  <template v-else-if="currentNode.node_type === 'voice_qa'">
                    <p class="node-instruction">{{ currentNode.prompt_content?.instruction }}</p>
                    <div class="speech-area">
                      <div class="speech-status" :class="speechStatus">
                        <el-icon><Microphone /></el-icon>
                        <span>{{ speechStatusLabel }}</span>
                      </div>
                      <div v-if="interimText || finalText" class="speech-transcript">
                        <span class="interim">{{ interimText }}</span>
                        <span class="final">{{ finalText }}</span>
                      </div>
                      <div class="speech-actions">
                        <el-button v-if="speechStatus === 'idle'" type="primary" size="small" :icon="Microphone" @click="startSpeech">开始回答</el-button>
                        <el-button v-else-if="speechStatus === 'listening'" type="warning" size="small" @click="stopSpeech">停止录音</el-button>
                        <el-button v-if="finalText" type="success" size="small" :icon="Check" @click="submitActionNode">提交回答</el-button>
                      </div>
                    </div>
                  </template>

                </div>

                <!-- 超时选项 -->
                <div v-if="showTimeoutOptions" class="timeout-bar">
                  <span class="timeout-bar__label">已超时，请选择：</span>
                  <el-button size="small" @click="retryNode">重新练习（-{{ currentNode.retry_score_deduct }}分）</el-button>
                  <el-button size="small" type="warning" @click="skipNode('skip')">跳过节点（-{{ currentNode.skip_score_deduct }}分）</el-button>
                </div>

                <!-- 判定结果反馈 -->
                <transition name="result-fade">
                  <div v-if="nodeResult" class="node-result" :class="`node-result--${nodeResult}`">
                    <el-icon :size="20">
                      <CircleCheck v-if="nodeResult === 'pass'" />
                      <CircleClose v-else />
                    </el-icon>
                    {{ nodeResult === 'pass' ? '通过！即将继续...' : '未通过，请重试' }}
                  </div>
                </transition>

              </div>
            </div>
          </transition>

          <!-- 悬浮摄像头窗 -->
          <div
            v-if="cameraOn"
            class="cam-float"
            :style="{ left: camPos.x + 'px', top: camPos.y + 'px' }"
            @mousedown="startDrag"
          >
            <video ref="cameraRef" autoplay muted playsinline class="cam-video" />
            <div class="cam-label">
              <span :class="{ 'cam-dot--active': nodeActive }">●</span>
              实时检测
            </div>
          </div>
        </div>

        <!-- 右侧节点进度栏 -->
        <div class="node-rail">
          <div class="node-rail__head">训练节点</div>
          <div
            v-for="(node, i) in video.nodes"
            :key="node.id"
            class="rail-item"
            :class="{
              'rail-item--active': currentNodeIndex === i && nodeActive,
              'rail-item--pass':   nodeStatuses[i] === 'pass',
              'rail-item--skip':   nodeStatuses[i] === 'skip' || nodeStatuses[i] === 'timeout',
            }"
          >
            <div class="rail-dot">
              <el-icon v-if="nodeStatuses[i] === 'pass'"><CircleCheck /></el-icon>
              <el-icon v-else-if="nodeStatuses[i] === 'skip' || nodeStatuses[i] === 'timeout'"><Remove /></el-icon>
              <span v-else>{{ i + 1 }}</span>
            </div>
            <div class="rail-info">
              <div class="rail-name">{{ node.title || `节点${i + 1}` }}</div>
              <div class="rail-time">{{ formatTime(node.trigger_time) }}</div>
            </div>
          </div>
        </div>

      </div>

    </template>

    <!-- 评估报告弹窗 -->
    <van-popup
      v-model:show="showReport"
      round
      :close-on-click-overlay="false"
      teleport="body"
      class="report-popup"
      :overlay-style="{ backgroundColor: 'rgba(0,0,0,0.75)' }"
    >
      <div v-if="report" class="report-card">
        <div class="report-header">
          <div class="report-grade" :class="`grade--${report.grade === '优秀' ? 'excellent' : report.grade === '合格' ? 'pass' : 'fail'}`">
            {{ report.grade }}
          </div>
          <div class="report-score">{{ report.total_score }} <span>/ {{ report.full_score }} 分</span></div>
          <div class="report-pct">得分率 {{ report.percentage }}%</div>
        </div>

        <div class="report-stats">
          <div class="rstat"><div class="rstat__num">{{ report.pass_count }}</div><div class="rstat__label">通过节点</div></div>
          <div class="rstat"><div class="rstat__num rstat__num--warn">{{ report.skip_count }}</div><div class="rstat__label">跳过节点</div></div>
          <div class="rstat"><div class="rstat__num rstat__num--danger">{{ report.total_deducted }}</div><div class="rstat__label">总扣分</div></div>
        </div>

        <div class="report-nodes">
          <div v-for="item in report.node_summaries" :key="item.node_index" class="rnode">
            <span class="rnode__idx">{{ item.node_index + 1 }}</span>
            <span class="rnode__result" :class="`rnode__result--${item.result}`">
              {{ resultLabel(item.result) }}
            </span>
            <span class="rnode__score">{{ item.score_earned }}分</span>
            <span v-if="item.score_deducted" class="rnode__deduct">-{{ item.score_deducted }}</span>
            <span v-if="item.retry_count" class="rnode__retry">重试×{{ item.retry_count }}</span>
          </div>
        </div>

        <div class="report-actions">
          <el-button @click="showReport = false; router.back()">返回展厅</el-button>
          <el-button type="primary" v-if="report.grade === '待重修'" @click="restartTraining">重新训练</el-button>
        </div>
      </div>
    </van-popup>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft, Timer, CircleCheck, CircleClose, Remove,
  Microphone, Check,
} from '@element-plus/icons-vue'
import request from '../utils/request'
import { createSpeechProvider } from '../services/speech/index'
import type { SpeechRecognitionProvider } from '../services/speech/types'

interface VideoNode {
  id: number
  node_index: number
  title: string
  trigger_time: number
  pause_mode: string
  prompt_content: Record<string, any>
  timeout_seconds: number
  retry_score_deduct: number
  skip_score_deduct: number
  node_type: string
  node_config: Record<string, any>
  required_keywords: string[]
  score_weight: number
}

interface VideoDetail {
  id: number
  title: string
  video_url?: string
  video_type: string
  nodes: VideoNode[]
  duration?: number
}

interface ReportItem {
  node_index: number
  result: string
  score_earned: number
  score_deducted: number
  retry_count: number
}

interface Report {
  session_id: number
  video_title: string
  mode: string
  total_score: number
  full_score: number
  percentage: number
  grade: string
  pass_count: number
  skip_count: number
  total_nodes: number
  total_deducted: number
  node_summaries: ReportItem[]
}

const route = useRoute()
const router = useRouter()
const videoId = Number(route.params.id)

// ── 视频 & Session ──
const video = ref<VideoDetail | null>(null)
const loading = ref(true)
const sessionId = ref<number | null>(null)
const trainingMode = ref<'practice' | 'exam'>('practice')

// ── 节点状态 ──
const currentNodeIndex = ref(-1)
const nodeActive = ref(false)
const nodeStatuses = ref<Record<number, string>>({})
const nodeResult = ref<'pass' | 'fail' | null>(null)
const showTimeoutOptions = ref(false)
const countdown = ref(0)
const nodeRetryCount = ref(0)
const nodeStartTime = ref(0)
let countdownTimer: ReturnType<typeof setInterval> | null = null

// ── 答题 ──
const choiceSelected = ref<number | null>(null)

// ── 语音识别 ──
const speechProvider = ref<SpeechRecognitionProvider | null>(null)
const speechStatus = ref<'idle' | 'listening' | 'processing' | 'error'>('idle')
const interimText = ref('')
const finalText = ref('')
const speechStatusLabel = computed(() => ({
  idle: '点击开始说话', listening: '正在识别...', processing: '处理中', error: '识别出错，重试',
}[speechStatus.value] || ''))

// ── 摄像头 ──
const videoRef = ref<HTMLVideoElement | null>(null)
const cameraRef = ref<HTMLVideoElement | null>(null)
const videoWrapRef = ref<HTMLElement | null>(null)
const cameraOn = ref(false)
const camPos = ref({ x: 16, y: 80 })

// ── 报告 ──
const showReport = ref(false)
const report = ref<Report | null>(null)

// ── 计算属性 ──
const currentNode = computed<VideoNode | null>(() =>
  currentNodeIndex.value >= 0 && video.value?.nodes
    ? video.value.nodes[currentNodeIndex.value] ?? null
    : null
)
const completedCount = computed(() => Object.keys(nodeStatuses.value).length)
const nodeProgress = computed(() => {
  const total = video.value?.nodes?.length || 0
  return total ? Math.round((completedCount.value / total) * 100) : 0
})

// ── 生命周期 ──
onMounted(async () => {
  await fetchVideo()
  if (video.value) {
    await initSession()
    await startCamera()
    setupVisibilityDetection()
  }
})

onUnmounted(() => {
  stopCamera()
  clearCountdown()
  speechProvider.value?.stop()
  document.removeEventListener('visibilitychange', onVisibilityChange)
})

// ── 数据加载 ──
async function fetchVideo() {
  loading.value = true
  try {
    const res: any = await request.get(`/videos/${videoId}`)
    video.value = res
  } catch {
    ElMessage.error('加载视频失败')
    video.value = null
  } finally {
    loading.value = false
  }
}

async function initSession() {
  try {
    const res: any = await request.post(`/video-training/start/${videoId}`, null, {
      params: { mode: trainingMode.value },
    } as any)
    sessionId.value = res.id
    trainingMode.value = res.mode || 'practice'
    // 恢复已有节点状态
    if (res.node_results?.length) {
      for (const r of res.node_results) {
        nodeStatuses.value[r.node_index] = r.result
      }
    }
    if (res.resumed) ElMessage.info('已恢复上次未完成的实训')
  } catch {
    ElMessage.warning('无法创建训练记录，进度不会保存')
  }
}

// ── 摄像头 ──
async function startCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
    if (cameraRef.value) cameraRef.value.srcObject = stream
    cameraOn.value = true
    // 语音识别使用同一个 stream
    speechProvider.value = createSpeechProvider()
  } catch {
    ElMessage.warning('无法获取摄像头/麦克风，AI识别不可用')
    cameraOn.value = false
    speechProvider.value = createSpeechProvider()
  }
}

function stopCamera() {
  if (cameraRef.value?.srcObject) {
    const s = cameraRef.value.srcObject as MediaStream
    s.getTracks().forEach(t => t.stop())
  }
}

// ── 违规检测 ──
function setupVisibilityDetection() {
  document.addEventListener('visibilitychange', onVisibilityChange)
}

async function onVisibilityChange() {
  if (document.hidden && sessionId.value && nodeActive.value) {
    try {
      await request.post(`/video-training/session/${sessionId.value}/violation`, {
        type: 'tab_switch',
        detail: '训练期间切换标签页',
      })
    } catch {}
    ElMessage.warning('检测到切换标签页，已记录违规')
  }
}

// ── 视频时间监听 ──
function onTimeUpdate() {
  if (!videoRef.value || !video.value?.nodes || nodeActive.value) return
  const t = Math.floor(videoRef.value.currentTime)
  for (let i = 0; i < video.value.nodes.length; i++) {
    if (nodeStatuses.value[i] !== undefined) continue
    if (t >= video.value.nodes[i].trigger_time) {
      triggerNode(i)
      break
    }
  }
}

function onVideoEnded() {
  if (video.value && completedCount.value < video.value.nodes.length) {
    // 视频结束但还有未触发节点，标记为跳过
    for (let i = 0; i < video.value.nodes.length; i++) {
      if (nodeStatuses.value[i] === undefined) {
        nodeStatuses.value[i] = 'skip'
      }
    }
  }
  finishTraining()
}

// ── 节点触发 ──
function triggerNode(index: number) {
  currentNodeIndex.value = index
  nodeActive.value = true
  nodeResult.value = null
  showTimeoutOptions.value = false
  choiceSelected.value = null
  interimText.value = ''
  finalText.value = ''
  nodeRetryCount.value = 0
  nodeStartTime.value = Date.now()

  videoRef.value?.pause()

  const node = video.value!.nodes[index]
  countdown.value = node.timeout_seconds
  startCountdown()
}

function startCountdown() {
  clearCountdown()
  countdownTimer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      clearCountdown()
      speechProvider.value?.stop()
      showTimeoutOptions.value = true
    }
  }, 1000)
}

function clearCountdown() {
  if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null }
}

// ── 语音识别 ──
function startSpeech() {
  if (!speechProvider.value) return
  interimText.value = ''
  finalText.value = ''
  speechStatus.value = 'listening'
  speechProvider.value.start({ lang: 'zh-CN', continuous: false }, {
    onInterim: (t) => { interimText.value = t },
    onFinal: (t) => { finalText.value = (finalText.value + ' ' + t).trim() },
    onAutoEnd: () => { speechStatus.value = 'idle' },
    onError: () => { speechStatus.value = 'error' },
    onStatusChange: (s) => { speechStatus.value = s },
  })
}

function stopSpeech() {
  speechProvider.value?.stop()
  speechStatus.value = 'idle'
}

// ── 节点提交 ──
async function submitNodeToBackend(
  action: 'pass' | 'skip' | 'timeout',
  extra: Record<string, any> = {},
) {
  if (!sessionId.value || !currentNode.value) return
  const timeUsed = Math.round((Date.now() - nodeStartTime.value) / 1000)
  try {
    await request.post(`/video-training/session/${sessionId.value}/node/submit`, {
      node_id: currentNode.value.id,
      node_index: currentNodeIndex.value,
      action,
      retry_count: nodeRetryCount.value,
      time_used: timeUsed,
      ...extra,
    })
  } catch {
    // 后端提交失败不阻断前端流程
  }
}

function passNode(extra: Record<string, any> = {}) {
  clearCountdown()
  stopSpeech()
  nodeResult.value = 'pass'
  nodeStatuses.value[currentNodeIndex.value] = 'pass'
  submitNodeToBackend('pass', extra)
  setTimeout(() => {
    nodeActive.value = false
    nodeResult.value = null
    videoRef.value?.play()
    checkAllNodesDone()
  }, 1200)
}

async function skipNode(type: 'skip' | 'timeout' = 'skip') {
  clearCountdown()
  stopSpeech()
  nodeStatuses.value[currentNodeIndex.value] = type
  await submitNodeToBackend(type)
  ElMessage.warning(`已${type === 'timeout' ? '超时跳过' : '跳过'}，扣 ${currentNode.value?.skip_score_deduct ?? 20} 分`)
  nodeActive.value = false
  nodeResult.value = null
  videoRef.value?.play()
  checkAllNodesDone()
}

function retryNode() {
  showTimeoutOptions.value = false
  nodeResult.value = null
  nodeRetryCount.value++
  countdown.value = currentNode.value?.timeout_seconds || 60
  startCountdown()
  ElMessage.warning(`重新练习，本次重试扣 ${currentNode.value?.retry_score_deduct ?? 5} 分`)
}

function submitActionNode() {
  stopSpeech()
  passNode({ speech_transcript: (finalText.value || '').trim() })
}

function submitJudge(answer: boolean) {
  const correct = currentNode.value?.node_config?.correct_answer
  if (answer === correct) {
    passNode({ answer_data: { answer } })
  } else {
    nodeResult.value = 'fail'
    const exp = currentNode.value?.node_config?.explanation
    if (exp) ElMessage.info(exp)
    nodeRetryCount.value++
  }
}

function submitChoice() {
  if (choiceSelected.value === null) return
  const correct = currentNode.value?.node_config?.correct_index
  if (choiceSelected.value === correct) {
    passNode({ answer_data: { selected: choiceSelected.value } })
  } else {
    nodeResult.value = 'fail'
    const exp = currentNode.value?.node_config?.explanation
    if (exp) ElMessage.info(exp)
    nodeRetryCount.value++
  }
}

function checkAllNodesDone() {
  const total = video.value?.nodes?.length || 0
  if (completedCount.value >= total) finishTraining()
}

// ── 完成训练 ──
async function finishTraining() {
  if (!sessionId.value) return
  try {
    const res: any = await request.post(`/video-training/session/${sessionId.value}/finish`)
    report.value = res
    showReport.value = true
  } catch {
    ElMessage.error('生成报告失败，请稍后查看历史记录')
    router.back()
  }
}

function restartTraining() {
  showReport.value = false
  router.replace(`/student/video-training/${videoId}`)
}

// ── 退出确认 ──
async function confirmExit() {
  if (!nodeActive.value && completedCount.value === 0) { router.back(); return }
  try {
    await ElMessageBox.confirm('退出后本次训练进度将保留，下次可继续。确认退出？', '退出实训', {
      confirmButtonText: '确认退出', cancelButtonText: '继续训练', type: 'warning',
    })
    router.back()
  } catch {}
}

// ── 摄像头拖拽 ──
function startDrag(e: MouseEvent) {
  const sx = e.clientX - camPos.value.x
  const sy = e.clientY - camPos.value.y
  const mv = (ev: MouseEvent) => { camPos.value = { x: ev.clientX - sx, y: ev.clientY - sy } }
  const up = () => { window.removeEventListener('mousemove', mv); window.removeEventListener('mouseup', up) }
  window.addEventListener('mousemove', mv)
  window.addEventListener('mouseup', up)
}

// ── 工具函数 ──
function formatTime(sec: number) {
  return `${String(Math.floor(sec / 60)).padStart(2, '0')}:${String(sec % 60).padStart(2, '0')}`
}

function resultLabel(r: string) {
  return ({ pass: '通过', skip: '跳过', timeout: '超时', fail: '未完成' } as any)[r] || r
}
</script>

<style scoped lang="scss">
/* ── 整体布局 ── */
.video-training-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #0a0f1a;
  color: #fff;
  overflow: hidden;
  user-select: none;
}

.state-center {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

/* ── 顶部状态栏 ── */
.topbar {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 8px 16px;
  background: rgba(255,255,255,0.04);
  border-bottom: 1px solid rgba(255,255,255,0.07);
  flex-shrink: 0;
  min-height: 44px;

  &__back { color: rgba(255,255,255,0.7) !important; }

  &__center {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
    min-width: 0;
  }

  &__title {
    font-size: 14px;
    font-weight: 600;
    color: #f1f5f9;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &__right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-shrink: 0;
  }

  &__stat {
    font-size: 12px;
    color: rgba(255,255,255,0.45);
    white-space: nowrap;
  }

  &__mode-tag {
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
  }
}

.mode-practice { background: rgba(59,130,246,0.2); color: #60a5fa; }
.mode-exam     { background: rgba(239,68,68,0.2);  color: #f87171; }

/* ── 主体区域 ── */
.main-area {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* ── 视频区 ── */
.video-wrap {
  position: relative;
  flex: 1;
  min-width: 0;
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.main-video {
  max-width: 100%;
  max-height: 100%;
  display: block;
  object-fit: contain;
  /* 禁止进度条拖拽：通过 JS 阻止，CSS 无法完全屏蔽原生控件 */
}

/* ── 节点遮罩 ── */
.node-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0,0,0,0.68);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
  backdrop-filter: blur(3px);
}

.node-card {
  width: min(560px, calc(100% - 32px));
  background: #1e293b;
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0,0,0,0.6);

  &__head {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    background: rgba(255,255,255,0.03);
    border-bottom: 1px solid rgba(255,255,255,0.07);
  }

  &__index {
    font-size: 11px;
    color: rgba(255,255,255,0.4);
    flex-shrink: 0;
  }

  &__title {
    flex: 1;
    font-size: 14px;
    font-weight: 600;
    color: #f1f5f9;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__timer {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    font-weight: 700;
    color: #94a3b8;
    flex-shrink: 0;
    min-width: 48px;
    justify-content: flex-end;

    &.warn { color: #f87171; }
  }

  &__body { padding: 16px; }
}

.node-instruction {
  margin: 0 0 12px;
  font-size: 14px;
  color: #e2e8f0;
  line-height: 1.7;
}

.hint-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 9px 12px;
  border-radius: 6px;
  margin-bottom: 8px;
  font-size: 13px;

  &--gesture { background: rgba(59,130,246,0.1); border-left: 3px solid #3b82f6; }
  &--speech  { background: rgba(16,185,129,0.08); border-left: 3px solid #10b981; }
}

.hint-label {
  font-weight: 700;
  font-size: 11px;
  color: rgba(255,255,255,0.45);
  white-space: nowrap;
  padding-top: 1px;
}

.hint-text {
  color: #cbd5e1;
  line-height: 1.6;
}

/* ── 语音区 ── */
.speech-area {
  margin-top: 12px;
  padding: 12px;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 8px;
}

.speech-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: rgba(255,255,255,0.45);
  margin-bottom: 8px;

  &.listening { color: #34d399; }
  &.error     { color: #f87171; }
}

.speech-transcript {
  min-height: 32px;
  margin-bottom: 10px;
  font-size: 13px;
  line-height: 1.6;

  .interim { color: rgba(255,255,255,0.4); }
  .final   { color: #e2e8f0; margin-left: 4px; }
}

.speech-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* ── 判断题 ── */
.judge-row {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}

/* ── 单选题 ── */
.choice-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
}

.choice-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 14px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 6px;
  color: #cbd5e1;
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s, border-color 0.15s;

  &:hover { background: rgba(59,130,246,0.1); border-color: rgba(59,130,246,0.3); }

  &.selected {
    background: rgba(59,130,246,0.2);
    border-color: #3b82f6;
    color: #93c5fd;
  }
}

.choice-alpha {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(255,255,255,0.1);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

/* ── 超时提示栏 ── */
.timeout-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 10px 16px;
  border-top: 1px solid rgba(255,255,255,0.07);
  background: rgba(239,68,68,0.06);

  &__label {
    font-size: 12px;
    color: #f87171;
    font-weight: 600;
  }
}

/* ── 判定结果 ── */
.node-result {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 10px;
  font-size: 13px;
  font-weight: 600;
  border-top: 1px solid rgba(255,255,255,0.07);

  &--pass { color: #22c55e; background: rgba(34,197,94,0.08); }
  &--fail { color: #f87171; background: rgba(248,113,113,0.08); }
}

/* ── 摄像头悬浮窗 ── */
.cam-float {
  position: absolute;
  width: 148px;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid rgba(59,130,246,0.5);
  cursor: move;
  z-index: 30;
  box-shadow: 0 4px 16px rgba(0,0,0,0.5);
}

.cam-video {
  width: 100%;
  display: block;
  transform: scaleX(-1);
  background: #000;
  aspect-ratio: 4/3;
}

.cam-label {
  padding: 3px 8px;
  background: rgba(0,0,0,0.7);
  font-size: 10px;
  color: rgba(255,255,255,0.6);
  text-align: center;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;

  .cam-dot--active { color: #22c55e; }
}

/* ── 右侧节点进度栏 ── */
.node-rail {
  width: 188px;
  flex-shrink: 0;
  background: #111827;
  border-left: 1px solid rgba(255,255,255,0.07);
  overflow-y: auto;
  padding: 10px 0;

  &__head {
    padding: 0 12px 8px;
    font-size: 10px;
    font-weight: 700;
    color: rgba(255,255,255,0.3);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    border-bottom: 1px solid rgba(255,255,255,0.06);
    margin-bottom: 4px;
  }
}

.rail-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 7px 12px;
  border-left: 3px solid transparent;
  transition: background 0.12s;

  &--active {
    background: rgba(59,130,246,0.1);
    border-left-color: #3b82f6;
  }
  &--pass .rail-dot  { background: rgba(34,197,94,0.15); color: #22c55e; }
  &--skip .rail-dot  { background: rgba(234,179,8,0.12);  color: #eab308; }
  &--pass .rail-name { color: rgba(255,255,255,0.35); }
  &--skip .rail-name { color: rgba(255,255,255,0.25); }
}

.rail-dot {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(255,255,255,0.07);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  color: rgba(255,255,255,0.35);
  flex-shrink: 0;
  margin-top: 1px;
}

.rail-info { flex: 1; min-width: 0; }

.rail-name {
  font-size: 12px;
  color: rgba(255,255,255,0.65);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rail-time {
  font-size: 10px;
  color: rgba(255,255,255,0.25);
  margin-top: 1px;
}

/* ── 评估报告弹窗 ── */
.report-popup {
  width: min(480px, calc(100vw - 24px));
  background: transparent;
}

.report-card {
  background: #1e293b;
  border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.1);
  overflow: hidden;
  padding: 24px;
  color: #e2e8f0;
}

.report-header {
  text-align: center;
  padding-bottom: 20px;
  border-bottom: 1px solid rgba(255,255,255,0.07);
  margin-bottom: 16px;
}

.report-grade {
  font-size: 28px;
  font-weight: 900;
  letter-spacing: 0.04em;
  margin-bottom: 6px;

  &.grade--excellent { color: #22c55e; }
  &.grade--pass      { color: #3b82f6; }
  &.grade--fail      { color: #f87171; }
}

.report-score {
  font-size: 36px;
  font-weight: 700;
  color: #f1f5f9;

  span { font-size: 16px; color: rgba(255,255,255,0.4); }
}

.report-pct {
  font-size: 13px;
  color: rgba(255,255,255,0.4);
  margin-top: 4px;
}

.report-stats {
  display: flex;
  justify-content: space-around;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid rgba(255,255,255,0.07);
  margin-bottom: 14px;
}

.rstat {
  text-align: center;

  &__num {
    font-size: 22px;
    font-weight: 700;
    color: #f1f5f9;

    &--warn   { color: #eab308; }
    &--danger { color: #f87171; }
  }

  &__label {
    font-size: 11px;
    color: rgba(255,255,255,0.4);
    margin-top: 3px;
  }
}

.report-nodes {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 220px;
  overflow-y: auto;
  margin-bottom: 20px;
}

.rnode {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: rgba(255,255,255,0.03);
  border-radius: 6px;
  font-size: 12px;

  &__idx {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: rgba(255,255,255,0.08);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    font-weight: 700;
    color: rgba(255,255,255,0.4);
    flex-shrink: 0;
  }

  &__result {
    font-weight: 600;
    min-width: 40px;

    &--pass    { color: #22c55e; }
    &--skip,
    &--timeout { color: #eab308; }
    &--fail    { color: #f87171; }
  }

  &__score  { color: #94a3b8; margin-left: auto; }
  &__deduct { color: #f87171; font-size: 11px; }
  &__retry  { color: #eab308; font-size: 11px; }
}

.report-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
}

/* ── 动画 ── */
.node-fade-enter-active,
.node-fade-leave-active { transition: opacity 0.22s ease; }
.node-fade-enter-from,
.node-fade-leave-to     { opacity: 0; }

.result-fade-enter-active,
.result-fade-leave-active { transition: opacity 0.2s, transform 0.2s; }
.result-fade-enter-from,
.result-fade-leave-to     { opacity: 0; transform: translateY(4px); }
</style>
