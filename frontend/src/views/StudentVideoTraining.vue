<template>
  <div class="video-training-page">
    <div v-if="loading" class="state-center">
      <el-skeleton :rows="4" animated style="max-width: 560px" />
    </div>

    <div v-else-if="!video" class="state-center">
      <el-empty description="视频不存在或暂未开放">
        <el-button @click="router.back()">返回</el-button>
      </el-empty>
    </div>

    <div v-else>
      <div class="topbar">
        <el-button :icon="ArrowLeft" text class="topbar__back" @click="confirmExit">返回</el-button>
        <div class="topbar__center">
          <el-tag type="danger" effect="dark" size="small">交互实训</el-tag>
          <span class="topbar__title">{{ video.title }}</span>
        </div>
        <div class="topbar__right">
          <span class="topbar__stat">节点 {{ completedCount }}/{{ video.nodes.length }}</span>
          <el-progress :percentage="nodeProgress" :stroke-width="5" style="width: 100px" :show-text="false" color="#3b82f6" />
        </div>
      </div>

      <div class="main-area">
        <div class="video-wrap" ref="videoWrapRef">
          <video
            ref="videoRef"
            class="main-video"
            :src="video.video_url"
            preload="auto"
            @timeupdate="onTimeUpdate"
            @ended="onVideoEnded"
            @contextmenu.prevent
          ></video>

          <transition name="node-fade">
            <div v-if="nodeActive && currentNode" class="node-overlay" @click.stop>
              <div class="node-card">
                <div class="node-card__head">
                  <span class="node-card__index">节点 {{ currentNodeIndex + 1 }}/{{ video.nodes.length }}</span>
                  <span class="node-card__title">{{ currentNode.title }}</span>
                  <div class="node-card__timer" :class="{ warn: countdown <= 10 }">
                    <el-icon><Timer /></el-icon>
                    {{ countdown }}s
                  </div>
                </div>

                <div class="node-card__body">
                  <div v-if="currentNode.node_type === 'judge'">
                    <p class="node-instruction">{{ currentNode.node_config?.question }}</p>
                    <div class="judge-row">
                      <el-button type="success" size="large" @click="submitJudge(true)">正确</el-button>
                      <el-button type="danger" size="large" @click="submitJudge(false)">错误</el-button>
                    </div>
                  </div>

                  <div v-else-if="currentNode.node_type === 'choice'">
                    <p class="node-instruction">{{ currentNode.node_config?.question }}</p>
                    <div class="choice-list">
                      <button
                        v-for="(opt, oi) in currentNode.node_config?.options || []"
                        :key="oi"
                        class="choice-item"
                        :class="{ selected: choiceSelected === Number(oi) }"
                        @click="choiceSelected = Number(oi)"
                      >
                        <span class="choice-alpha">{{ String.fromCharCode(65 + Number(oi)) }}</span>
                        {{ opt }}
                      </button>
                    </div>
                    <el-button type="primary" :disabled="choiceSelected === null" style="margin-top: 12px" @click="submitChoice">提交答案</el-button>
                  </div>

                  <div v-else>
                    <p class="node-instruction">{{ currentNode.prompt_content?.instruction }}</p>
                    <div v-if="currentNode.prompt_content?.gesture_hint" class="hint-row hint-row--gesture">
                      <span class="hint-label">标准手势</span>
                      <span class="hint-text">{{ currentNode.prompt_content.gesture_hint }}</span>
                    </div>
                    <div v-if="currentNode.prompt_content?.script_hint" class="hint-row hint-row--script">
                      <span class="hint-label">标准话术</span>
                      <span class="hint-text">{{ currentNode.prompt_content.script_hint }}</span>
                    </div>
                    <div class="response-area">
                      <el-input v-model="finalText" type="textarea" :rows="3" placeholder="请输入话术或回答内容"></el-input>
                      <div class="response-actions">
                        <el-button type="success" size="small" :icon="Check" :disabled="!finalText.trim()" @click="submitActionNode">提交</el-button>
                      </div>
                    </div>
                  </div>
                </div>

                <div v-if="showTimeoutOptions" class="timeout-bar">
                  <span class="timeout-bar__label">已超时，请选择：</span>
                  <el-button size="small" @click="retryNode">重新练习</el-button>
                  <el-button size="small" type="warning" @click="skipNode('skip')">跳过节点</el-button>
                </div>

                <transition name="result-fade">
                  <div v-if="nodeResult" class="node-result" :class="`node-result--${nodeResult}`">
                    <el-icon :size="20">
                      <CircleCheck v-if="nodeResult === 'pass'" />
                      <CircleClose v-else />
                    </el-icon>
                    {{ nodeResult === 'pass' ? '通过，即将继续...' : '未通过，请重试' }}
                  </div>
                </transition>
              </div>
            </div>
          </transition>

          <div
            v-if="cameraOn"
            class="cam-float"
            :style="{ left: camPos.x + 'px', top: camPos.y + 'px' }"
            @mousedown="startDrag"
          >
            <video ref="cameraRef" autoplay muted playsinline class="cam-video"></video>
            <div class="cam-label">
              <span :class="{ 'cam-dot--active': nodeActive }">●</span>
              实时检测
            </div>
          </div>
        </div>

        <div class="node-rail">
          <div class="node-rail__head">训练节点</div>
          <div
            v-for="(node, i) in video.nodes"
            :key="node.id"
            class="rail-item"
            :class="{
              'rail-item--active': currentNodeIndex === i && nodeActive,
              'rail-item--pass': nodeStatuses[i] === 'pass',
              'rail-item--skip': nodeStatuses[i] === 'skip' || nodeStatuses[i] === 'timeout',
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
    </div>

    <van-popup v-model:show="showReport" round :close-on-click-overlay="false" teleport="body" class="report-popup">
      <div v-if="report" class="report-card">
        <div class="report-header">
          <div class="report-grade">{{ report.grade }}</div>
          <div class="report-score">{{ report.total_score }} <span>/ {{ report.full_score }} 分</span></div>
          <div class="report-pct">得分率 {{ report.percentage }}%</div>
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
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Timer, CircleCheck, CircleClose, Remove, Check } from '@element-plus/icons-vue'
import request from '../utils/request'

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

const video = ref<VideoDetail | null>(null)
const loading = ref(true)
const sessionId = ref<number | null>(null)
const trainingMode = ref<'practice' | 'exam'>('practice')
const currentNodeIndex = ref(-1)
const nodeActive = ref(false)
const nodeStatuses = ref<Record<number, string>>({})
const nodeResult = ref<'pass' | 'fail' | null>(null)
const showTimeoutOptions = ref(false)
const countdown = ref(0)
const nodeRetryCount = ref(0)
const nodeStartTime = ref(0)
const choiceSelected = ref<number | null>(null)
const finalText = ref('')
const videoRef = ref<HTMLVideoElement | null>(null)
const cameraRef = ref<HTMLVideoElement | null>(null)
const videoWrapRef = ref<HTMLElement | null>(null)
const cameraOn = ref(false)
const camPos = ref({ x: 16, y: 80 })
const showReport = ref(false)
const report = ref<Report | null>(null)
let countdownTimer: ReturnType<typeof setInterval> | null = null

const currentNode = computed<VideoNode | null>(() =>
  currentNodeIndex.value >= 0 && video.value?.nodes ? video.value.nodes[currentNodeIndex.value] ?? null : null,
)
const completedCount = computed(() => Object.keys(nodeStatuses.value).length)
const nodeProgress = computed(() => {
  const total = video.value?.nodes?.length || 0
  return total ? Math.round((completedCount.value / total) * 100) : 0
})

onMounted(async () => {
  await fetchVideo()
  if (video.value) {
    await initSession()
    await startCamera()
  }
})

onUnmounted(() => {
  stopCamera()
  clearCountdown()
})

async function fetchVideo() {
  loading.value = true
  try {
    video.value = await request.get(`/videos/${videoId}`)
  } catch {
    ElMessage.error('加载视频失败')
    video.value = null
  } finally {
    loading.value = false
  }
}

async function initSession() {
  try {
    const res: any = await request.post(`/video-training/start/${videoId}`, null, { params: { mode: trainingMode.value } } as any)
    sessionId.value = res.id
    trainingMode.value = res.mode || 'practice'
    if (res.node_results?.length) {
      for (const item of res.node_results) nodeStatuses.value[item.node_index] = item.result
    }
  } catch {
    ElMessage.warning('无法创建训练记录')
  }
}

async function startCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true })
    if (cameraRef.value) cameraRef.value.srcObject = stream
    cameraOn.value = true
  } catch {
    ElMessage.warning('无法获取摄像头，监考画面不可用')
    cameraOn.value = false
  }
}

function stopCamera() {
  const stream = cameraRef.value?.srcObject as MediaStream | null
  stream?.getTracks().forEach((track) => track.stop())
}

function onTimeUpdate() {
  if (!videoRef.value || !video.value?.nodes || nodeActive.value) return
  const current = Math.floor(videoRef.value.currentTime)
  for (let i = 0; i < video.value.nodes.length; i += 1) {
    if (nodeStatuses.value[i] !== undefined) continue
    if (current >= video.value.nodes[i].trigger_time) {
      triggerNode(i)
      break
    }
  }
}

function onVideoEnded() {
  if (video.value && completedCount.value < video.value.nodes.length) {
    for (let i = 0; i < video.value.nodes.length; i += 1) {
      if (nodeStatuses.value[i] === undefined) nodeStatuses.value[i] = 'skip'
    }
  }
  finishTraining()
}

function triggerNode(index: number) {
  currentNodeIndex.value = index
  nodeActive.value = true
  nodeResult.value = null
  showTimeoutOptions.value = false
  choiceSelected.value = null
  finalText.value = ''
  nodeRetryCount.value = 0
  nodeStartTime.value = Date.now()
  videoRef.value?.pause()
  countdown.value = video.value!.nodes[index].timeout_seconds
  startCountdown()
}

function startCountdown() {
  clearCountdown()
  countdownTimer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) {
      clearCountdown()
      showTimeoutOptions.value = true
    }
  }, 1000)
}

function clearCountdown() {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

async function submitNodeToBackend(action: 'pass' | 'skip' | 'timeout', extra: Record<string, any> = {}) {
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
    // ignore submit error
  }
}

function passNode(extra: Record<string, any> = {}) {
  clearCountdown()
  nodeResult.value = 'pass'
  nodeStatuses.value[currentNodeIndex.value] = 'pass'
  void submitNodeToBackend('pass', extra)
  window.setTimeout(() => {
    nodeActive.value = false
    nodeResult.value = null
    videoRef.value?.play()
    checkAllNodesDone()
  }, 800)
}

async function skipNode(type: 'skip' | 'timeout' = 'skip') {
  clearCountdown()
  nodeStatuses.value[currentNodeIndex.value] = type
  await submitNodeToBackend(type)
  nodeActive.value = false
  nodeResult.value = null
  videoRef.value?.play()
  checkAllNodesDone()
}

function retryNode() {
  showTimeoutOptions.value = false
  nodeResult.value = null
  nodeRetryCount.value += 1
  countdown.value = currentNode.value?.timeout_seconds || 60
  startCountdown()
}

function submitActionNode() {
  if (!finalText.value.trim()) return
  passNode({ answer_data: { text: finalText.value.trim() } })
}

function submitJudge(answer: boolean) {
  const correct = currentNode.value?.node_config?.correct_answer
  if (answer === correct) {
    passNode({ answer_data: { answer } })
  } else {
    nodeResult.value = 'fail'
    nodeRetryCount.value += 1
  }
}

function submitChoice() {
  if (choiceSelected.value === null) return
  const correct = currentNode.value?.node_config?.correct_index
  if (choiceSelected.value === correct) {
    passNode({ answer_data: { selected: choiceSelected.value } })
  } else {
    nodeResult.value = 'fail'
    nodeRetryCount.value += 1
  }
}

function checkAllNodesDone() {
  if ((video.value?.nodes.length || 0) > 0 && completedCount.value >= (video.value?.nodes.length || 0)) {
    finishTraining()
  }
}

async function finishTraining() {
  if (!sessionId.value) return
  try {
    const res: any = await request.post(`/video-training/session/${sessionId.value}/finish`)
    report.value = res
    showReport.value = true
  } catch {
    ElMessage.warning('生成报告失败')
  }
}

async function restartTraining() {
  showReport.value = false
  report.value = null
  nodeStatuses.value = {}
  currentNodeIndex.value = -1
  nodeActive.value = false
  await initSession()
  if (videoRef.value) {
    videoRef.value.currentTime = 0
    void videoRef.value.play()
  }
}

async function confirmExit() {
  try {
    await ElMessageBox.confirm('确认退出当前视频实训？', '提示', { type: 'warning' })
    router.back()
  } catch {
    // ignore
  }
}

function formatTime(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

function resultLabel(result: string) {
  return result === 'pass' ? '通过' : result === 'skip' ? '跳过' : result === 'timeout' ? '超时' : '未通过'
}

function startDrag() {
  // simplified placeholder
}
</script>

<style scoped>
.video-training-page { min-height: 100vh; background: #0f172a; color: #e2e8f0; }
.state-center { min-height: 60vh; display: flex; align-items: center; justify-content: center; }
.topbar { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; background: #111827; }
.topbar__center, .topbar__right { display: flex; align-items: center; gap: 12px; }
.topbar__title, .topbar__stat { font-weight: 600; }
.main-area { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 16px; padding: 16px 20px 24px; }
.video-wrap { position: relative; min-height: 520px; border-radius: 12px; overflow: hidden; background: #020617; }
.main-video { width: 100%; height: 100%; min-height: 520px; object-fit: contain; background: #000; }
.node-overlay { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; padding: 24px; background: rgba(2, 6, 23, 0.74); }
.node-card { width: min(680px, 100%); background: #111827; border: 1px solid rgba(148, 163, 184, 0.25); border-radius: 12px; box-shadow: 0 24px 64px rgba(0, 0, 0, 0.35); }
.node-card__head { display: flex; align-items: center; gap: 12px; padding: 16px 18px; border-bottom: 1px solid rgba(148, 163, 184, 0.18); }
.node-card__index { color: #93c5fd; font-size: 13px; }
.node-card__title { flex: 1; font-size: 18px; font-weight: 700; }
.node-card__timer { display: inline-flex; align-items: center; gap: 6px; color: #cbd5e1; }
.node-card__timer.warn { color: #fca5a5; }
.node-card__body { padding: 18px; }
.node-instruction { margin: 0 0 12px; line-height: 1.7; color: #f8fafc; }
.hint-row { display: flex; gap: 10px; margin-bottom: 8px; padding: 10px 12px; border-radius: 8px; background: rgba(255, 255, 255, 0.04); }
.hint-label { color: #93c5fd; font-weight: 700; white-space: nowrap; }
.hint-text { color: #cbd5e1; line-height: 1.6; }
.response-area { display: grid; gap: 10px; margin-top: 12px; }
.response-actions, .judge-row { display: flex; gap: 10px; flex-wrap: wrap; }
.choice-list { display: grid; gap: 8px; }
.choice-item { width: 100%; padding: 12px 14px; border: 1px solid #334155; border-radius: 8px; background: #0f172a; color: #e2e8f0; text-align: left; cursor: pointer; }
.choice-item.selected { border-color: #60a5fa; background: rgba(37, 99, 235, 0.16); }
.choice-alpha { display: inline-block; width: 24px; color: #93c5fd; font-weight: 700; }
.timeout-bar { display: flex; align-items: center; gap: 10px; padding: 0 18px 18px; flex-wrap: wrap; }
.timeout-bar__label { color: #fbbf24; font-size: 13px; }
.node-result { display: flex; align-items: center; gap: 8px; margin: 0 18px 18px; padding: 10px 12px; border-radius: 8px; }
.node-result--pass { background: rgba(34, 197, 94, 0.12); color: #86efac; }
.node-result--fail { background: rgba(239, 68, 68, 0.12); color: #fca5a5; }
.cam-float { position: absolute; z-index: 3; width: 220px; border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 10px; overflow: hidden; background: rgba(15, 23, 42, 0.85); }
.cam-video { display: block; width: 100%; aspect-ratio: 4 / 3; object-fit: cover; background: #020617; }
.cam-label { display: flex; align-items: center; gap: 8px; padding: 8px 10px; font-size: 12px; color: #cbd5e1; }
.cam-dot--active { color: #22c55e; }
.node-rail { border: 1px solid rgba(148, 163, 184, 0.18); border-radius: 12px; background: #111827; padding: 14px; }
.node-rail__head { margin-bottom: 10px; font-weight: 700; }
.rail-item { display: flex; gap: 10px; padding: 10px 0; border-top: 1px solid rgba(148, 163, 184, 0.12); }
.rail-item:first-of-type { border-top: 0; }
.rail-dot { width: 26px; height: 26px; border-radius: 999px; display: inline-flex; align-items: center; justify-content: center; background: #1e293b; color: #cbd5e1; flex: 0 0 auto; }
.rail-item--pass .rail-dot { background: rgba(34, 197, 94, 0.18); color: #86efac; }
.rail-item--skip .rail-dot { background: rgba(245, 158, 11, 0.18); color: #fcd34d; }
.rail-item--active .rail-dot { background: rgba(59, 130, 246, 0.2); color: #93c5fd; }
.rail-info { min-width: 0; }
.rail-name { font-size: 14px; font-weight: 600; color: #f8fafc; }
.rail-time { margin-top: 4px; font-size: 12px; color: #94a3b8; }
.report-card { min-width: min(480px, 92vw); padding: 20px; background: #111827; color: #e2e8f0; }
.report-header { display: grid; gap: 10px; margin-bottom: 16px; }
.report-grade { font-size: 28px; font-weight: 800; }
.report-score { font-size: 18px; }
.report-pct { color: #94a3b8; }
.report-actions { display: flex; justify-content: flex-end; gap: 10px; }
@media (max-width: 960px) { .main-area { grid-template-columns: 1fr; } .video-wrap { min-height: 360px; } .main-video { min-height: 360px; } }
</style>
