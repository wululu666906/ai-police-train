<template>
  <div class="handwriting-pad">
    <div class="handwriting-toolbar">
      <button type="button" class="tool-btn" :disabled="!strokes.length" @click="undoStroke">撤销</button>
      <button type="button" class="tool-btn" :disabled="!strokes.length" @click="clearCanvas">清空</button>
      <span class="handwriting-hint">在下方区域手写，确认后写入输入框</span>
    </div>

    <div ref="canvasWrapRef" class="handwriting-canvas-wrap">
      <canvas
        ref="canvasRef"
        class="handwriting-canvas"
        @pointerdown.prevent="onPointerDown"
        @pointermove.prevent="onPointerMove"
        @pointerup.prevent="onPointerUp"
        @pointercancel.prevent="onPointerUp"
        @pointerleave.prevent="onPointerUp"
      ></canvas>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { HandwritingStroke, HandwritingStrokePoint } from '../services/handwriting'

const props = withDefaults(
  defineProps<{
    lineWidth?: number
    strokeColor?: string
  }>(),
  {
    lineWidth: 3,
    strokeColor: '#0f172a',
  }
)

const emit = defineEmits<{
  change: [strokes: HandwritingStroke[]]
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const canvasWrapRef = ref<HTMLElement | null>(null)
const strokes = ref<HandwritingStroke[]>([])
const currentStroke = ref<HandwritingStrokePoint[]>([])
const isDrawing = ref(false)

let resizeObserver: ResizeObserver | null = null

const getContext = () => canvasRef.value?.getContext('2d') || null

const resizeCanvas = () => {
  const canvas = canvasRef.value
  const wrap = canvasWrapRef.value
  if (!canvas || !wrap) return

  const rect = wrap.getBoundingClientRect()
  const ratio = window.devicePixelRatio || 1
  canvas.width = Math.max(1, Math.floor(rect.width * ratio))
  canvas.height = Math.max(1, Math.floor(rect.height * ratio))
  canvas.style.width = `${rect.width}px`
  canvas.style.height = `${rect.height}px`

  const ctx = getContext()
  if (!ctx) return
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
  redraw()
}

const redraw = () => {
  const ctx = getContext()
  const canvas = canvasRef.value
  if (!ctx || !canvas) return

  const ratio = window.devicePixelRatio || 1
  const width = canvas.width / ratio
  const height = canvas.height / ratio

  ctx.clearRect(0, 0, width, height)
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.strokeStyle = props.strokeColor
  ctx.lineWidth = props.lineWidth

  const drawStroke = (points: HandwritingStrokePoint[]) => {
    if (points.length < 2) return
    ctx.beginPath()
    ctx.moveTo(points[0].x, points[0].y)
    for (let index = 1; index < points.length; index += 1) {
      ctx.lineTo(points[index].x, points[index].y)
    }
    ctx.stroke()
  }

  strokes.value.forEach((stroke) => drawStroke(stroke.points))
  drawStroke(currentStroke.value)
}

const emitChange = () => {
  emit('change', strokes.value.map((stroke) => ({ points: [...stroke.points] })))
}

const getPoint = (event: PointerEvent): HandwritingStrokePoint | null => {
  const canvas = canvasRef.value
  if (!canvas) return null
  const rect = canvas.getBoundingClientRect()
  return {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top,
  }
}

const onPointerDown = (event: PointerEvent) => {
  if (event.button !== 0) return
  const point = getPoint(event)
  if (!point) return
  isDrawing.value = true
  currentStroke.value = [point]
  canvasRef.value?.setPointerCapture(event.pointerId)
  redraw()
}

const onPointerMove = (event: PointerEvent) => {
  if (!isDrawing.value) return
  const point = getPoint(event)
  if (!point) return
  currentStroke.value.push(point)
  redraw()
}

const onPointerUp = (event: PointerEvent) => {
  if (!isDrawing.value) return
  isDrawing.value = false
  if (currentStroke.value.length) {
    strokes.value.push({ points: [...currentStroke.value] })
    currentStroke.value = []
    emitChange()
  }
  try {
    canvasRef.value?.releasePointerCapture(event.pointerId)
  } catch {
    // noop
  }
  redraw()
}

const undoStroke = () => {
  strokes.value.pop()
  emitChange()
  redraw()
}

const clearCanvas = () => {
  strokes.value = []
  currentStroke.value = []
  emitChange()
  redraw()
}

const exportImage = (): string => {
  const canvas = canvasRef.value
  if (!canvas) return ''
  return canvas.toDataURL('image/png')
}

const getStrokes = () => strokes.value.map((stroke) => ({ points: [...stroke.points] }))

const getSize = () => {
  const wrap = canvasWrapRef.value
  return {
    width: wrap?.clientWidth || 0,
    height: wrap?.clientHeight || 0,
  }
}

defineExpose({
  exportImage,
  getStrokes,
  getSize,
  clearCanvas,
})

watch(
  () => [props.lineWidth, props.strokeColor],
  () => redraw()
)

onMounted(async () => {
  await nextTick()
  resizeCanvas()
  resizeObserver = new ResizeObserver(() => resizeCanvas())
  if (canvasWrapRef.value) {
    resizeObserver.observe(canvasWrapRef.value)
  }
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
})
</script>

<style scoped>
.handwriting-pad {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.handwriting-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.tool-btn {
  border: 1px solid rgba(15, 23, 42, 0.12);
  border-radius: 999px;
  background: #fff;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 12px;
  cursor: pointer;
}

.tool-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.handwriting-hint {
  margin-left: auto;
  font-size: 12px;
  color: #64748b;
}

.handwriting-canvas-wrap {
  height: 220px;
  border-radius: 16px;
  border: 1px dashed rgba(15, 23, 42, 0.16);
  background: #fff;
  overflow: hidden;
}

.handwriting-canvas {
  display: block;
  width: 100%;
  height: 100%;
  touch-action: none;
  cursor: crosshair;
}
</style>
