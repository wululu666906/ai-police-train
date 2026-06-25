import { ref } from 'vue'

type Landmark = {
  x: number
  y: number
  z?: number
  visibility?: number
  presence?: number
}

type VisionStatus = 'idle' | 'ready' | 'unavailable'

const modelBase = (import.meta.env.VITE_MEDIAPIPE_MODEL_BASE || '/mediapipe/models').replace(/\/$/, '')

export function useMultimodalVision() {
  const status = ref<VisionStatus>('idle')
  const error = ref('')
  let visionModulePromise: Promise<any> | null = null
  let handLandmarker: any = null
  let poseLandmarker: any = null
  let lastMotionAverage: number | null = null

  const loadVisionModule = async () => {
    if (!visionModulePromise) {
      visionModulePromise = import('@mediapipe/tasks-vision')
    }
    return visionModulePromise
  }

  const init = async () => {
    if (status.value === 'ready') return true
    try {
      const vision = await loadVisionModule()
      const resolver = await vision.FilesetResolver.forVisionTasks(`${modelBase}/wasm`)
      handLandmarker = await vision.HandLandmarker.createFromOptions(resolver, {
        baseOptions: { modelAssetPath: `${modelBase}/hand_landmarker.task` },
        runningMode: 'VIDEO',
        numHands: 2,
      })
      poseLandmarker = await vision.PoseLandmarker.createFromOptions(resolver, {
        baseOptions: { modelAssetPath: `${modelBase}/pose_landmarker_lite.task` },
        runningMode: 'VIDEO',
        numPoses: 1,
      })
      status.value = 'ready'
      error.value = ''
      return true
    } catch (err: any) {
      status.value = 'unavailable'
      error.value = String(err?.message || err || 'MediaPipe unavailable')
      return false
    }
  }

  const summarizeMotion = (canvas: HTMLCanvasElement) => {
    const ctx = canvas.getContext('2d')
    if (!ctx) return { motion_score: 0 }
    const imageData = ctx.getImageData(0, 0, Math.min(64, canvas.width), Math.min(64, canvas.height)).data
    let total = 0
    for (let index = 0; index < imageData.length; index += 4) {
      total += (imageData[index] + imageData[index + 1] + imageData[index + 2]) / 3
    }
    const average = total / Math.max(imageData.length / 4, 1)
    const delta = lastMotionAverage == null ? 0 : Math.abs(average - lastMotionAverage)
    lastMotionAverage = average
    return { motion_score: Math.max(0, Math.min(1, delta / 28)) }
  }

  const toLandmarks = (items?: Landmark[]) =>
    Array.isArray(items)
      ? items.map((point) => ({
          x: Number(point.x || 0),
          y: Number(point.y || 0),
          z: Number(point.z || 0),
          visibility: Number(point.visibility ?? point.presence ?? 1),
        }))
      : []

  const analyze = async (video: HTMLVideoElement | null, canvas: HTMLCanvasElement | null) => {
    const ready = await init()
    if (!ready || !video || !canvas || !video.videoWidth) {
      return {
        hands: [],
        pose: { landmarks: [] },
        motion: canvas ? summarizeMotion(canvas) : { motion_score: 0 },
        model_status: { mediapipe: status.value, error: error.value },
      }
    }

    const timestamp = performance.now()
    const handResult = handLandmarker?.detectForVideo(video, timestamp)
    const poseResult = poseLandmarker?.detectForVideo(video, timestamp)
    const hands = (handResult?.landmarks || []).map((landmarks: Landmark[], index: number) => ({
      landmarks: toLandmarks(landmarks),
      handedness: handResult?.handedness?.[index]?.[0]?.categoryName || '',
      score: Number(handResult?.handedness?.[index]?.[0]?.score || 0.75),
    }))
    const poseLandmarks = toLandmarks(poseResult?.landmarks?.[0] || [])

    return {
      hands,
      pose: { landmarks: poseLandmarks },
      motion: summarizeMotion(canvas),
      model_status: { mediapipe: status.value, error: error.value },
    }
  }

  return { status, error, init, analyze }
}
