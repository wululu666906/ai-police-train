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

    <div v-if="inputMode === 'voice'" class="voice-call-panel voice-call-panel--legacy">
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

    <div v-if="inputMode === 'voice'" class="container-vao" :class="{ 'is-open': isVoiceCardOpen, 'is-error': voiceHintType === 'error' }">
      <div class="container-chat-ia" aria-live="polite">
        <div class="container-title">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M3 14V10M21 14V10M16.5 18V8M12 22V2M7.5 18V6" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          </svg>
          <p class="text-title"><span>实时</span><span>语音助手</span></p>
          <span class="voice-source-state">{{ voiceCardState }}</span>
        </div>
        <div class="container-chat">
          <div class="container-chat-limit">
            <div class="chats" :class="{ 'is-sending': isVoiceSending }">
              <div v-if="voiceDisplayTranscriptWords.length" class="chat-user" style="--delay: 0">
                <p>
                  <span v-for="(word, index) in voiceDisplayTranscriptWords" :key="`text-${index}-${word}`" :style="wordDelay(index)">{{ word }}</span>
                </p>
              </div>
              <div v-if="isVoiceSending || !voiceDisplayTranscriptWords.length" class="chat-ia" style="--delay: 0">
                <p>
                  <span v-for="(word, index) in voiceCardHintWords" :key="`hint-${index}-${word}`" :style="wordDelay(index, 1)">{{ word }}</span>
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <button type="button" class="orb" :class="{ 'is-muted': isMuted, 'is-connecting': isConnecting }" :disabled="disabled || isConnecting" :title="micButtonTitle" @click="toggleVoiceCall">
        <span class="icons">
          <svg class="svg" viewBox="0 0 24 24" aria-hidden="true">
            <g class="close"><path fill="currentColor" d="M18.3 5.71a.996.996 0 0 0-1.41 0L12 10.59L7.11 5.7A.996.996 0 1 0 5.7 7.11L10.59 12L5.7 16.89a.996.996 0 1 0 1.41 1.41L12 13.41l4.89 4.89a.996.996 0 1 0 1.41-1.41L13.41 12l4.89-4.89c.38-.38.38-1.02 0-1.4" /></g>
            <g class="mic" fill="none"><rect width="8" height="13" x="8" y="2" fill="currentColor" rx="4" /><path d="M5 11a7 7 0 1 0 14 0m-7 10v-2" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" /></g>
          </svg>
        </span>
        <span class="ball"><span class="container-lines"></span><span class="container-rings"></span></span>
        <svg class="gooey-filter" aria-hidden="true"><filter id="voice-gooey"><feGaussianBlur in="SourceGraphic" stdDeviation="6" /><feColorMatrix values="1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 20 -10" /></filter></svg>
      </button>
      <button v-if="inVoiceCall" type="button" class="voice-source-close" :disabled="isConnecting" title="结束语音通话" @click="endVoiceCall">×</button>
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
import request from '../utils/request'

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
type SpeechStatusPayload = {
  configured?: boolean
  provider?: string
  source?: string
  realtime_model?: string
  realtime_url?: string
  realtime_proxy?: string
}

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
const isVoiceSending = ref(false)
const voiceSendingTranscript = ref('')
let lastSentTranscript = ''
let lastModel = ''
let sendTimer: ReturnType<typeof window.setTimeout> | null = null
let sendFlashTimer: ReturnType<typeof window.setTimeout> | null = null
let speechStatus: SpeechStatusPayload | null = null

const micButtonTitle = computed(() => {
  if (isConnecting.value) return '正在连接语音电话'
  if (!inVoiceCall.value) return '开始语音电话'
  return isMuted.value ? '打开麦克风' : '关闭麦克风'
})

const isVoiceCardOpen = computed(() => inVoiceCall.value || isConnecting.value || Boolean(voiceHint.value))
const voiceCardState = computed(() => {
  if (voiceHintType.value === 'error') return '连接异常'
  if (isConnecting.value) return '正在连接'
  if (!inVoiceCall.value) return '等待开始'
  return isMuted.value ? '已静音' : '正在聆听'
})
const voiceCardHint = computed(() => {
  if (voiceHint.value) return voiceHint.value
  if (isMuted.value) return '麦克风已关闭，语音通话保持连接。'
  if (inVoiceCall.value) return '正在聆听，请直接说出你的处置指令。'
  return '点击语音球开始通话，识别内容将在这里实时流动展示。'
})
const splitVoiceWords = (text: string) => Array.from(text.replace(/\s+/g, ' ').trim()).filter(Boolean)
const voiceCardHintWords = computed(() => splitVoiceWords(voiceCardHint.value))
const voiceDisplayTranscriptWords = computed(() => splitVoiceWords(isVoiceSending.value ? voiceSendingTranscript.value : props.modelValue))
const wordDelay = (index: number, offset = 0) => ({ '--word-delay': `${Math.min((index + offset) * 38, 720)}ms` })

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
  return import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '/api')
}

const getRealtimeHttpBase = () => {
  const apiBase = getApiBaseUrl().replace(/\/$/, '')
  if (!apiBase) return window.location.origin
  if (apiBase.startsWith('/')) return `${window.location.origin}${apiBase}`
  return apiBase
}

const getRealtimeWsUrl = () => {
  const httpBase = getRealtimeHttpBase()
  const wsBase = httpBase.replace(/^http/i, 'ws')
  const token = encodeURIComponent(localStorage.getItem('token') || '')
  return `${wsBase}/speech/realtime?language=zh&token=${token}`
}

const loadBackendSpeechStatus = async () => {
  const status = (await request.get('/speech/status', { _skipErrorToast: true } as any)) as SpeechStatusPayload
  speechStatus = status
  lastModel = String(status?.realtime_model || lastModel || '')
  if (!status?.configured) {
    throw new Error('语音服务未配置，请先在管理端 API Key 中填写千问 API Key')
  }
  if (!status?.realtime_model) {
    throw new Error('实时语音模型未配置，请先在管理端 API Key 中填写千问实时语音模型')
  }
  return status
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

const clearSendFlash = () => {
  if (sendFlashTimer) window.clearTimeout(sendFlashTimer)
  sendFlashTimer = null
  isVoiceSending.value = false
  voiceSendingTranscript.value = ''
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
  clearSendFlash()
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
    voiceSendingTranscript.value = draft
    isVoiceSending.value = true
    voiceDraftSegments.value = []
    currentPartial.value = ''
    setInputPreview(draft)
    voiceHint.value = '识别完成，正在发送...'
    sendFlashTimer = window.setTimeout(() => {
      isVoiceSending.value = false
      voiceSendingTranscript.value = ''
      setInputPreview('')
      emit('voice-send', draft)
      sendFlashTimer = null
    }, 260)
  }, delayMs)
}

const dispatchTranscriptDelta = (text: string, model?: string) => {
  const delta = text.trim()
  if (!delta) return
  clearSendFlash()
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
          lastModel = String(payload.realtime_model || speechStatus?.realtime_model || '')
          voiceHint.value = '语音电话已连接，正在使用管理端 API Key 中的千问实时语音配置'
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
    // Keep a slow network connection from accumulating an unbounded audio queue.
    if (ws.bufferedAmount > 512 * 1024) return
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
  voiceHint.value = '正在读取管理端语音服务配置...'
  try {
    await loadBackendSpeechStatus()
    voiceHint.value = '正在连接语音电话...'
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
  voiceHint.value = ''
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

.voice-call-panel--legacy {
  display: none;
}

.voice-orb-panel {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 10px;
}

.voice-orb-card {
  box-sizing: border-box;
  width: 100%;
  height: 0;
  min-height: 0;
  opacity: 0;
  overflow: hidden;
  padding: 0 16px;
  border: 1px solid transparent;
  border-radius: 18px;
  background:
    linear-gradient(135deg, rgba(239, 246, 255, 0.98), rgba(255, 241, 242, 0.96)) padding-box,
    linear-gradient(120deg, rgba(59, 130, 246, 0.35), rgba(239, 68, 68, 0.25)) border-box;
  box-shadow: 0 12px 28px rgba(30, 64, 175, 0.1);
  filter: blur(12px);
  transform: translateY(8px);
  transition: height 0.45s cubic-bezier(0.175, 0.885, 0.32, 1.1), min-height 0.45s cubic-bezier(0.175, 0.885, 0.32, 1.1), opacity 0.25s ease, filter 0.35s ease, transform 0.35s ease, padding 0.45s ease;
}

.voice-orb-card.is-open {
  height: 164px;
  min-height: 164px;
  opacity: 1;
  padding: 12px 16px;
  filter: blur(0);
  transform: translateY(0);
}

.voice-orb-card.is-error {
  background:
    linear-gradient(135deg, rgba(254, 242, 242, 0.98), rgba(255, 247, 237, 0.96)) padding-box,
    linear-gradient(120deg, rgba(239, 68, 68, 0.42), rgba(249, 115, 22, 0.3)) border-box;
}

.voice-orb-card__header {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #2563eb;
  font-size: 13px;
  font-weight: 700;
}

.voice-orb-card__state {
  margin-left: auto;
  font-size: 12px;
  font-weight: 600;
  background: linear-gradient(90deg, #ef4444, #3b82f6, #ef4444);
  background-size: 300% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: voice-orb-gradient 5s linear infinite;
}

.voice-orb-card__content {
  position: relative;
  height: 120px;
  margin-top: 7px;
  overflow: hidden;
  contain: layout paint;
  border-radius: 13px;
  background-image: linear-gradient(to top left, rgba(255, 0, 2, 0.13), rgba(59, 130, 246, 0.15));
  mask-image: linear-gradient(to bottom, transparent, #000 12%, #000 82%, transparent);
}

.voice-orb-card__content::after {
  position: absolute;
  content: '';
  inset: 0;
  pointer-events: none;
  background: repeating-conic-gradient(rgba(255, 255, 255, 0.2) 0.0000001%, rgba(232, 232, 232, 0.42) 0.000104%) 60% 60% / 600% 600%;
}

.voice-orb-card__messages {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 9px;
  padding: 16px 4px 28px;
  transform: translateY(0);
  transition: transform 180ms cubic-bezier(0.22, 1, 0.36, 1);
  will-change: transform;
}

.voice-orb-card__messages.is-sending {
  transform: translateY(-54px);
}

.voice-orb-card__hint,
.voice-orb-card__transcript {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  margin: 0;
  line-height: 1.6;
}

.voice-orb-card__hint {
  color: #475569;
  font-size: 13px;
  width: 85%;
  padding: 9px 10px;
  border-radius: 10px 10px 10px 2px;
  background: rgba(255, 255, 255, 0.46);
  flex: 0 0 auto;
}

.voice-orb-card__transcript {
  align-self: flex-end;
  width: fit-content;
  max-width: 92%;
  padding: 7px 10px;
  border-radius: 10px 10px 2px 10px;
  background: rgba(255, 255, 255, 0.7);
  color: #1e3a8a;
  font-size: 14px;
  box-shadow: 0 3px 10px rgba(59, 130, 246, 0.08);
  flex: 0 0 auto;
}

.voice-orb-card__hint span,
.voice-orb-card__transcript span {
  opacity: 0;
  transform: translateY(7px);
  animation: voice-orb-word-in 0.45s calc(var(--word-delay) + 80ms) both cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.voice-orb-dock {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 118px;
  overflow: visible;
}

.voice-orb,
.voice-orb-close {
  border: 0;
  cursor: pointer;
}

.voice-orb {
  position: relative;
  isolation: isolate;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 94px;
  height: 94px;
  border-radius: 50%;
  overflow: hidden;
  background: linear-gradient(145deg, #7c3aed 3%, #a855f7 34%, #ec4899 72%, #f9a8d4 100%);
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.96), 0 0 21px rgba(255, 255, 255, 0.98), 0 0 42px rgba(236, 72, 153, 0.32);
  transition: transform 0.18s ease, filter 0.18s ease, opacity 0.2s ease;
}

.voice-orb:hover:not(:disabled) {
  transform: scale(1.045);
  filter: saturate(1.08) brightness(1.04);
}

.voice-orb:active:not(:disabled) {
  transform: scale(0.94);
}

.voice-orb:disabled,
.voice-orb-close:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.voice-orb__ball,
.voice-orb__rings,
.voice-orb__lines,
.voice-orb__borders {
  position: absolute;
  border-radius: inherit;
  pointer-events: none;
}

.voice-orb__ball {
  inset: 0;
  z-index: -1;
  background: transparent;
  transform: scale(1);
}

.voice-orb__lines {
  display: none;
  z-index: -2;
  background: radial-gradient(ellipse at center, rgba(255, 255, 255, 0.75) 15%, #3b82f6 50%);
  clip-path: polygon(50% 25%, 65% 30%, 75% 42%, 75% 58%, 65% 70%, 50% 75%, 35% 70%, 25% 58%, 25% 42%, 35% 30%);
  animation: voice-orb-lines 4.8s both ease-in-out infinite;
}

.voice-orb__borders {
  display: none;
}

.voice-orb__rings {
  display: none;
}

.voice-orb.is-active .voice-orb__rings {
  display: none;
}

.voice-orb.is-muted {
  background: linear-gradient(145deg, #94a3b8, #64748b);
}

.voice-orb.is-connecting {
  animation: voice-orb-pulse 0.9s ease-in-out infinite alternate;
}

.voice-orb-icon {
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.voice-orb-icon--headphones {
  width: 18px;
  height: 18px;
}

.voice-orb-icon--mic {
  position: relative;
  z-index: 3;
  width: 30px;
  height: 30px;
  color: #fff;
  filter: drop-shadow(0 0 4px rgba(255, 255, 255, 0.8));
}

.voice-orb-icon--close {
  width: 17px;
  height: 17px;
  color: #64748b;
}

.voice-orb-close {
  position: absolute;
  left: calc(50% + 62px);
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 3px 9px rgba(15, 23, 42, 0.14);
}

@keyframes voice-orb-gradient {
  to { background-position: 300% 0; }
}

@keyframes voice-orb-word-in {
  to { opacity: 1; transform: translateY(0); }
}

@keyframes voice-orb-ring {
  0% { transform: rotateY(180deg) rotateX(180deg) rotateZ(180deg); }
  50% { transform: rotateY(360deg) rotateX(360deg) rotateZ(360deg) scale(1.1); }
  100% { transform: rotateY(540deg) rotateX(540deg) rotateZ(540deg); }
}

@keyframes voice-orb-lines {
  0%, 12%, 55%, 61%, 100% { clip-path: polygon(50% 25%, 65% 30%, 75% 42%, 75% 58%, 65% 70%, 50% 75%, 35% 70%, 25% 58%, 25% 42%, 35% 30%); }
  7%, 59% { clip-path: polygon(50% 25%, 100% 12%, 75% 42%, 85% 66%, 65% 70%, 50% 75%, 35% 70%, 15% 65%, 25% 42%, 0 12%); }
  9%, 57% { clip-path: polygon(50% 25%, 50% 0, 75% 42%, 75% 58%, 65% 70%, 50% 75%, 35% 70%, 25% 58%, 25% 42%, 50% 0); }
}

@keyframes voice-orb-pulse {
  to { transform: scale(1.035); }
}

@media (prefers-reduced-motion: reduce) {
  .voice-orb-card__state,
  .voice-orb-card__messages,
  .voice-orb-card__hint span,
  .voice-orb-card__transcript span,
  .voice-orb__rings,
  .voice-orb.is-connecting {
    animation: none;
  }
}

/* Uiverse "hot-dodo-99" source component, adapted only for the platform's full-width card. */
.container-vao {
  position: relative;
  width: 100%;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 18px;
  min-height: 90px;
  overflow: visible;
}

.container-chat-ia {
  box-sizing: border-box;
  width: 64px;
  height: 0;
  min-height: 0;
  opacity: 0;
  filter: blur(50px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0 0.5rem;
  border-radius: 2rem;
  box-shadow: 6px 6px 12px rgba(255, 0, 2, 0.1), -6px 6px 12px rgba(59, 130, 246, 0.1);
  gap: 6px;
  pointer-events: none;
  transition: width 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.1), height 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.1), min-height 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.1), padding 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.1), filter 0.42s ease, opacity 0.32s ease;
}

.container-vao.is-open .container-chat-ia {
  width: 100%;
  height: 118px;
  min-height: 118px;
  opacity: 1;
  filter: blur(0);
  padding: 0.5rem;
}

.container-vao.is-open {
  padding-bottom: 18px;
}

.container-title {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.25rem 0.5rem;
  gap: 6px;
}

.container-title svg {
  width: 20px;
  height: 20px;
  color: #ff0002;
  animation: animation-color-svg 8s 1s infinite both;
}

.container-title .text-title {
  display: flex;
  gap: 4px;
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  background-image: linear-gradient(to left, #ff0002 0% 20%, #3b82f6 50%, #ff0002 80% 100%);
  background-clip: text;
  -webkit-background-clip: text;
  color: transparent;
  background-size: 800px;
  animation: animation-color-text 8s infinite linear;
}

.voice-source-state {
  margin-left: auto;
  color: #ef4444;
  font-size: 12px;
  font-weight: 700;
}

.container-chat {
  position: relative;
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  width: 100%;
  font-size: 13px;
  background-image: linear-gradient(to top left, rgba(255, 0, 2, 0.22), rgba(59, 130, 246, 0.22));
  border-radius: 1.5rem;
  overflow: hidden;
}

.container-chat::after {
  position: absolute;
  content: '';
  inset: 0;
  background: repeating-conic-gradient(rgba(255, 255, 255, 0.2) 0.0000001%, rgba(232, 232, 232, 0.8) 0.000104%) 60% 60% / 600% 600%;
  pointer-events: none;
}

.container-chat-limit {
  display: flex;
  height: 100%;
  overflow: hidden;
  -webkit-mask: linear-gradient(0deg, white 85%, transparent 95% 100%);
  mask: linear-gradient(0deg, white 85%, transparent 95% 100%);
  z-index: 1;
}

.chats {
  display: flex;
  width: 100%;
  flex-direction: column;
  padding: 0.5rem 0.75rem;
  gap: 0.25rem;
  transform: translateY(0);
  transition: transform 180ms cubic-bezier(0.22, 1, 0.36, 1);
}

.chats.is-sending { transform: translateY(-48px); }

.chat-user { display: flex; justify-content: flex-start; }
.chat-ia { display: flex; }

.chat-user p,
.chat-ia p {
  opacity: 0;
  transform: translateY(10px);
  width: 100%;
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  line-height: 1.3;
  margin: 0;
  animation: animation-chat 0.5s both cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.chat-user p {
  justify-content: flex-start;
  padding: 0.375rem 0;
  color: #475569;
  background: transparent;
}

.chat-ia p { justify-content: flex-start; padding: 0.375rem 0; color: #393754; }

.chat-user p span,
.chat-ia p span {
  opacity: 0;
  transform: translateY(10px);
  display: block;
  animation: animation-chat 0.55s calc(var(--word-delay) + 20ms) both cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.orb {
  position: relative;
  width: 58px;
  height: 58px;
  flex: 0 0 58px;
  border: 0;
  padding: 0;
  border-radius: 50%;
  background: transparent;
  cursor: pointer;
  filter: drop-shadow(0 0 4px rgba(255, 255, 255, 1)) drop-shadow(0 0 12px rgba(255, 255, 255, 1)) drop-shadow(0 0 12px rgba(145, 71, 255, 0.3)) drop-shadow(0 0 5px rgba(255, 0, 0, 0.3));
  transform: scale(1);
  transition: all 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.container-vao.is-open .orb {
  filter: drop-shadow(0 0 12px rgba(145, 71, 255, 0.3)) drop-shadow(0 0 5px rgba(255, 0, 0, 0.3));
  transform: scale(1);
}

.orb:hover:not(:disabled) { transform: scale(1.08); }
.container-vao.is-open .orb:hover:not(:disabled) { transform: scale(1.1); }
.orb:active:not(:disabled) { transform: scale(1.1); }
.orb:disabled { cursor: not-allowed; opacity: 0.45; }

.icons {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #fff;
  z-index: 3;
}

.icons .svg { width: 24px; height: 24px; opacity: 0.75; transition: all 0.3s ease-in-out; }
.icons .close { opacity: 0; }

.ball {
  position: absolute;
  inset: 0;
  display: flex;
  width: 58px;
  height: 58px;
  border-radius: 50px;
  background-color: #ff0002;
  filter: url(#voice-gooey);
  animation: circle2 4.2s ease-in-out infinite;
}

.container-lines {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 100px;
  height: 100px;
  transform: translate(-50%, -50%);
  background-image: radial-gradient(ellipse at center, rgba(255, 255, 255, 0.75) 15%, #3b82f6 50%);
  clip-path: polygon(50% 25%, 65% 30%, 75% 42%, 75% 58%, 65% 70%, 50% 75%, 35% 70%, 26% 58%, 25% 42%, 35% 30%);
  animation: animation-ball 15s both ease infinite;
  pointer-events: none;
}

.container-rings {
  aspect-ratio: 1;
  border-radius: 50%;
  position: absolute;
  inset: 0;
  perspective: 11rem;
}

.container-rings::before,
.container-rings::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 6px solid transparent;
  mask: linear-gradient(#fff 0 0) padding-box, linear-gradient(#fff 0 0);
  -webkit-mask: linear-gradient(#fff 0 0) padding-box, linear-gradient(#fff 0 0);
  mask-composite: exclude;
  -webkit-mask-composite: xor;
  background: linear-gradient(white, blue, magenta, violet, lightyellow) border-box;
}

.container-rings::before { animation: ring180 10s linear infinite; }
.container-rings::after { animation: ring90 10s linear infinite; }
.gooey-filter { position: absolute; width: 0; height: 0; pointer-events: none; }

.voice-source-close {
  position: absolute;
  left: calc(50% + 48px);
  bottom: 17px;
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 50%;
  background: #fff;
  color: #64748b;
  font-size: 22px;
  line-height: 1;
  box-shadow: 0 3px 9px rgba(15, 23, 42, 0.14);
  cursor: pointer;
}

@keyframes circle2 { 0% { transform: scale(1.08); } 15% { transform: scale(1.11); } 30% { transform: scale(1.06); } 45% { transform: scale(1.03); } 60% { transform: scale(1.06); } 85% { transform: scale(1.11); } 100% { transform: scale(1.08); } }
@keyframes animation-color-svg { 0%, 30% { color: #ff0002; } 15% { color: #3b82f6; } }
@keyframes animation-color-text { 0% { background-position: -800px; } 50% { background-position: 0; } }
@keyframes animation-chat { to { opacity: 1; transform: translateY(0); } }
@keyframes animation-ball { 0%, 12%, 55%, 61%, 100% { clip-path: polygon(50% 25%, 65% 30%, 75% 42%, 75% 58%, 65% 70%, 50% 75%, 35% 70%, 26% 58%, 25% 42%, 35% 30%); } 2%, 9%, 57% { clip-path: polygon(50% 25%, 50% 0, 75% 42%, 75% 58%, 65% 70%, 50% 75%, 35% 70%, 26% 58%, 25% 42%, 50% 0); } 4% { clip-path: polygon(50% 25%, 70% 0, 75% 42%, 85% 66%, 65% 100%, 50% 75%, 35% 100%, 15% 65%, 25% 42%, 30% 0); } 7%, 59% { clip-path: polygon(50% 25%, 100% 12%, 75% 42%, 85% 66%, 65% 70%, 50% 75%, 35% 70%, 15% 65%, 25% 42%, 0 12%); } }
@keyframes ring180 { 0% { transform: rotateY(180deg) rotateX(180deg) rotateZ(180deg); } 50% { transform: rotateY(360deg) rotateX(360deg) rotateZ(360deg) scale(1.1); } 100% { transform: rotateY(540deg) rotateX(540deg) rotateZ(540deg); } }
@keyframes ring90 { 0% { transform: rotateY(90deg) rotateX(90deg) rotateZ(90deg); } 50% { transform: rotateY(270deg) rotateX(270deg) rotateZ(270deg) scale(1.1); } 100% { transform: rotateY(450deg) rotateX(450deg) rotateZ(450deg); } }

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
