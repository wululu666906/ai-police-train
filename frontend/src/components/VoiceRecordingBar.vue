<template>
  <div class="voice-recording-bar">
    <div class="voice-recording-bar__mic" aria-hidden="true">
      <svg class="voice-recording-bar__mic-icon" viewBox="0 0 24 24" fill="none">
        <rect x="9" y="3" width="6" height="11" rx="3" stroke="currentColor" stroke-width="1.6" />
        <path
          d="M6 11a6 6 0 0 0 12 0"
          stroke="currentColor"
          stroke-width="1.6"
          stroke-linecap="round"
        />
        <path d="M12 17v3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />
      </svg>
    </div>

    <div class="voice-recording-bar__wave">
      <canvas ref="canvasRef" class="voice-recording-bar__canvas" aria-hidden="true"></canvas>
    </div>

    <div class="voice-recording-bar__controls">
      <span class="voice-recording-bar__timer">{{ elapsedLabel }}</span>
      <button type="button" class="voice-recording-bar__icon-btn" title="取消听写" @click="emit('cancel')">
        <van-icon name="cross" size="16" />
      </button>
      <button type="button" class="voice-recording-bar__icon-btn" title="完成听写" @click="emit('confirm')">
        <van-icon name="success" size="16" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { useRecordingWaveform } from '../composables/useRecordingWaveform'

defineProps<{
  elapsedLabel: string
}>()

const emit = defineEmits<{
  cancel: []
  confirm: []
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const waveform = useRecordingWaveform(canvasRef, {
  variant: 'scrolling',
  bufferDurationSecs: 10,
})

const startWaveformDisplay = () => waveform.startWaveformDisplay()
const pushAudioLevel = (level: number) => waveform.pushAudioLevel(level)
const stopWaveformCapture = () => waveform.stopWaveformCapture()
const resetWaveformDisplay = () => waveform.resetWaveformDisplay()

defineExpose({
  startWaveformDisplay,
  pushAudioLevel,
  stopWaveformCapture,
  resetWaveformDisplay,
})

onBeforeUnmount(() => {
  stopWaveformCapture()
})
</script>

<style scoped>
.voice-recording-bar {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 6px 6px 6px 12px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.06);
  box-shadow: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.voice-recording-bar__mic {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #64748b;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.voice-recording-bar__mic-icon {
  width: 22px;
  height: 22px;
}

.voice-recording-bar__wave {
  flex: 1;
  min-width: 0;
  height: 32px;
  display: flex;
  align-items: center;
}

.voice-recording-bar__canvas {
  display: block;
  width: 100%;
  height: 100%;
  color: #64748b;
}

.voice-recording-bar__controls {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.voice-recording-bar__timer {
  min-width: 34px;
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: #0f172a;
  text-align: right;
}

.voice-recording-bar__icon-btn {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: #64748b;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.voice-recording-bar__icon-btn:last-child {
  color: #64748b;
}

.voice-recording-bar__icon-btn:active {
  background: rgba(15, 23, 42, 0.06);
}
</style>
