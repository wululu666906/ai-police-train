import { onBeforeUnmount, shallowRef, type Ref } from 'vue'

const SILENCE_FLOOR = 0.025
const NOISE_GATE = 0.04
const ATTACK_FACTOR = 0.4
const RELEASE_FACTOR = 0.12
const MIN_ACTIVE_LEVEL = 0.08
const MAX_LEVEL = 0.95
const SAMPLE_INTERVAL_MS = 33 // 波纹滚动速度：约 30Hz（比 60Hz 慢一半）
const LEVEL_GAMMA = 0.78 // <1 更敏感，弱声音也有起伏

type WaveformVariant = 'scrolling' | 'compact' | 'centered'

export type UseRecordingWaveformOptions = {
  bufferDurationSecs?: number
  variant?: WaveformVariant
}

export const useRecordingWaveform = (
  canvasRef: Ref<HTMLCanvasElement | null>,
  options: UseRecordingWaveformOptions = {}
) => {
  const variant: WaveformVariant = options.variant ?? 'scrolling'
  const isCapturing = shallowRef(false)
  let historyLength = 0

  let levels: number[] = []
  let smoothedLevel = SILENCE_FLOOR
  let lastInputLevel = SILENCE_FLOOR
  let lastSampleAt = 0
  let currentLevel = SILENCE_FLOOR
  let frameRafId = 0
  let resizeObserver: ResizeObserver | null = null

  const initCanvas = (canvas: HTMLCanvasElement) => {
    const width = canvas.clientWidth
    if (width <= 0) return false
    const barCount = variant === 'compact' ? 4 : Math.max(24, Math.floor(width / 4))
    historyLength = barCount
    levels = Array.from({ length: barCount }, () => SILENCE_FLOOR)
    return true
  }

  const drawWaveform = () => {
    const canvas = canvasRef.value
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const { clientHeight, clientWidth } = canvas
    if (clientWidth === 0 || clientHeight === 0) return

    const desiredBarCount = variant === 'compact' ? 4 : Math.max(24, Math.floor(clientWidth / 4))
    if (levels.length !== desiredBarCount) {
      initCanvas(canvas)
    }
    if (levels.length === 0) return

    const dpr = window.devicePixelRatio || 1
    canvas.width = clientWidth * dpr
    canvas.height = clientHeight * dpr
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.save()

    const centerY = canvas.height * 0.5
    ctx.translate(0, centerY)
    const barWidth = canvas.width / levels.length
    const color = getComputedStyle(canvas).color || '#64748b'
    ctx.fillStyle = color

    for (let i = 0; i < levels.length; i += 1) {
      const level = Math.max(SILENCE_FLOOR, levels[i] ?? SILENCE_FLOOR)
      const shaped = Math.pow(level, LEVEL_GAMMA)
      const halfHeight = shaped * centerY * 1.65
      const x = i * barWidth
      const alpha = level <= MIN_ACTIVE_LEVEL ? 0.35 : 1
      ctx.globalAlpha = alpha
      const w = Math.max(1, barWidth * 0.45)
      const inset = (barWidth - w) * 0.5
      ctx.fillRect(x + inset, -halfHeight, w, halfHeight * 2)
    }

    ctx.restore()
  }

  const pushRenderedLevel = (level: number) => {
    if (levels.length === 0) return
    levels.push(level)
    if (levels.length > historyLength) {
      levels.shift()
    }
  }

  const frameTick = () => {
    if (!isCapturing.value) return

    const target =
      lastInputLevel < NOISE_GATE ? SILENCE_FLOOR : Math.min(MAX_LEVEL, Math.max(MIN_ACTIVE_LEVEL, lastInputLevel))
    const factor = target > smoothedLevel ? ATTACK_FACTOR : RELEASE_FACTOR
    smoothedLevel += (target - smoothedLevel) * factor
    currentLevel = Math.max(SILENCE_FLOOR, Math.min(MAX_LEVEL, smoothedLevel))

    const now = performance.now()
    if (now - lastSampleAt >= SAMPLE_INTERVAL_MS) {
      lastSampleAt = now
      pushRenderedLevel(currentLevel)
    }
    drawWaveform()
    frameRafId = window.requestAnimationFrame(frameTick)
  }

  const clearCanvas = () => {
    const canvas = canvasRef.value
    const ctx = canvas?.getContext('2d')
    if (!canvas || !ctx) return
    ctx.clearRect(0, 0, canvas.width, canvas.height)
  }

  const resetWaveformDisplay = () => {
    levels = []
    smoothedLevel = SILENCE_FLOOR
    lastInputLevel = SILENCE_FLOOR
    clearCanvas()
  }

  const stopWaveformCapture = () => {
    isCapturing.value = false
    if (frameRafId) {
      window.cancelAnimationFrame(frameRafId)
      frameRafId = 0
    }
    resizeObserver?.disconnect()
    resizeObserver = null
    resetWaveformDisplay()
  }

  const pushAudioLevel = (level: number) => {
    if (!isCapturing.value) return
    const normalized = Math.max(0, Math.min(1, Number.isFinite(level) ? level : 0))
    lastInputLevel = normalized
  }

  const startWaveformDisplay = () => {
    stopWaveformCapture()
    isCapturing.value = true
    const canvas = canvasRef.value
    if (canvas) {
      initCanvas(canvas)
      drawWaveform()
      if (typeof ResizeObserver !== 'undefined') {
        resizeObserver = new ResizeObserver(() => {
          if (canvasRef.value) {
            initCanvas(canvasRef.value)
            drawWaveform()
          }
        })
        resizeObserver.observe(canvas)
      }
    }
    lastSampleAt = 0
    currentLevel = SILENCE_FLOOR
    frameRafId = window.requestAnimationFrame(frameTick)
  }

  // 兼容旧接口：采集由 AudioHub 统一管理，波纹这里仅做展示。
  const startWaveformCapture = async () => {
    startWaveformDisplay()
  }

  onBeforeUnmount(() => {
    stopWaveformCapture()
  })

  return {
    isCapturing,
    startWaveformDisplay,
    pushAudioLevel,
    startWaveformCapture,
    stopWaveformCapture,
    resetWaveformDisplay,
    redrawWaveform: drawWaveform,
  }
}
