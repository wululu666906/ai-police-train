<template>
  <div class="training-input-bar">
    <div class="mode-switch">
      <button
        type="button"
        class="mode-switch__link"
        :disabled="disabled || inVoiceCall"
        @click="inputMode = inputMode === 'voice' ? 'typing' : 'voice'"
      >
        {{ inputMode === 'voice' ? '切换打字输入' : '切换语音电话' }}
      </button>
    </div>

    <div v-if="inputMode === 'voice'" class="voice-call-panel">
      <div class="input-shell voice-input-shell" :class="{ 'is-disabled': disabled }">
        <textarea
          ref="textareaRef"
          :value="modelValue"
          rows="1"
          class="input-box"
          placeholder="语音识别内容会实时显示在这里..."
          readonly
        ></textarea>
      </div>

      <div class="voice-call-dock">
        <div class="voice-call-dock__caption">
          <span v-if="voiceHintType === 'error'" class="voice-call-dock__hint voice-call-dock__hint--error">
            {{ voiceHint }}
          </span>
          <span v-else-if="isMuted" class="voice-call-dock__hint">麦克风已关闭，通话保持中</span>
          <span v-else class="voice-call-dock__hint">
            {{ voiceHint || '点击麦克风开始语音电话，说完后自动识别并发送' }}
          </span>
        </div>

        <div class="voice-call-dock__controls">
          <button
            type="button"
            class="voice-call-dock__btn voice-call-dock__btn--mic"
            :class="{ 'is-active': inVoiceCall && !isMuted, 'is-muted': isMuted }"
            :disabled="disabled || isConnecting"
            :title="micButtonTitle"
            @click="toggleVoiceCall"
          >
            <van-icon :name="isMuted ? 'volume-o' : 'service-o'" size="22" color="#fff" />
          </button>

          <button
            type="button"
            class="voice-call-dock__btn voice-call-dock__btn--close"
            :disabled="!inVoiceCall || isConnecting"
            title="结束通话"
            @click="endVoiceCall"
          >
            <van-icon name="cross" size="22" color="#fff" />
          </button>
        </div>
      </div>
    </div>

    <div v-else class="composer-row">
      <div class="input-shell" :class="{ 'is-disabled': disabled }">
        <textarea
          ref="textareaRef"
          :value="modelValue"
          rows="1"
          class="input-box"
          :placeholder="placeholder"
          :disabled="disabled"
          @input="onTextInput"
          @keydown.enter.exact.prevent="emitSend"
        ></textarea>
      </div>

      <button
        type="button"
        class="send-btn-card"
        :disabled="!modelValue.trim() || disabled || loading"
        @click="emitSend"
      >
        {{ loading ? '发送中' : '发送' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { showToast } from 'vant'

const props = withDefaults(
  defineProps<{
    modelValue: string
    disabled?: boolean
    loading?: boolean
    placeholder?: string
  }>(),
  {
    disabled: false,
    loading: false,
    placeholder: '请输入处置话术...',
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  send: []
  'voice-send': [transcript: string]
  'voice-event': [payload: {
    event_type: string
    transcript?: string
    model?: string
  }]
}>()

type InputMode = 'voice' | 'typing'
type VoiceHintType = 'info' | 'error'

const MIN_TRANSCRIPT_LEN = 2
const TARGET_SAMPLE_RATE = 16000
const SEND_AFTER_SILENCE_MS = 2200
const SEND_AFTER_LOADING_IDLE_MS = 2200

const inputMode = ref<InputMode>('voice')
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const socket = ref<WebSocket | null>(null)
const micStream = ref<MediaStream | null>(null)
const audioContext = ref<AudioContext | null>(null)
const audioSource = ref<MediaStreamAudioSourceNode | null>(null)
const audioProcessor = ref<ScriptProcessorNode | null>(null)
const inVoiceCall = ref(false)
const isConnecting = ref(false)
const isMuted = ref(false)
const voiceHint = ref('')
const voiceHintType = ref<VoiceHintType>('info')
const voiceDraftSegments = ref<string[]>([])
const currentPartial = ref('')
let lastSentTranscript = ''
let lastModel = ''
let sendTimer: ReturnType<typeof window.setTimeout> | null = null

const micButtonTitle = computed(() => {
  if (isConnecting.value) return '正在连接语音电话'
  if (!inVoiceCall.value) return '开始语音电话'
  return isMuted.value ? '打开麦克风' : '关闭麦克风'
})

const onTextInput = (event: Event) => {
  emit('update:modelValue', (event.target as HTMLTextAreaElement).value)
  resizeTextarea()
}

const resizeTextarea = () => {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 120)}px`
}

const emitSend = () => {
  if (!props.modelValue.trim() || props.disabled || props.loading) return
  emit('send')
  requestAnimationFrame(() => resizeTextarea())
}

const getApiBaseUrl = () => {
  return import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '')
}

const getRealtimeWsUrl = () => {
  const apiBase = getApiBaseUrl().replace(/\/$/, '')
  const httpBase = apiBase || window.location.origin
  const wsBase = httpBase.replace(/^http/i, 'ws')
  const token = encodeURIComponent(localStorage.getItem('token') || '')
  return `${wsBase}/speech/realtime?language=zh&token=${token}`
}

const downsampleTo16k = (samples: Float32Array, sourceRate: number) => {
  if (sourceRate === TARGET_SAMPLE_RATE) return samples
  const ratio = sourceRate / TARGET_SAMPLE_RATE
  const nextLength = Math.max(1, Math.round(samples.length / ratio))
  const result = new Float32Array(nextLength)
  let sourceOffset = 0
  for (let i = 0; i < nextLength; i += 1) {
    const nextOffset = Math.round((i + 1) * ratio)
    let sum = 0
    let count = 0
    for (let j = sourceOffset; j < nextOffset && j < samples.length; j += 1) {
      sum += samples[j]
      count += 1
    }
    result[i] = count ? sum / count : 0
    sourceOffset = nextOffset
  }
  return result
}

const pcm16ToBase64 = (samples: Float32Array) => {
  const buffer = new ArrayBuffer(samples.length * 2)
  const view = new DataView(buffer)
  for (let i = 0; i < samples.length; i += 1) {
    const clamped = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true)
  }
  const bytes = new Uint8Array(buffer)
  let binary = ''
  const chunkSize = 0x8000
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize))
  }
  return window.btoa(binary)
}

const clearSendTimer = () => {
  if (!sendTimer) return
  window.clearTimeout(sendTimer)
  sendTimer = null
}

const setInputPreview = (text: string) => {
  emit('update:modelValue', text)
  void nextTick(resizeTextarea)
}

const buildDraftText = () => {
  return [...voiceDraftSegments.value, currentPartial.value].filter(Boolean).join('')
}

const refreshVoicePreview = () => {
  setInputPreview(buildDraftText())
}

const mergePartialDelta = (delta: string) => {
  const previous = currentPartial.value
  if (!previous || delta.startsWith(previous)) return delta
  if (previous.endsWith(delta) || previous.includes(delta)) return previous
  return `${previous}${delta}`
}

const resetVoiceDraft = () => {
  voiceDraftSegments.value = []
  currentPartial.value = ''
  lastSentTranscript = ''
  clearSendTimer()
}

const trySendVoiceDraft = (delayMs = SEND_AFTER_SILENCE_MS) => {
  clearSendTimer()
  sendTimer = window.setTimeout(() => {
    if (!inVoiceCall.value) return

    const draft = buildDraftText().trim()
    if (!draft || draft.length < MIN_TRANSCRIPT_LEN) return

    if (currentPartial.value.trim()) {
      voiceHint.value = '正在识别，等待你说完后发送...'
      trySendVoiceDraft(SEND_AFTER_SILENCE_MS)
      return
    }

    if (props.loading || props.disabled) {
      voiceHint.value = '已识别，等待 AI 回复结束并确认你没有继续说话...'
      trySendVoiceDraft(SEND_AFTER_LOADING_IDLE_MS)
      return
    }

    if (draft === lastSentTranscript) return
    lastSentTranscript = draft
    voiceDraftSegments.value = []
    currentPartial.value = ''
    setInputPreview(draft)
    voiceHint.value = '识别完成，正在发送...'
    emit('voice-send', draft)
  }, delayMs)
}

const dispatchTranscriptDelta = (text: string, model?: string) => {
  const delta = text.trim()
  if (!delta) return
  lastModel = model || lastModel
  currentPartial.value = mergePartialDelta(delta)
  refreshVoicePreview()
  voiceHint.value = '正在识别，继续说完后会自动发送...'
  emit('voice-event', {
    event_type: 'transcript_delta',
    transcript: buildDraftText(),
    model: lastModel,
  })
  trySendVoiceDraft(SEND_AFTER_SILENCE_MS)
}

const dispatchTranscript = (text: string, model?: string) => {
  const transcript = text.trim()
  if (transcript.length < MIN_TRANSCRIPT_LEN) return
  lastModel = model || lastModel
  const finalText =
    currentPartial.value &&
    !transcript.includes(currentPartial.value) &&
    !currentPartial.value.includes(transcript)
      ? `${currentPartial.value}${transcript}`
      : transcript

  if (voiceDraftSegments.value[voiceDraftSegments.value.length - 1] !== finalText) {
    voiceDraftSegments.value.push(finalText)
  }
  currentPartial.value = ''
  refreshVoicePreview()
  voiceHint.value = '已识别，等待静默确认后发送...'
  emit('voice-event', {
    event_type: 'utterance_end',
    transcript: buildDraftText(),
    model: lastModel,
  })
  trySendVoiceDraft(SEND_AFTER_SILENCE_MS)
}

watch(
  () => props.loading,
  (loading) => {
    if (!loading && inVoiceCall.value && voiceDraftSegments.value.length) {
      voiceHint.value = 'AI 回复结束，等待确认你没有继续说话...'
      trySendVoiceDraft(SEND_AFTER_LOADING_IDLE_MS)
    }
  }
)

const connectRealtimeSocket = () =>
  new Promise<WebSocket>((resolve, reject) => {
    const ws = new WebSocket(getRealtimeWsUrl())
    ws.onopen = () => resolve(ws)
    ws.onerror = () => reject(new Error('实时语音服务连接失败'))
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(String(event.data || '{}'))
        if (payload.type === 'ready') {
          lastModel = String(payload.realtime_model || '')
          voiceHint.value = '语音电话已连接，千问服务端 VAD 正在监听'
          emit('voice-event', { event_type: 'call_start', model: lastModel })
        } else if (payload.type === 'transcript_delta') {
          dispatchTranscriptDelta(String(payload.text || ''), String(payload.model || ''))
        } else if (payload.type === 'transcript') {
          dispatchTranscript(String(payload.text || ''), String(payload.model || ''))
        } else if (payload.type === 'error') {
          throw new Error(String(payload.message || '实时语音识别失败'))
        }
      } catch (error: any) {
        voiceHintType.value = 'error'
        voiceHint.value = error?.message || '实时语音识别失败'
      }
    }
    ws.onclose = () => {
      if (inVoiceCall.value) {
        cleanupVoiceCall(false)
        voiceHintType.value = 'error'
        voiceHint.value = '语音电话已断开'
      }
    }
  })

const startPcmStreaming = async (stream: MediaStream, ws: WebSocket) => {
  const context = new AudioContext()
  if (context.state === 'suspended') await context.resume()
  const source = context.createMediaStreamSource(stream)
  const processor = context.createScriptProcessor(4096, 1, 1)
  processor.onaudioprocess = (event) => {
    if (ws.readyState !== WebSocket.OPEN || isMuted.value) return
    const channel = event.inputBuffer.getChannelData(0)
    const downsampled = downsampleTo16k(channel, context.sampleRate)
    const audio = pcm16ToBase64(downsampled)
    if (audio) ws.send(JSON.stringify({ type: 'audio', audio }))
  }
  source.connect(processor)
  processor.connect(context.destination)
  audioContext.value = context
  audioSource.value = source
  audioProcessor.value = processor
}

const startVoiceCall = async () => {
  if (props.disabled || isConnecting.value || inVoiceCall.value) return
  if (!navigator.mediaDevices?.getUserMedia || typeof AudioContext === 'undefined') {
    voiceHintType.value = 'error'
    voiceHint.value = '当前浏览器不支持实时语音电话'
    return
  }

  isConnecting.value = true
  voiceHintType.value = 'info'
  voiceHint.value = '正在连接语音电话...'
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    })
    const ws = await connectRealtimeSocket()
    socket.value = ws
    micStream.value = stream
    inVoiceCall.value = true
    isMuted.value = false
    resetVoiceDraft()
    setInputPreview('')
    await startPcmStreaming(stream, ws)
  } catch (error: any) {
    cleanupVoiceCall(true)
    const detail = error?.message || '无法启动语音电话'
    voiceHintType.value = 'error'
    voiceHint.value = detail
    showToast({ type: 'fail', message: detail })
  } finally {
    isConnecting.value = false
  }
}

const setMicEnabled = (enabled: boolean) => {
  micStream.value?.getAudioTracks().forEach((track) => {
    track.enabled = enabled
  })
  isMuted.value = !enabled
  emit('voice-event', { event_type: enabled ? 'unmute' : 'mute', model: lastModel })
}

const toggleVoiceCall = async () => {
  if (!inVoiceCall.value) {
    await startVoiceCall()
    return
  }
  setMicEnabled(isMuted.value)
}

const cleanupVoiceCall = (notifyUpstream: boolean) => {
  clearSendTimer()
  audioProcessor.value?.disconnect()
  audioSource.value?.disconnect()
  void audioContext.value?.close()
  audioProcessor.value = null
  audioSource.value = null
  audioContext.value = null
  micStream.value?.getTracks().forEach((track) => track.stop())
  micStream.value = null
  if (notifyUpstream && socket.value?.readyState === WebSocket.OPEN) {
    socket.value.send(JSON.stringify({ type: 'close' }))
  }
  socket.value?.close()
  socket.value = null
  inVoiceCall.value = false
  isMuted.value = false
}

const endVoiceCall = () => {
  if (!inVoiceCall.value) return
  cleanupVoiceCall(true)
  resetVoiceDraft()
  setInputPreview('')
  voiceHintType.value = 'info'
  voiceHint.value = '语音电话已结束'
  emit('voice-event', { event_type: 'call_end', model: lastModel })
}

onBeforeUnmount(() => {
  cleanupVoiceCall(true)
})

watch(
  () => props.modelValue,
  () => {
    void nextTick(resizeTextarea)
  }
)
</script>

<style scoped>
.training-input-bar {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mode-switch {
  display: flex;
  justify-content: flex-end;
}

.mode-switch__link {
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}

.mode-switch__link:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.voice-call-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.voice-input-shell {
  min-height: 42px;
}

.voice-call-dock {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 58px;
  padding: 8px 12px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.voice-call-dock__caption {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
}

.voice-call-dock__hint {
  font-size: 13px;
  color: #64748b;
  font-weight: 600;
}

.voice-call-dock__hint--error {
  color: #dc2626;
}

.voice-call-dock__controls {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 10px;
}

.voice-call-dock__btn {
  width: 44px;
  height: 44px;
  border: none;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform 0.12s ease, opacity 0.15s ease, background 0.15s ease;
}

.voice-call-dock__btn:active:not(:disabled) {
  transform: scale(0.96);
}

.voice-call-dock__btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.voice-call-dock__btn--mic {
  background: #334155;
  box-shadow: 0 5px 12px rgba(15, 23, 42, 0.16);
}

.voice-call-dock__btn--mic.is-active {
  background: #165dff;
}

.voice-call-dock__btn--mic.is-muted {
  background: #94a3b8;
}

.voice-call-dock__btn--close {
  background: #ef4444;
  box-shadow: 0 5px 12px rgba(239, 68, 68, 0.2);
}

.composer-row {
  display: flex;
  align-items: stretch;
  gap: 10px;
}

.input-shell {
  flex: 1;
  display: flex;
  align-items: flex-end;
  min-height: 40px;
  padding: 6px 12px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.06);
}

.input-shell.is-disabled {
  background: #f1f5f9;
  opacity: 0.85;
}

.input-box {
  flex: 1;
  min-height: 28px;
  max-height: 120px;
  resize: none;
  border: none;
  padding: 4px 0;
  background: transparent;
  color: #0f172a;
  font-size: 15px;
  line-height: 1.45;
  outline: none;
}

.input-box::placeholder {
  color: #94a3b8;
}

.send-btn-card {
  flex-shrink: 0;
  align-self: stretch;
  min-width: 68px;
  padding: 0 18px;
  border: none;
  border-radius: 8px;
  background: #12b7f5;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}

.send-btn-card:disabled {
  background: #a8ddf3;
  cursor: not-allowed;
}
</style>
