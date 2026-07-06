import { computed, onUnmounted, ref } from 'vue'

export type GestureType =
  | 'salute'
  | 'show_id'
  | 'raise_hand'
  | 'standard_stance'
  | 'hands_forward'
  | 'hand_on_chest'
  | 'stop_signal'
  | 'point_front'

export interface GestureRuleConfig {
  min_confidence?: number
  hold_frames?: number
  tolerance?: 'strict' | 'standard' | 'relaxed'
}

type DetectorStatus = 'idle' | 'loading' | 'ready' | 'matched' | 'unmatched' | 'unsupported' | 'error'

interface LandmarkPoint {
  x: number
  y: number
  z?: number
  visibility?: number
}

interface PoseDetectionResult {
  landmarks?: LandmarkPoint[][]
}

interface PoseLandmarkerLike {
  detectForVideo(video: HTMLVideoElement, timestampMs: number): PoseDetectionResult
  close?: () => void
}

const REMOTE_TASKS_VISION_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22'
const REMOTE_TASKS_VISION_WASM_URL = `${REMOTE_TASKS_VISION_URL}/wasm`
const REMOTE_POSE_MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task'

const LOCAL_TASKS_VISION_URL = import.meta.env.VITE_MEDIAPIPE_TASKS_VISION_URL || '/mediapipe/tasks-vision/index.js'
const LOCAL_TASKS_VISION_WASM_URL = import.meta.env.VITE_MEDIAPIPE_TASKS_VISION_WASM_URL || '/mediapipe/tasks-vision/wasm'
const LOCAL_POSE_MODEL_URL = import.meta.env.VITE_MEDIAPIPE_POSE_MODEL_URL || '/mediapipe/models/pose_landmarker_lite.task'

const DEFAULT_REQUIRED_STREAK = 5
const DETECTION_INTERVAL_MS = 120

const GESTURE_LABELS: Record<GestureType, string> = {
  salute: '标准敬礼',
  show_id: '出示证件',
  raise_hand: '举手示意',
  standard_stance: '标准站姿',
  hands_forward: '双手前伸',
  hand_on_chest: '扶胸示意',
  stop_signal: '停止手势',
  point_front: '前方指引',
}

const loadRemoteModule = async (url: string) => {
  const dynamicImporter = new Function('u', 'return import(/* @vite-ignore */ u)') as (u: string) => Promise<any>
  return dynamicImporter(url)
}

const pointVisible = (point?: LandmarkPoint) => Boolean(point && (point.visibility ?? 1) > 0.35)
const dist = (a: LandmarkPoint, b: LandmarkPoint) => Math.hypot(a.x - b.x, a.y - b.y)

function getToleranceScale(tolerance?: string) {
  if (tolerance === 'strict') return 0.84
  if (tolerance === 'relaxed') return 1.18
  return 1
}

async function loadVisionModule() {
  const candidates = [
    {
      moduleUrl: LOCAL_TASKS_VISION_URL,
      wasmUrl: LOCAL_TASKS_VISION_WASM_URL,
      modelUrl: LOCAL_POSE_MODEL_URL,
      sourceLabel: 'local',
    },
    {
      moduleUrl: REMOTE_TASKS_VISION_URL,
      wasmUrl: REMOTE_TASKS_VISION_WASM_URL,
      modelUrl: REMOTE_POSE_MODEL_URL,
      sourceLabel: 'remote',
    },
  ] as const

  const errors: unknown[] = []
  for (const candidate of candidates) {
    try {
      const visionModule = await loadRemoteModule(candidate.moduleUrl)
      return { ...candidate, visionModule }
    } catch (error) {
      errors.push(error)
    }
  }
  throw errors[errors.length - 1] || new Error('Unable to load mediapipe vision module')
}

function evaluateGesture(gesture: GestureType, landmarks: LandmarkPoint[], ruleConfig: GestureRuleConfig) {
  const toleranceScale = getToleranceScale(ruleConfig.tolerance)
  const leftShoulder = landmarks[11]
  const rightShoulder = landmarks[12]
  const leftElbow = landmarks[13]
  const rightElbow = landmarks[14]
  const leftWrist = landmarks[15]
  const rightWrist = landmarks[16]
  const leftHip = landmarks[23]
  const rightHip = landmarks[24]
  const leftMouth = landmarks[9]
  const rightEye = landmarks[5]

  if (!pointVisible(leftShoulder) || !pointVisible(rightShoulder)) {
    return { matched: false, confidence: 0, reason: '请保持上半身完整进入画面' }
  }

  const shoulderWidth = dist(leftShoulder, rightShoulder) || 0.2
  const shoulderMidX = (leftShoulder.x + rightShoulder.x) / 2
  const shoulderMidY = (leftShoulder.y + rightShoulder.y) / 2
  const hipMidY = pointVisible(leftHip) && pointVisible(rightHip) ? (leftHip.y + rightHip.y) / 2 : shoulderMidY + 0.28

  switch (gesture) {
    case 'raise_hand': {
      if (!pointVisible(leftWrist) && !pointVisible(rightWrist)) {
        return { matched: false, confidence: 0, reason: '请让至少一只手保持在镜头内' }
      }
      const highestWrist = Math.min(leftWrist?.y ?? 1, rightWrist?.y ?? 1)
      const matched = highestWrist < shoulderMidY - (0.06 * toleranceScale)
      return {
        matched,
        confidence: matched ? 0.9 : 0.35,
        reason: matched ? '已检测到举手动作' : '请将任意一只手举过肩线',
      }
    }
    case 'salute': {
      if (!pointVisible(rightWrist) || !pointVisible(rightElbow) || !pointVisible(rightEye)) {
        return { matched: false, confidence: 0, reason: '请保持右手与头部都在画面内' }
      }
      const wristToEye = dist(rightWrist, rightEye)
      const elbowRaised = rightElbow.y < rightShoulder.y + (0.12 / toleranceScale)
      const wristAboveShoulder = rightWrist.y < rightShoulder.y + (0.08 / toleranceScale)
      const matched = wristToEye < (0.16 * toleranceScale) && elbowRaised && wristAboveShoulder
      return {
        matched,
        confidence: matched ? 0.92 : 0.4,
        reason: matched ? '已检测到敬礼动作' : '请将右手抬至眉心附近形成敬礼姿势',
      }
    }
    case 'standard_stance': {
      if (!pointVisible(leftHip) || !pointVisible(rightHip) || !pointVisible(leftWrist) || !pointVisible(rightWrist)) {
        return { matched: false, confidence: 0, reason: '请保持上半身和双手清晰可见' }
      }
      const shouldersLevel = Math.abs(leftShoulder.y - rightShoulder.y) < (0.06 * toleranceScale)
      const hipsLevel = Math.abs(leftHip.y - rightHip.y) < (0.08 * toleranceScale)
      const wristsLower = leftWrist.y > leftShoulder.y && rightWrist.y > rightShoulder.y
      const centered = Math.abs(shoulderMidX - 0.5) < (0.22 * toleranceScale)
      const matched = shouldersLevel && hipsLevel && wristsLower && centered
      return {
        matched,
        confidence: matched ? 0.88 : 0.45,
        reason: matched ? '站姿基本稳定' : '请正对镜头站稳，双肩放平，双手自然下垂',
      }
    }
    case 'hands_forward':
    case 'show_id': {
      if (!pointVisible(leftWrist) || !pointVisible(rightWrist) || !pointVisible(leftElbow) || !pointVisible(rightElbow)) {
        return { matched: false, confidence: 0, reason: '请让双手完整保持在画面内' }
      }
      const wristGap = Math.abs(leftWrist.x - rightWrist.x)
      const avgWristY = (leftWrist.y + rightWrist.y) / 2
      const nearBodyCenter = Math.abs(((leftWrist.x + rightWrist.x) / 2) - shoulderMidX) < shoulderWidth * 0.55 * toleranceScale
      const elbowsOpen = leftElbow.y < hipMidY + (0.06 * toleranceScale) && rightElbow.y < hipMidY + (0.06 * toleranceScale)
      const handsRaised = avgWristY < hipMidY + (0.08 * toleranceScale) && avgWristY > shoulderMidY - (0.06 * toleranceScale)
      const matched = wristGap < shoulderWidth * 1.2 * toleranceScale && nearBodyCenter && elbowsOpen && handsRaised
      return {
        matched,
        confidence: matched ? 0.86 : 0.42,
        reason: matched
          ? gesture === 'show_id'
            ? '已检测到出示证件动作'
            : '已检测到双手前伸动作'
          : gesture === 'show_id'
            ? '请将双手抬至胸前中部，保持出示证件姿势'
            : '请将双手前伸并保持在身体中线附近',
      }
    }
    case 'hand_on_chest': {
      if (!pointVisible(rightWrist) || !pointVisible(leftShoulder) || !pointVisible(rightShoulder)) {
        return { matched: false, confidence: 0, reason: '请保持右手和胸前区域都在画面内' }
      }
      const chestCenter = {
        x: shoulderMidX,
        y: shoulderMidY + (hipMidY - shoulderMidY) * 0.28,
      }
      const wristToChest = dist(rightWrist, chestCenter)
      const matched = wristToChest < 0.14 * toleranceScale
      return {
        matched,
        confidence: matched ? 0.87 : 0.4,
        reason: matched ? '已检测到扶胸示意动作' : '请将右手放至胸前完成扶胸示意',
      }
    }
    case 'stop_signal': {
      if (!pointVisible(rightWrist) || !pointVisible(rightElbow)) {
        return { matched: false, confidence: 0, reason: '请保持右手完整出现在镜头内' }
      }
      const wristRaised = rightWrist.y < shoulderMidY + (0.04 * toleranceScale)
      const armOpen = Math.abs(rightWrist.x - rightShoulder.x) > shoulderWidth * 0.18
      const matched = wristRaised && armOpen
      return {
        matched,
        confidence: matched ? 0.84 : 0.38,
        reason: matched ? '已检测到停止手势' : '请抬起右手，做出停止示意',
      }
    }
    case 'point_front': {
      if (!pointVisible(rightWrist) || !pointVisible(rightElbow)) {
        return { matched: false, confidence: 0, reason: '请保持右手完整出现在镜头内' }
      }
      const wristForward = rightWrist.x < rightShoulder.x - (0.02 / toleranceScale)
      const wristLevel = rightWrist.y < hipMidY && rightWrist.y > shoulderMidY - (0.04 * toleranceScale)
      const matched = wristForward && wristLevel
      return {
        matched,
        confidence: matched ? 0.83 : 0.36,
        reason: matched ? '已检测到前方指引动作' : '请伸出右手朝前方做指引动作',
      }
    }
    default:
      return { matched: false, confidence: 0, reason: '未识别的动作类型' }
  }
}

export function useGestureDetector() {
  const status = ref<DetectorStatus>('idle')
  const targetGesture = ref<GestureType | null>(null)
  const matched = ref(false)
  const confidence = ref(0)
  const message = ref('未启用动作识别')
  const streak = ref(0)
  const source = ref<'local' | 'remote' | null>(null)
  const ruleConfig = ref<GestureRuleConfig>({})

  let poseLandmarker: PoseLandmarkerLike | null = null
  let rafId: number | null = null
  let boundVideo: HTMLVideoElement | null = null
  let lastDetectionAt = 0

  const targetLabel = computed(() => (targetGesture.value ? GESTURE_LABELS[targetGesture.value] : ''))
  const requiredStreak = computed(() => Math.max(Number(ruleConfig.value.hold_frames || DEFAULT_REQUIRED_STREAK), 1))
  const minConfidence = computed(() => Math.max(Math.min(Number(ruleConfig.value.min_confidence || 0), 1), 0))

  async function ensurePoseLandmarker() {
    if (poseLandmarker || status.value === 'loading') return
    status.value = 'loading'
    message.value = '正在加载动作识别模型...'

    try {
      const loaded = await loadVisionModule()
      const { FilesetResolver, PoseLandmarker } = loaded.visionModule
      if (!FilesetResolver || !PoseLandmarker) {
        status.value = 'unsupported'
        message.value = '动作识别资源不可用，已切换为人工确认补位'
        return
      }

      const resolver = await FilesetResolver.forVisionTasks(loaded.wasmUrl)
      poseLandmarker = await PoseLandmarker.createFromOptions(resolver, {
        baseOptions: { modelAssetPath: loaded.modelUrl },
        runningMode: 'VIDEO',
        numPoses: 1,
      })

      source.value = loaded.sourceLabel
      status.value = 'ready'
      message.value = loaded.sourceLabel === 'local'
        ? '动作识别已就绪'
        : '动作识别已就绪，当前使用在线模型'
    } catch (error) {
      poseLandmarker = null
      source.value = null
      status.value = 'unsupported'
      message.value = '动作识别资源不可用，已切换为人工确认补位'
      console.warn('Gesture detector init failed', error)
    }
  }

  function resetDetectionState(idleMessage = '等待动作识别') {
    matched.value = false
    confidence.value = 0
    streak.value = 0
    if (status.value !== 'unsupported' && status.value !== 'error') {
      status.value = targetGesture.value ? 'ready' : 'idle'
    }
    message.value = idleMessage
  }

  function stopLoop() {
    if (rafId != null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
  }

  function detectFrame() {
    if (!poseLandmarker || !boundVideo || !targetGesture.value) {
      stopLoop()
      return
    }
    if (boundVideo.readyState < 2 || boundVideo.videoWidth === 0 || boundVideo.videoHeight === 0) {
      rafId = requestAnimationFrame(detectFrame)
      return
    }

    const now = performance.now()
    if (now - lastDetectionAt < DETECTION_INTERVAL_MS) {
      rafId = requestAnimationFrame(detectFrame)
      return
    }
    lastDetectionAt = now

    try {
      const result = poseLandmarker.detectForVideo(boundVideo, now)
      const landmarks = result.landmarks?.[0]

      if (!landmarks) {
        streak.value = 0
        matched.value = false
        confidence.value = 0
        status.value = 'unmatched'
        message.value = '未检测到人体关键点，请调整站位'
      } else {
        const evaluation = evaluateGesture(targetGesture.value, landmarks, ruleConfig.value)
        confidence.value = evaluation.confidence

        const confidencePassed = evaluation.confidence >= minConfidence.value
        if (evaluation.matched && confidencePassed) {
          streak.value += 1
          if (streak.value >= requiredStreak.value) {
            matched.value = true
            status.value = 'matched'
            message.value = `${targetLabel.value}识别通过`
          } else {
            matched.value = false
            status.value = 'ready'
            message.value = `正在确认${targetLabel.value}...`
          }
        } else {
          streak.value = 0
          matched.value = false
          status.value = 'unmatched'
          message.value = evaluation.matched && !confidencePassed
            ? `动作已接近标准，但置信度不足（需 ≥ ${(minConfidence.value * 100).toFixed(0)}%）`
            : evaluation.reason
        }
      }
    } catch (error) {
      matched.value = false
      confidence.value = 0
      streak.value = 0
      status.value = 'error'
      message.value = '动作识别运行异常，可继续按标准动作手动确认'
      console.warn('Gesture detector runtime failed', error)
    }

    rafId = requestAnimationFrame(detectFrame)
  }

  async function attachVideo(video: HTMLVideoElement | null) {
    boundVideo = video
    if (!video) {
      stopLoop()
      return
    }

    if (targetGesture.value) {
      await ensurePoseLandmarker()
      if (status.value === 'unsupported') return
      stopLoop()
      rafId = requestAnimationFrame(detectFrame)
    } else {
      resetDetectionState()
    }
  }

  async function setTargetGesture(gesture: string | null | undefined, nextRuleConfig?: GestureRuleConfig | null) {
    targetGesture.value = (gesture as GestureType | null) || null
    ruleConfig.value = nextRuleConfig || {}
    stopLoop()

    if (!gesture) {
      resetDetectionState('当前节点无需动作识别')
      return
    }

    resetDetectionState(`请完成${GESTURE_LABELS[gesture as GestureType]}`)
    if (boundVideo && !poseLandmarker) {
      await ensurePoseLandmarker()
    }
    if (boundVideo && poseLandmarker && status.value !== 'unsupported') {
      rafId = requestAnimationFrame(detectFrame)
    }
  }

  async function restart() {
    resetDetectionState(targetGesture.value ? `请完成${targetLabel.value}` : '等待动作识别')
    if (boundVideo) {
      await attachVideo(boundVideo)
    }
  }

  function stop() {
    stopLoop()
    boundVideo = null
    if (poseLandmarker?.close) poseLandmarker.close()
    poseLandmarker = null
    source.value = null
    status.value = 'idle'
    matched.value = false
    confidence.value = 0
    streak.value = 0
    targetGesture.value = null
    ruleConfig.value = {}
    message.value = '动作识别已停止'
  }

  onUnmounted(stop)

  return {
    status,
    matched,
    confidence,
    message,
    streak,
    targetGesture,
    targetLabel,
    source,
    ruleConfig,
    attachVideo,
    setTargetGesture,
    restart,
    stop,
  }
}
