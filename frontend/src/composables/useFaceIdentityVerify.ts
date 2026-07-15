import { computed, onUnmounted, ref } from 'vue'
import request from '../utils/request'
import { captureSelfieFrame } from '../utils/selfieFrameCapture'

export interface FaceVerifyResult {
  passed?: boolean
  registered?: boolean
  reason?: string
  similarity?: number
  terminated?: boolean
  failure_count?: number
  max_failures?: number
  monitor_failure_count?: number
}

const localizeFaceMessage = (value: unknown, fallback = '人脸验证失败，请调整后继续') => {
  const text = String(value || '').trim()
  const lowered = text.toLowerCase()
  if (!text || /^\?+$/.test(text)) return fallback
  if (lowered.includes('no registered face profile')) return '当前账号尚未注册人脸档案'
  if (lowered.includes('no face detected') || lowered.includes('no face')) return '未检测到人脸，请正对摄像头'
  if (lowered.includes('multiple faces') || lowered.includes('multiple')) return '检测到多人入镜，请保持单人验证'
  if (lowered.includes('face mismatch') || lowered.includes('mismatch')) return '当前人脸与注册学员不一致'
  if (lowered.includes('invalid camera frame')) return '摄像头画面无效，请继续调整'
  if (lowered.includes('invalid image')) return '画面格式无效，请继续调整'
  if (lowered.includes('embedding extraction')) return '人脸特征提取失败，请调整光线后继续'
  if (lowered.includes('blur')) return '画面略有模糊，请调整摄像头或保持稳定'
  if (lowered.includes('insightface') || lowered.includes('model init') || lowered.includes('face engine unavailable')) {
    return '人脸识别模型暂不可用，请检查后端模型服务'
  }
  if (lowered === 'passed' || lowered.includes('人脸验证通过')) return '人脸验证通过'
  return text
}

const formatSimilarity = (value: unknown) => {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return ''
  if (numeric <= 0) return '未匹配'
  return `${Math.round(numeric * 100)}%`
}

export function useFaceIdentityVerify() {
  const registered = ref(false)
  const verified = ref(false)
  const verifying = ref(false)
  const message = ref('等待人脸身份核验')
  const similarityText = ref('')
  const similarityScore = ref(0)
  const passStreak = ref(0)
  const attemptCount = ref(0)
  const failureCount = ref(0)
  const maxFailures = ref(5)
  const terminated = ref(false)

  let verifyTimer: number | null = null
  let heartbeatTimer: number | null = null
  let verifyInFlight = false
  let heartbeatInFlight = false
  let boundVideo: HTMLVideoElement | null = null
  let boundCanvas: HTMLCanvasElement | null = null
  let activeSessionId: number | null = null
  let activeMode: 'me' | 'video-session' = 'me'
  let canVerifyFrame: (() => boolean) | null = null

  const statusText = computed(() => {
    if (terminated.value) return '人脸异常次数已达上限'
    if (verified.value) return '本人身份核验通过'
    if (!registered.value) return '当前账号尚未注册人脸档案'
    if (verifying.value) return message.value || '正在比对本人身份'
    return message.value
  })

  const canProceed = computed(() => verified.value)

  function stopVerifyLoop() {
    if (verifyTimer != null) {
      window.clearInterval(verifyTimer)
      verifyTimer = null
    }
    verifyInFlight = false
  }

  function stopHeartbeat() {
    if (heartbeatTimer != null) {
      window.clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
    heartbeatInFlight = false
  }

  function stop() {
    stopVerifyLoop()
    stopHeartbeat()
    verifying.value = false
    boundVideo = null
    boundCanvas = null
    activeSessionId = null
    canVerifyFrame = null
  }

  function captureFrame(size = 640, jpegQuality = 0.9) {
    const video = boundVideo
    const canvas = boundCanvas
    if (!video || !canvas) return null
    return captureSelfieFrame(video, canvas, { size, jpegQuality, mode: 'preview' })
  }

  function buildPayload() {
    const frame = captureFrame()
    if (!frame) return null
    const livenessVerified = canVerifyFrame ? canVerifyFrame() : false
    return {
      frame,
      quality_metrics: {
        liveness_verified: livenessVerified,
        single_face_verified: livenessVerified,
      },
    }
  }

  function resolveEndpoint(endpoint: 'verify' | 'heartbeat') {
    if (activeMode === 'video-session' && activeSessionId) {
      return `/face/video-session/${activeSessionId}/${endpoint}`
    }
    if (endpoint === 'verify') return '/face/me/verify-frame'
    return null
  }

  function applyResult(result: FaceVerifyResult, endpoint: 'verify' | 'heartbeat') {
    if (result?.registered === false) registered.value = false
    if (typeof result?.registered === 'boolean') registered.value = result.registered
    failureCount.value = Number(
      result?.monitor_failure_count ?? result?.failure_count ?? failureCount.value,
    )
    maxFailures.value = Number(result?.max_failures ?? maxFailures.value)
    similarityText.value = formatSimilarity(result?.similarity)
    similarityScore.value = Number(result?.similarity ?? 0)

    if (result?.terminated) {
      verified.value = false
      passStreak.value = 0
      terminated.value = true
      failureCount.value = maxFailures.value
      message.value = localizeFaceMessage(result?.reason, '人脸验证异常，训练已中断')
      stopVerifyLoop()
      stopHeartbeat()
      verifying.value = false
      return
    }

    if (result?.passed) {
      verified.value = true
      message.value = localizeFaceMessage(result?.reason, '人脸验证通过')
      if (endpoint === 'verify') {
        stopVerifyLoop()
        verifying.value = false
        if (activeMode === 'video-session' && activeSessionId) startHeartbeat()
      }
      return
    }

    if (endpoint === 'verify') {
      passStreak.value = 0
      const similarityLabel = formatSimilarity(result?.similarity)
      const reason = localizeFaceMessage(result?.reason, '本帧未通过，正在继续匹配')
      message.value = similarityLabel ? `${similarityLabel} · ${reason}` : reason
    }
  }

  async function postFrame(endpoint: 'verify' | 'heartbeat') {
    const url = resolveEndpoint(endpoint)
    if (!url) return
    if (endpoint === 'verify' && verifyInFlight) return
    if (endpoint === 'heartbeat' && heartbeatInFlight) return
    if (endpoint === 'verify' && canVerifyFrame && !canVerifyFrame()) return
    if (endpoint === 'verify') verifyInFlight = true
    if (endpoint === 'heartbeat') heartbeatInFlight = true

    const payload = buildPayload()
    if (!payload) {
      if (endpoint === 'verify') message.value = '摄像头画面尚未就绪，请稍候'
      if (endpoint === 'verify') verifyInFlight = false
      if (endpoint === 'heartbeat') heartbeatInFlight = false
      return
    }

    try {
      const result = await request.post(url, payload, { _skipErrorToast: true } as any)
      if (endpoint === 'verify') attemptCount.value += 1
      applyResult(result, endpoint)
    } catch (error: any) {
      if (endpoint === 'verify') attemptCount.value += 1
      message.value = localizeFaceMessage(error?.response?.data?.detail, '人脸校验服务暂不可用')
    } finally {
      if (endpoint === 'verify') verifyInFlight = false
      if (endpoint === 'heartbeat') heartbeatInFlight = false
    }
  }

  async function fetchProfileStatus() {
    try {
      const result: any = await request.get('/face/me/profile', { _skipErrorToast: true } as any)
      registered.value = Boolean(result?.registered)
      if (!registered.value) message.value = '当前账号尚未注册人脸档案'
      return registered.value
    } catch {
      registered.value = false
      message.value = '人脸档案服务暂不可用'
      return false
    }
  }

  async function fetchVideoSessionStatus(sessionId: number) {
    try {
      const result: any = await request.get(`/face/video-session/${sessionId}/status`, { _skipErrorToast: true } as any)
      registered.value = Boolean(result?.registered)
      failureCount.value = Number(result?.monitor_failure_count ?? result?.failure_count ?? 0)
      maxFailures.value = Number(result?.max_failures ?? 5)
      terminated.value = Boolean(result?.terminated)
      if (!registered.value) message.value = '当前账号尚未注册人脸档案'
      if (result?.terminated) message.value = localizeFaceMessage(result?.reason, '人脸验证异常')
      return result
    } catch {
      message.value = '人脸校验服务暂不可用'
      return null
    }
  }

  async function startVerify(options: {
    video: HTMLVideoElement
    canvas: HTMLCanvasElement
    mode?: 'me' | 'video-session'
    sessionId?: number | null
    retryMs?: number
    requireRegistered?: boolean
    canVerifyFrame?: () => boolean
  }) {
    const {
      video,
      canvas,
      mode = 'me',
      sessionId = null,
      retryMs = 1200,
      requireRegistered = true,
      canVerifyFrame: verifyGate,
    } = options

    stopVerifyLoop()
    boundVideo = video
    boundCanvas = canvas
    activeMode = mode
    activeSessionId = sessionId
    canVerifyFrame = verifyGate ?? null
    verified.value = false
    terminated.value = false
    verifying.value = true
    attemptCount.value = 0
    passStreak.value = 0
    similarityScore.value = 0
    similarityText.value = ''
    message.value = '正在启动人脸识别模型'

    if (mode === 'video-session' && sessionId) {
      await fetchVideoSessionStatus(sessionId)
    } else {
      await fetchProfileStatus()
    }

    if (requireRegistered && !registered.value) {
      verifying.value = false
      return false
    }

    await postFrame('verify')
    stopVerifyLoop()
    verifyTimer = window.setInterval(() => {
      if (!verifying.value || verified.value || terminated.value) return
      void postFrame('verify')
    }, retryMs)
    return true
  }

  function startHeartbeat(retryMs = 1500) {
    stopHeartbeat()
    if (activeMode !== 'video-session' || !activeSessionId || !verified.value) return
    heartbeatTimer = window.setInterval(() => {
      if (!verified.value || terminated.value) return
      void postFrame('heartbeat')
    }, retryMs)
  }

  function resetVerification() {
    verified.value = false
    terminated.value = false
    attemptCount.value = 0
    passStreak.value = 0
    similarityScore.value = 0
    similarityText.value = ''
    message.value = '等待人脸身份核验'
  }

  function beginVideoSessionMonitoring(
    sessionId: number,
    video: HTMLVideoElement,
    canvas: HTMLCanvasElement,
  ) {
    stopVerifyLoop()
    boundVideo = video
    boundCanvas = canvas
    activeMode = 'video-session'
    activeSessionId = sessionId
    verifying.value = false
    terminated.value = false
    startHeartbeat()
  }

  onUnmounted(stop)

  return {
    registered,
    verified,
    verifying,
    terminated,
    message,
    statusText,
    similarityText,
    similarityScore,
    passStreak,
    attemptCount,
    failureCount,
    maxFailures,
    canProceed,
    fetchProfileStatus,
    fetchVideoSessionStatus,
    startVerify,
    startHeartbeat,
    beginVideoSessionMonitoring,
    resetVerification,
    stop,
  }
}
