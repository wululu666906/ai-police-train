import { computed, onUnmounted, ref } from 'vue'

type PresenceStatus = 'idle' | 'checking' | 'ready' | 'warn' | 'unsupported' | 'error'

interface FaceLike {
  boundingBox?: DOMRectReadOnly
}

interface FaceDetectorLike {
  detect(source: ImageBitmapSource): Promise<FaceLike[]>
}

declare global {
  interface Window {
    FaceDetector?: new (options?: Record<string, unknown>) => FaceDetectorLike
  }
}

const CHECK_INTERVAL_MS = 900
const REQUIRED_SINGLE_FACE_STREAK = 3
const REQUIRED_LIVE_MOTION = 0.012

export function usePresenceMonitor() {
  const status = ref<PresenceStatus>('idle')
  const message = ref('身份校验未启动')
  const faceCount = ref(0)
  const singleFaceReady = ref(false)
  const liveReady = ref(false)
  const lastMotion = ref(0)

  let detector: FaceDetectorLike | null = null
  let boundVideo: HTMLVideoElement | null = null
  let timerId: ReturnType<typeof setTimeout> | null = null
  let singleFaceStreak = 0
  let previousCenter: { x: number; y: number } | null = null

  const supported = computed(() => typeof window !== 'undefined' && typeof window.FaceDetector === 'function')
  const verified = computed(() => singleFaceReady.value && liveReady.value)

  function reset(reason = '等待身份校验') {
    status.value = supported.value ? 'checking' : 'unsupported'
    message.value = supported.value ? reason : '当前浏览器不支持本地人脸检测'
    faceCount.value = 0
    singleFaceReady.value = false
    liveReady.value = false
    lastMotion.value = 0
    singleFaceStreak = 0
    previousCenter = null
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

  async function ensureDetector() {
    if (!supported.value) {
      status.value = 'unsupported'
      message.value = '当前浏览器不支持本地人脸检测'
      return false
    }

    if (!detector) {
      detector = new window.FaceDetector!({
        fastMode: true,
        maxDetectedFaces: 3,
      })
    }
    return true
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

    const ok = await ensureDetector()
    if (!ok || !detector) return

    try {
      const faces = await detector.detect(boundVideo)
      faceCount.value = faces.length

      if (faces.length !== 1 || !faces[0].boundingBox) {
        singleFaceStreak = 0
        singleFaceReady.value = false
        liveReady.value = false
        previousCenter = null
        status.value = 'warn'
        message.value = faces.length === 0
          ? '请确保仅本人单人入镜'
          : '检测到多人入镜，请保持单人画面'
        queueNextCheck()
        return
      }

      singleFaceStreak += 1
      if (singleFaceStreak >= REQUIRED_SINGLE_FACE_STREAK) {
        singleFaceReady.value = true
      }

      const box = faces[0].boundingBox
      const center = {
        x: box.x + box.width / 2,
        y: box.y + box.height / 2,
      }

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
        ? '单人入镜与活体校验通过'
        : singleFaceReady.value
          ? '请做轻微自然动作以完成活体校验'
          : '正在确认是否为单人稳定入镜'
    } catch (error) {
      status.value = 'error'
      message.value = '身份校验运行失败，请稍后重试'
      console.warn('Presence monitor failed', error)
    }

    queueNextCheck()
  }

  async function attachVideo(video: HTMLVideoElement | null) {
    boundVideo = video
    stopLoop()
    if (!video) return
    reset('正在启动身份校验')
    if (!supported.value) return
    await detectFrame()
  }

  async function restart() {
    if (!boundVideo) return
    reset('正在重新校验身份')
    await detectFrame()
  }

  function stop() {
    stopLoop()
    boundVideo = null
    detector = null
    status.value = 'idle'
    message.value = '身份校验已停止'
    faceCount.value = 0
    singleFaceReady.value = false
    liveReady.value = false
    lastMotion.value = 0
    singleFaceStreak = 0
    previousCenter = null
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
    attachVideo,
    restart,
    stop,
  }
}
