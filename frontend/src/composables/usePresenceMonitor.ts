import { computed, onUnmounted, ref } from 'vue'
import { loadVisionTasksModule } from '../utils/mediapipeVision'

type PresenceStatus = 'idle' | 'loading' | 'checking' | 'ready' | 'warn' | 'unsupported' | 'error'

interface BoundingBoxLike {
  originX: number
  originY: number
  width: number
  height: number
}

interface DetectionLike {
  boundingBox?: BoundingBoxLike
}

interface FaceDetectorResult {
  detections?: DetectionLike[]
}

interface FaceDetectorLike {
  detectForVideo(video: HTMLVideoElement, timestampMs: number): FaceDetectorResult
  close?: () => void
}

const REMOTE_FACE_MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite'

const CHECK_INTERVAL_MS = 700
const REQUIRED_SINGLE_FACE_STREAK = 3
const REQUIRED_LIVE_MOTION = 0.008
const MIN_FACE_AREA_RATIO = 0.025

function normalizeBox(box: BoundingBoxLike, videoWidth: number, videoHeight: number) {
  const width = Math.max(videoWidth, 1)
  const height = Math.max(videoHeight, 1)
  const looksNormalized =
    box.originX <= 1
    && box.originY <= 1
    && box.width <= 1
    && box.height <= 1

  if (looksNormalized) {
    return {
      originX: box.originX,
      originY: box.originY,
      width: box.width,
      height: box.height,
    }
  }

  return {
    originX: box.originX / width,
    originY: box.originY / height,
    width: box.width / width,
    height: box.height / height,
  }
}

function detectionCenter(box: BoundingBoxLike) {
  return {
    x: box.originX + box.width / 2,
    y: box.originY + box.height / 2,
  }
}

function faceAreaRatio(box: BoundingBoxLike) {
  return box.width * box.height
}

function faceCenterOffset(box: BoundingBoxLike) {
  const center = detectionCenter(box)
  return Math.hypot(center.x - 0.5, center.y - 0.5)
}

function resolvePrimaryFace(detections: DetectionLike[], videoWidth: number, videoHeight: number) {
  const normalized = detections
    .map((detection) => {
      if (!detection.boundingBox) return null
      return {
        ...detection,
        boundingBox: normalizeBox(detection.boundingBox, videoWidth, videoHeight),
      }
    })
    .filter((detection): detection is DetectionLike => Boolean(detection?.boundingBox))

  const valid = normalized.filter((detection) => {
    const box = detection.boundingBox!
    return faceAreaRatio(box) >= MIN_FACE_AREA_RATIO
  })

  if (!valid.length) {
    return { count: 0, primary: null as DetectionLike | null }
  }

  const sorted = [...valid].sort(
    (left, right) => {
      const areaDifference = faceAreaRatio(right.boundingBox!) - faceAreaRatio(left.boundingBox!)
      if (areaDifference) return areaDifference
      return faceCenterOffset(left.boundingBox!) - faceCenterOffset(right.boundingBox!)
    },
  )
  // The displayed camera is already clipped to a circle.  Detection operates
  // on the untransformed source video, so using source-frame coordinates to
  // enforce the circle would incorrectly require the face to be centred.
  // Always verify the largest visible face instead.
  return { count: 1, primary: sorted[0] }
}

export function usePresenceMonitor() {
  const status = ref<PresenceStatus>('idle')
  const message = ref('身份校验未启动')
  const faceCount = ref(0)
  const singleFaceReady = ref(false)
  const liveReady = ref(false)
  const lastMotion = ref(0)
  const source = ref<string | null>(null)

  let faceDetector: FaceDetectorLike | null = null
  let boundVideo: HTMLVideoElement | null = null
  let timerId: ReturnType<typeof setTimeout> | null = null
  let detectorInitPromise: Promise<boolean> | null = null
  let loadingTimeoutId: ReturnType<typeof setTimeout> | null = null
  let singleFaceStreak = 0
  let previousCenter: { x: number; y: number } | null = null
  let lastDetectionAt = 0

  const supported = computed(() => status.value !== 'unsupported')
  const verified = computed(() => singleFaceReady.value && liveReady.value)

  function reset(reason = '等待身份校验') {
    faceCount.value = 0
    singleFaceReady.value = false
    liveReady.value = false
    lastMotion.value = 0
    singleFaceStreak = 0
    previousCenter = null
    if (status.value === 'unsupported') {
      message.value = '人脸检测模型不可用，请检查网络或刷新页面'
      return
    }
    status.value = faceDetector ? 'checking' : 'loading'
    message.value = faceDetector ? reason : '正在加载人脸检测模型...'
  }

  function stopLoop() {
    if (timerId) {
      clearTimeout(timerId)
      timerId = null
    }
  }

  function queueNextCheck() {
    stopLoop()
    timerId = setTimeout(() => {
      void detectFrame()
    }, CHECK_INTERVAL_MS)
  }

  async function initFaceDetector(): Promise<boolean> {
    status.value = 'loading'
    message.value = '正在加载人脸检测模型...'
    if (loadingTimeoutId) clearTimeout(loadingTimeoutId)
    loadingTimeoutId = setTimeout(() => {
      if (!faceDetector && status.value === 'loading') {
        status.value = 'unsupported'
        message.value = '本地模型加载超时，已切换后端识别'
      }
    }, 15000)

    try {
      const loaded = await loadVisionTasksModule()
      const { FilesetResolver, FaceDetector } = loaded.visionModule
      if (!FilesetResolver || !FaceDetector) {
        status.value = 'unsupported'
        message.value = '人脸检测资源不可用'
        return false
      }

      const resolver = await FilesetResolver.forVisionTasks(loaded.wasmUrl)
      faceDetector = await FaceDetector.createFromOptions(resolver, {
        baseOptions: {
          modelAssetPath: REMOTE_FACE_MODEL_URL,
          delegate: 'CPU',
        },
        runningMode: 'VIDEO',
        minDetectionConfidence: 0.4,
        minSuppressionThreshold: 0.3,
      })

      source.value = loaded.sourceLabel
      status.value = 'checking'
      message.value = '人脸检测已就绪，请保持面部在圆形区域内'
      if (loadingTimeoutId) {
        clearTimeout(loadingTimeoutId)
        loadingTimeoutId = null
      }
      return true
    } catch (error) {
      faceDetector = null
      source.value = null
      status.value = 'unsupported'
      message.value = '人脸检测模型加载失败，已切换后端识别'
      if (loadingTimeoutId) {
        clearTimeout(loadingTimeoutId)
        loadingTimeoutId = null
      }
      console.warn('Presence monitor init failed', error)
      return false
    }
  }

  async function ensureFaceDetector() {
    if (faceDetector) return true
    if (!detectorInitPromise) {
      detectorInitPromise = initFaceDetector().finally(() => {
        detectorInitPromise = null
      })
    }
    return detectorInitPromise
  }

  async function detectFrame() {
    if (!boundVideo) {
      stopLoop()
      return
    }
    if (boundVideo.readyState < 2 || boundVideo.videoWidth === 0 || boundVideo.videoHeight === 0) {
      queueNextCheck()
      return
    }

    const ok = await ensureFaceDetector()
    if (!ok || !faceDetector) {
      if (status.value !== 'unsupported') queueNextCheck()
      return
    }

    const now = performance.now()
    if (now - lastDetectionAt < CHECK_INTERVAL_MS - 40) {
      queueNextCheck()
      return
    }
    lastDetectionAt = now

    try {
      const result = faceDetector.detectForVideo(boundVideo, now)
      const videoWidth = boundVideo.videoWidth
      const videoHeight = boundVideo.videoHeight
      const { count, primary } = resolvePrimaryFace(result.detections || [], videoWidth, videoHeight)
      faceCount.value = count

      if (count !== 1 || !primary?.boundingBox) {
        singleFaceStreak = 0
        singleFaceReady.value = false
        liveReady.value = false
        previousCenter = null
        status.value = 'warn'
        message.value = count === 0
          ? '请将面部保持在圆形区域内'
          : '请将面部保持在圆形区域内'
        queueNextCheck()
        return
      }

      singleFaceStreak += 1
      if (singleFaceStreak >= REQUIRED_SINGLE_FACE_STREAK) {
        singleFaceReady.value = true
      }

      const box = primary.boundingBox
      const center = detectionCenter(box)

      if (previousCenter) {
        const motion = Math.hypot(center.x - previousCenter.x, center.y - previousCenter.y)
        lastMotion.value = motion
        if (motion >= REQUIRED_LIVE_MOTION) {
          liveReady.value = true
        }
      }
      previousCenter = center

      status.value = verified.value ? 'ready' : 'checking'
      message.value = verified.value
        ? '人脸入镜与活体校验通过'
        : singleFaceReady.value
          ? '请轻微转头或眨眼'
          : '正在确认人脸入镜'
    } catch (error) {
      status.value = 'error'
      message.value = '身份校验运行失败，请稍后重试'
      console.warn('Presence monitor failed', error)
    }

    queueNextCheck()
  }

  async function attachVideo(video: HTMLVideoElement | null) {
    if (!video) {
      stopLoop()
      boundVideo = null
      return
    }
    if (boundVideo === video && faceDetector && timerId !== null) {
      return
    }
    boundVideo = video
    stopLoop()
    reset('正在启动身份校验')
    if (status.value === 'unsupported') return
    await detectFrame()
  }

  async function restart() {
    if (!boundVideo) return
    reset('正在重新校验身份')
    await detectFrame()
  }

  function stop() {
    stopLoop()
    if (loadingTimeoutId) {
      clearTimeout(loadingTimeoutId)
      loadingTimeoutId = null
    }
    boundVideo = null
    if (faceDetector?.close) faceDetector.close()
    faceDetector = null
    detectorInitPromise = null
    source.value = null
    status.value = 'idle'
    message.value = '身份校验已停止'
    faceCount.value = 0
    singleFaceReady.value = false
    liveReady.value = false
    lastMotion.value = 0
    singleFaceStreak = 0
    previousCenter = null
    lastDetectionAt = 0
  }

  onUnmounted(stop)

  return {
    status,
    message,
    faceCount,
    supported,
    singleFaceReady,
    liveReady,
    verified,
    lastMotion,
    source,
    attachVideo,
    restart,
    stop,
  }
}
