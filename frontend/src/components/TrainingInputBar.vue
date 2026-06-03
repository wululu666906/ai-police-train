<template>
  <div class="training-input-bar">
    <div v-if="inputMode === 'voice'" class="mode-switch">
      <button type="button" class="mode-switch__link" :disabled="disabled || inVoiceCall" @click="inputMode = 'typing'">
        切换打字输入
      </button>
    </div>
    <div v-else class="mode-switch">
      <button type="button" class="mode-switch__link" :disabled="disabled" @click="inputMode = 'voice'">
        切换语音说话
      </button>
    </div>

    <VoiceCallDock
      v-if="inputMode === 'voice'"
      :in-call="inVoiceCall"
      :is-muted="isMicMuted"
      :is-ending="isEndingCall"
      :disabled="disabled || loading"
      :live-text="liveTranscript"
      :idle-hint="voiceIdleHint"
      @toggle-mic="onToggleMic"
      @close="onCloseVoice"
    />

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
import { onBeforeUnmount, ref, watch } from 'vue'
import { showToast } from 'vant'
import { useSpeechInput } from '../composables/useSpeechInput'
import {
  acquireSharedMicrophoneLease,
  type MicrophoneLease,
} from '../composables/useSharedMicrophone'
import VoiceCallDock from './VoiceCallDock.vue'

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
    placeholder: '请输入执法话术、追问内容或安抚表达...',
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  send: []
  'voice-send': [transcript: string]
}>()

type InputMode = 'voice' | 'typing'

const MIN_UTTERANCE_LEN = 2

const inputMode = ref<InputMode>('voice')
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const inVoiceCall = ref(false)
const isMicMuted = ref(false)
const isEndingCall = ref(false)
const liveTranscript = ref('')
const voiceIdleHint = '点击麦克风开始，说完自动发送'
const pendingUtterances = ref<string[]>([])
let microphoneLease: MicrophoneLease | null = null
let micStream: MediaStream | null = null

const speech = useSpeechInput()

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

const releaseMicrophone = () => {
  microphoneLease?.release()
  microphoneLease = null
  micStream = null
}

const setMicTracksEnabled = (enabled: boolean) => {
  micStream?.getAudioTracks().forEach((track) => {
    track.enabled = enabled
  })
  isMicMuted.value = !enabled
}

const emitSend = () => {
  if (!props.modelValue.trim() || props.disabled || props.loading) return
  emit('send')
  requestAnimationFrame(() => resizeTextarea())
}

const isUtteranceValid = (transcript: string) => transcript.trim().length >= MIN_UTTERANCE_LEN

const drainPendingUtterances = () => {
  if (!inVoiceCall.value || props.disabled || isEndingCall.value || props.loading) return
  while (pendingUtterances.value.length > 0) {
    if (props.loading) break
    const next = pendingUtterances.value.shift()
    if (!next || !isUtteranceValid(next)) continue
    liveTranscript.value = ''
    emit('voice-send', next)
    if (props.loading) break
  }
  if (!props.loading && pendingUtterances.value.length) {
    liveTranscript.value = '等待上一条回复后再发送…'
  }
}

watch(
  () => props.loading,
  (loading) => {
    if (!loading) {
      drainPendingUtterances()
    }
  }
)

const dispatchUtterance = (transcript: string) => {
  if (!inVoiceCall.value || isMicMuted.value || !isUtteranceValid(transcript)) {
    return
  }

  if (props.loading || props.disabled) {
    pendingUtterances.value.push(transcript)
    liveTranscript.value = '等待上一条回复后再发送…'
    return
  }

  liveTranscript.value = ''
  emit('voice-send', transcript)
}

const ensureMicReady = async () => {
  const providerReady = await speech.prepareProviderForListening()
  if (!providerReady || !speech.isSupported()) {
    showToast(speech.getUnsupportedReason() || speech.errorMessage.value || '当前环境不支持语音')
    return false
  }

  if (!microphoneLease) {
    try {
      const lease = await acquireSharedMicrophoneLease()
      microphoneLease = lease
      micStream = lease.stream
    } catch {
      showToast('无法访问麦克风，请检查浏览器权限')
      return false
    }
  }

  return true
}

const startVoiceCallSession = async () => {
  if (props.disabled || props.loading || inVoiceCall.value) return
  if (!(await ensureMicReady())) return

  pendingUtterances.value = []
  liveTranscript.value = ''
  isMicMuted.value = false
  setMicTracksEnabled(true)
  inVoiceCall.value = true
  speech.resetSession()

  speech.startVoiceCall(
    {
      onInterim: (text) => {
        if (!inVoiceCall.value || isMicMuted.value) return
        liveTranscript.value = text
      },
      onUtteranceEnd: (transcript) => {
        dispatchUtterance(transcript)
      },
      onError: () => {
        inVoiceCall.value = false
        isEndingCall.value = false
        pendingUtterances.value = []
        releaseMicrophone()
        showToast(speech.errorMessage.value || '语音识别失败')
      },
    },
    { mediaStream: micStream || undefined }
  )
}

const onToggleMic = async () => {
  if (props.disabled || props.loading || isEndingCall.value) return

  if (!inVoiceCall.value) {
    await startVoiceCallSession()
    return
  }

  setMicTracksEnabled(isMicMuted.value)
  if (isMicMuted.value) {
    liveTranscript.value = '麦克风已关闭'
  }
}

const onCloseVoice = async () => {
  if (!inVoiceCall.value || props.disabled || props.loading || isEndingCall.value) return

  isEndingCall.value = true
  setMicTracksEnabled(true)

  try {
    const tail = await speech.hangUpVoiceCall()
    inVoiceCall.value = false
    liveTranscript.value = ''
    pendingUtterances.value = []
    releaseMicrophone()

    if (tail && isUtteranceValid(tail) && !props.loading) {
      emit('voice-send', tail)
    }
  } catch {
    showToast('结束通话失败，请重试')
    speech.cancelVoiceCall()
    inVoiceCall.value = false
    liveTranscript.value = ''
    pendingUtterances.value = []
    releaseMicrophone()
  } finally {
    isEndingCall.value = false
  }
}

onBeforeUnmount(() => {
  if (inVoiceCall.value) {
    speech.cancelVoiceCall()
    inVoiceCall.value = false
  }
  releaseMicrophone()
})
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
  font-size: 15px;
  line-height: 1.45;
  color: #0f172a;
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












