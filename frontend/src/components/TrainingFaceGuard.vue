<template>
  <section class="face-guard" :class="[`face-guard--${mode}`, { 'face-guard--passed': verified }]">
    <div class="face-guard__camera">
      <video ref="videoRef" autoplay muted playsinline></video>
      <canvas ref="canvasRef" class="face-guard__canvas"></canvas>
      <div v-if="!cameraReady" class="face-guard__placeholder">
        <van-icon name="photograph" size="28" />
      </div>
    </div>

    <div class="face-guard__body">
      <div class="face-guard__title-row">
        <strong>人脸验证</strong>
        <span class="face-guard__badge">{{ badgeText }}</span>
      </div>
      <div class="face-guard__meta">
        <span>连续异常次数 {{ failureCount }}/{{ maxFailures }}</span>
      </div>
      <p v-if="failureCount >= maxFailures">
        人脸异常已连续达到上限，系统将自动终止训练并进入评估报告。
      </p>
      <div v-if="mode === 'gate'" class="face-guard__actions">
        <van-button size="small" type="primary" :loading="verifying" @click="runVerify">开始验证</van-button>
      </div>
    </div>

    <van-dialog
      v-model:show="verifyDialogVisible"
      title="人脸验证"
      :show-confirm-button="false"
      :close-on-click-overlay="false"
      class-name="face-verify-dialog"
    >
      <div class="face-verify">
        <div class="face-verify__circle">
          <video ref="dialogVideoRef" autoplay muted playsinline></video>
          <div v-if="!cameraReady" class="face-verify__mask">正在打开摄像头...</div>
        </div>
        <strong>请正对摄像头</strong>
        <p>{{ verifyHint }}</p>
        <div class="face-verify__feedback" :class="verifyFeedbackClass" aria-live="polite">
          <div class="face-verify__feedback-row">
            <span class="face-verify__dot" :class="{ 'is-active': verifyInFlight }"></span>
            <span>{{ verifyStatusText }}</span>
          </div>
          <div class="face-verify__progress" aria-hidden="true">
            <span :style="{ width: `${verifyProgressPercent}%` }"></span>
          </div>
          <div class="face-verify__feedback-row face-verify__feedback-row--muted">
            <span>已采集 {{ verifyAttemptCount }} 帧</span>
            <span v-if="lastSimilarityText">匹配度 {{ lastSimilarityText }}</span>
          </div>
        </div>
        <van-button size="small" plain hairline type="default" @click="cancelVerify">退出验证</van-button>
      </div>
    </van-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { showToast } from 'vant'
import request from '../utils/request'
import { FACE_HEARTBEAT_RETRY_MS, FACE_VERIFY_RETRY_MS, localizeFaceMessage } from '../utils/faceVerification'

const props = defineProps<{
  sessionId: string | number
  mode?: 'gate' | 'monitor'
}>()

const emit = defineEmits<{
  (event: 'verified'): void
  (event: 'failed', message: string): void
  (event: 'terminated', payload: any): void
}>()

const videoRef = ref<HTMLVideoElement | null>(null)
const dialogVideoRef = ref<HTMLVideoElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const cameraReady = ref(false)
const verified = ref(false)
const verifying = ref(false)
const failureCount = ref(0)
const maxFailures = ref(5)
const stream = ref<MediaStream | null>(null)
const heartbeatTimer = ref<number | null>(null)
const verifyTimer = ref<number | null>(null)
const verifyInFlight = ref(false)
const heartbeatInFlight = ref(false)
const verifyDialogVisible = ref(false)
const verifyHint = ref('请将脸部放在圆形区域内，系统正在识别本人身份。')
const verifyStatusText = ref('等待启动人脸识别模型')
const verifyAttemptCount = ref(0)
const lastSimilarityText = ref('')
const lastSimilarityScore = ref(0)

const targetCameraLabel = 'HK 5M CAM 200W'
const builtInCameraLabel = 'ASUS FHD webcam'
const verifyRetryMs = FACE_VERIFY_RETRY_MS
const heartbeatRetryMs = FACE_HEARTBEAT_RETRY_MS

const mode = computed(() => props.mode || (verified.value ? 'monitor' : 'gate'))
const badgeText = computed(() => {
  if (failureCount.value >= maxFailures.value) return '已中断'
  if (verified.value) return '已通过'
  if (verifying.value) return '验证中'
  return '待验证'
})

const verifyFeedbackClass = computed(() => ({
  'face-verify__feedback--matching': verifyInFlight.value,
  'face-verify__feedback--success': verified.value,
  'face-verify__feedback--warning': verifying.value && verifyAttemptCount.value > 0 && !verifyInFlight.value && !verified.value,
}))

const verifyProgressPercent = computed(() => {
  if (verified.value) return 100
  if (lastSimilarityScore.value > 0) return Math.max(12, Math.min(96, Math.round(lastSimilarityScore.value * 100)))
  if (verifyInFlight.value) return Math.min(72, 18 + verifyAttemptCount.value * 10)
  return verifyAttemptCount.value > 0 ? 18 : 8
})

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

const waitForVideoReady = async (video: HTMLVideoElement | null, timeoutMs = 3000) => {
  const startedAt = Date.now()
  while (Date.now() - startedAt < timeoutMs) {
    if (video && video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.videoWidth > 0 && video.videoHeight > 0) {
      return true
    }
    await sleep(40)
  }
  return false
}

const scoreVideoDevice = (device: MediaDeviceInfo) => {
  const label = device.label.toLowerCase()
  if (label.includes(targetCameraLabel.toLowerCase())) return 200
  if (label.includes(builtInCameraLabel.toLowerCase())) return 100
  return 0
}

const chooseVideoInput = async () => {
  const devices = await navigator.mediaDevices.enumerateDevices()
  const videoInputs = devices.filter((device) => device.kind === 'videoinput').map((device, index) => ({ device, index }))
  return [...videoInputs].sort((a, b) => {
    const scoreDiff = scoreVideoDevice(b.device) - scoreVideoDevice(a.device)
    return scoreDiff || a.index - b.index
  })[0]?.device || null
}

const openStream = async (deviceId?: string) => {
  const video: MediaTrackConstraints = deviceId ? { deviceId: { exact: deviceId } } : { facingMode: 'user' }
  return navigator.mediaDevices.getUserMedia({
    video: {
      ...video,
      width: { ideal: 640 },
      height: { ideal: 640 },
    },
    audio: false,
  })
}

const bindStreamToVideos = async (media: MediaStream) => {
  if (videoRef.value) {
    videoRef.value.srcObject = media
    await videoRef.value.play()
    await waitForVideoReady(videoRef.value)
  }
  if (dialogVideoRef.value) {
    dialogVideoRef.value.srcObject = media
    await dialogVideoRef.value.play()
    await waitForVideoReady(dialogVideoRef.value)
  }
}

const startCamera = async () => {
  if (stream.value && cameraReady.value) {
    await nextTick()
    await bindStreamToVideos(stream.value)
    return
  }
  let fallbackStream: MediaStream | null = null
  try {
    const initialStream = await openStream()
    fallbackStream = initialStream
    const selected = await chooseVideoInput()
    let media: MediaStream = initialStream
    if (selected?.deviceId) {
      const initialTrack = initialStream.getVideoTracks()[0]
      const selectedIsInitial = initialTrack?.getSettings?.().deviceId === selected.deviceId || initialTrack?.label === selected.label
      try {
        if (!selectedIsInitial) {
          const selectedStream = await openStream(selected.deviceId)
          fallbackStream.getTracks().forEach((track) => track.stop())
          fallbackStream = null
          media = selectedStream
        }
      } catch {
        media = initialStream
      }
    }
    stream.value = media
    await bindStreamToVideos(media)
    cameraReady.value = true
  } catch {
    fallbackStream?.getTracks().forEach((track) => track.stop())
    const message = '无法打开摄像头，请检查浏览器权限或摄像头占用情况。'
    verifyHint.value = message
    emit('failed', message)
  }
}

const stopVerifyLoop = () => {
  if (verifyTimer.value != null) {
    window.clearInterval(verifyTimer.value)
    verifyTimer.value = null
  }
  verifyInFlight.value = false
}

const stopHeartbeat = () => {
  if (heartbeatTimer.value != null) {
    window.clearInterval(heartbeatTimer.value)
    heartbeatTimer.value = null
  }
  heartbeatInFlight.value = false
}

const stopCamera = () => {
  stopVerifyLoop()
  stopHeartbeat()
  stream.value?.getTracks().forEach((track) => track.stop())
  stream.value = null
  cameraReady.value = false
}

const captureFrame = (size = 360, jpegQuality = 0.72) => {
  const video = videoRef.value
  const canvas = canvasRef.value
  if (!video || !canvas || !cameraReady.value || !video.videoWidth) return null
  const drawFrame = (targetSize: number, quality: number) => {
    const sourceSize = Math.min(video.videoWidth, video.videoHeight)
    const sx = Math.max(0, Math.round((video.videoWidth - sourceSize) / 2))
    const sy = Math.max(0, Math.round((video.videoHeight - sourceSize) / 2))
    canvas.width = targetSize
    canvas.height = targetSize
    const ctx = canvas.getContext('2d')
    if (!ctx) return null
    ctx.drawImage(video, sx, sy, sourceSize, sourceSize, 0, 0, canvas.width, canvas.height)
    return canvas.toDataURL('image/jpeg', quality)
  }
  const frame = drawFrame(size, jpegQuality)
  // Keep every verification and monitoring request below the public proxy body limit.
  if (!frame || frame.length <= 48_000) return frame
  return drawFrame(300, 0.62)
}

const buildPayload = (endpoint: 'verify' | 'heartbeat') => {
  const frame = captureFrame()
  if (!frame) return null
  return {
    frame,
    quality_metrics: {
      visible_region: 'circle',
      circle_center: [0.5, 0.5],
      circle_radius: 0.5,
    },
  }
}

const applyResult = (result: any, endpoint: 'verify' | 'heartbeat') => {
  if (endpoint === 'heartbeat') {
    failureCount.value = Number(result?.monitor_failure_count ?? result?.failure_count ?? failureCount.value)
  }
  if (endpoint === 'verify' && result?.passed) failureCount.value = 0
  maxFailures.value = Number(result?.max_failures ?? maxFailures.value)
  if (result?.terminated) {
    verified.value = false
    failureCount.value = maxFailures.value
    stopHeartbeat()
    stopVerifyLoop()
    verifyDialogVisible.value = false
    verifying.value = false
    emit('terminated', result)
    return
  }
  if (result?.passed) {
    if (endpoint === 'verify') {
      verifyStatusText.value = '人脸匹配成功，正在进入训练'
      lastSimilarityText.value = formatSimilarity(result?.similarity)
    }
    verified.value = true
    stopVerifyLoop()
    verifyDialogVisible.value = false
    verifying.value = false
    emit('verified')
    startHeartbeat()
    return
  }
  if (endpoint === 'verify') {
    verifyHint.value = localizeFaceMessage(result?.reason)
    verifyStatusText.value = result?.reason ? '本帧未通过，正在继续匹配' : '正在比对本人身份'
    lastSimilarityText.value = formatSimilarity(result?.similarity)
  }
}

const formatSimilarity = (value: any) => {
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric <= 0) {
    lastSimilarityScore.value = 0
    return ''
  }
  lastSimilarityScore.value = numeric
  return `${Math.round(numeric * 100)}%`
}

const postFrame = async (endpoint: 'verify' | 'heartbeat') => {
  if (endpoint === 'verify' && verifyInFlight.value) return
  if (endpoint === 'heartbeat' && heartbeatInFlight.value) return
  if (endpoint === 'verify') verifyInFlight.value = true
  if (endpoint === 'heartbeat') heartbeatInFlight.value = true
  const payload = buildPayload(endpoint)
  if (!payload) {
    if (endpoint === 'verify') verifyHint.value = '摄像头画面尚未就绪，请稍候。'
    if (endpoint === 'verify') verifyStatusText.value = '等待摄像头画面稳定'
    if (endpoint === 'verify') verifyInFlight.value = false
    if (endpoint === 'heartbeat') heartbeatInFlight.value = false
    return
  }
  try {
    if (endpoint === 'verify') {
      verifyAttemptCount.value += 1
      verifyStatusText.value = `正在调用人脸识别模型，第 ${verifyAttemptCount.value} 次匹配`
    }
    const result = await request.post(`/face/session/${props.sessionId}/${endpoint}`, payload, { _skipErrorToast: true } as any)
    applyResult(result, endpoint)
  } finally {
    if (endpoint === 'verify') verifyInFlight.value = false
    if (endpoint === 'heartbeat') heartbeatInFlight.value = false
  }
}

const runVerify = async () => {
  if (verifying.value) return
  verifying.value = true
  verified.value = false
  verifyDialogVisible.value = true
  verifyHint.value = '请将脸部放在圆形区域内，系统正在识别本人身份。'
  verifyStatusText.value = '正在启动摄像头和人脸识别模型'
  verifyAttemptCount.value = 0
  lastSimilarityText.value = ''
  lastSimilarityScore.value = 0
  try {
    await nextTick()
    await startCamera()
    await nextTick()
    if (stream.value) await bindStreamToVideos(stream.value)
    await sleep(40)
    await postFrame('verify')
    stopVerifyLoop()
    verifyTimer.value = window.setInterval(() => {
      if (!verifying.value || !verifyDialogVisible.value || verified.value) return
      void postFrame('verify').catch((error: any) => {
        verifyHint.value = localizeFaceMessage(error?.response?.data?.detail, '检测失败，请调整后继续。')
        verifyStatusText.value = '本次识别请求失败，正在继续尝试'
      })
    }, verifyRetryMs)
  } catch (error: any) {
    const message = localizeFaceMessage(error?.response?.data?.detail || error?.message)
    verifyHint.value = message
    verifyStatusText.value = '人脸识别未启动成功'
    emit('failed', message)
  }
}

const cancelVerify = () => {
  stopVerifyLoop()
  verifying.value = false
  verifyDialogVisible.value = false
  verifyStatusText.value = '已退出验证'
}

const startHeartbeat = () => {
  stopHeartbeat()
  heartbeatTimer.value = window.setInterval(() => {
    if (!verified.value || verifying.value) return
    void postFrame('heartbeat').catch(() => {
      // Heartbeat errors are surfaced by the next successful status/result update.
    })
  }, heartbeatRetryMs)
}

const fetchStatus = async () => {
  try {
    const result: any = await request.get(`/face/session/${props.sessionId}/status`, { _skipErrorToast: true } as any)
    failureCount.value = Number(result.monitor_failure_count ?? result.failure_count ?? 0)
    maxFailures.value = Number(result.max_failures || 5)
    if (!result.registered) verifyHint.value = '当前账号尚未注册人脸档案'
    if (result.terminated) emit('terminated', result)
  } catch {
    verifyHint.value = '人脸校验服务暂不可用'
  }
}

defineExpose({ runVerify, stopCamera })

onMounted(async () => {
  await fetchStatus()
  await startCamera()
})

onBeforeUnmount(stopCamera)
</script>

<style scoped>
.face-guard {
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr);
  gap: 16px;
  align-items: center;
  padding: 16px;
  border: 1px solid rgba(37, 99, 235, 0.16);
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
}

.face-guard--monitor {
  grid-template-columns: 72px minmax(0, 1fr);
  width: 260px;
  height: 112px;
  box-sizing: border-box;
  gap: 10px;
  padding: 10px;
  overflow: hidden;
  box-shadow: none;
}

.face-guard__camera {
  position: relative;
  width: 160px;
  height: 160px;
  overflow: hidden;
  border: 3px solid #38bdf8;
  border-radius: 50%;
  background: #0f172a;
  box-shadow: 0 0 0 6px #eef6ff;
}

.face-guard--monitor .face-guard__camera {
  width: 72px;
  height: 72px;
  border-color: #10b981;
  box-shadow: 0 0 0 4px #ecfdf5;
}

.face-guard--monitor .face-guard__body {
  min-width: 0;
  overflow: hidden;
}

.face-guard--monitor .face-guard__title-row,
.face-guard--monitor .face-guard__meta,
.face-guard--monitor .face-guard__body p {
  max-width: 100%;
  overflow: hidden;
}

.face-guard--monitor .face-guard__title-row {
  flex-wrap: wrap;
  row-gap: 4px;
}

.face-guard--monitor .face-guard__meta span,
.face-guard--monitor .face-guard__body p {
  display: block;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.face-guard--monitor .face-guard__badge {
  flex-shrink: 0;
}

.face-guard--monitor .face-guard__body p {
  margin-top: 6px;
}

.face-guard__camera video,
.face-verify__circle video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transform: scaleX(-1);
}

.face-guard__canvas {
  display: none;
}

.face-guard__placeholder {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: rgba(255, 255, 255, 0.86);
  background: #111827;
}

.face-guard__title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.face-guard__title-row strong {
  color: #0f172a;
  font-size: 15px;
}

.face-guard__badge {
  padding: 3px 8px;
  border-radius: 999px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 11px;
  font-weight: 700;
}

.face-guard--passed .face-guard__badge {
  background: #ecfdf5;
  color: #059669;
}

.face-guard__body p {
  margin: 8px 0 0;
  color: #ef4444;
  font-size: 13px;
  line-height: 1.6;
}

.face-guard__meta {
  display: flex;
  margin-top: 8px;
  color: #64748b;
  font-size: 12px;
}

.face-guard__actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.face-verify {
  display: grid;
  justify-items: center;
  gap: 12px;
  padding: 18px 20px 22px;
  text-align: center;
}

.face-verify__circle {
  position: relative;
  width: 220px;
  height: 220px;
  overflow: hidden;
  border: 4px solid #38bdf8;
  border-radius: 50%;
  background: #0f172a;
}

.face-verify__mask {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #ffffff;
  background: rgba(15, 23, 42, 0.72);
}

.face-verify strong {
  color: #0f172a;
  font-size: 18px;
}

.face-verify p {
  margin: 0;
  color: #475569;
  font-size: 14px;
  line-height: 1.6;
}

.face-verify__feedback {
  display: grid;
  gap: 8px;
  width: min(100%, 260px);
  padding: 10px 12px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
  color: #1e3a8a;
  font-size: 13px;
  line-height: 1.4;
}

.face-verify__feedback--matching {
  border-color: #bfdbfe;
  background: #eff6ff;
}

.face-verify__feedback--warning {
  border-color: #fde68a;
  background: #fffbeb;
  color: #92400e;
}

.face-verify__feedback--success {
  border-color: #bbf7d0;
  background: #f0fdf4;
  color: #047857;
}

.face-verify__feedback-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 18px;
}

.face-verify__progress {
  width: 100%;
  height: 5px;
  overflow: hidden;
  border-radius: 999px;
  background: #e2e8f0;
}

.face-verify__progress span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #2563eb;
  transition: width 0.2s ease;
}

.face-verify__feedback--warning .face-verify__progress span {
  background: #f59e0b;
}

.face-verify__feedback--success .face-verify__progress span {
  background: #10b981;
}

.face-verify__feedback-row--muted {
  justify-content: space-between;
  color: #64748b;
  font-size: 12px;
}

.face-verify__dot {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #93c5fd;
}

.face-verify__dot.is-active {
  background: #2563eb;
  box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.35);
  animation: verify-pulse 1s ease-out infinite;
}

@keyframes verify-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.35);
  }
  100% {
    box-shadow: 0 0 0 8px rgba(37, 99, 235, 0);
  }
}

@media (max-width: 720px) {
  .face-guard {
    grid-template-columns: 116px minmax(0, 1fr);
  }

  .face-guard__camera {
    width: 116px;
    height: 116px;
  }

  .face-verify__circle {
    width: 190px;
    height: 190px;
  }
}
</style>
