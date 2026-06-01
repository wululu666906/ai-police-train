<template>
  <div class="training-input-bar">
    <div class="composer-row">
      <VoiceRecordingBar
        v-if="isVoiceActive"
        ref="voiceBarRef"
        :elapsed-label="voiceElapsedLabel"
        @cancel="cancelVoiceListening"
        @confirm="confirmVoiceListening"
      />

      <div v-else class="input-shell" :class="{ 'is-disabled': disabled }">
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
        <button
          type="button"
          class="mic-btn"
          :disabled="disabled || !speech.isSupported()"
          title="点击开始听写，说完约 2 秒自动结束"
          @click="startVoiceListening"
        >
          <svg class="mic-btn__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <rect x="9" y="3" width="6" height="11" rx="3" stroke="currentColor" stroke-width="1.7" />
            <path
              d="M6 11a6 6 0 0 0 12 0"
              stroke="currentColor"
              stroke-width="1.7"
              stroke-linecap="round"
            />
            <path d="M12 17v3" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
          </svg>
        </button>
      </div>

      <button
        type="button"
        class="send-btn-card"
        :disabled="!modelValue.trim() || disabled || loading || isVoiceActive"
        @click="emitSend"
      >
        {{ loading ? '发送中' : '发送' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref } from 'vue'
import { showToast } from 'vant'
import { useSpeechInput } from '../composables/useSpeechInput'
import {
  acquireSharedMicrophoneLease,
  type MicrophoneLease,
} from '../composables/useSharedMicrophone'
import VoiceRecordingBar from './VoiceRecordingBar.vue'

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
}>()

const textareaRef = ref<HTMLTextAreaElement | null>(null)
const isVoiceActive = ref(false)
const voiceSessionBase = ref('')
const recognizedInSession = ref('')
const lastSessionDisplay = ref('')
const voiceElapsedSeconds = ref(0)
let voiceTimerId: ReturnType<typeof setInterval> | null = null
let microphoneLease: MicrophoneLease | null = null

const speech = useSpeechInput()
const voiceBarRef = ref<InstanceType<typeof VoiceRecordingBar> | null>(null)

const voiceElapsedLabel = computed(() => {
  const total = voiceElapsedSeconds.value
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
})

const appendText = (base: string, chunk: string) => {
  const prefix = base.trim()
  const addition = chunk.trim()
  if (!addition) return prefix
  if (!prefix) return addition
  const joiner = /[，。！？；：、]$/.test(prefix) ? '' : ' '
  return `${prefix}${joiner}${addition}`
}

const updateModel = (value: string) => {
  emit('update:modelValue', value)
}

const onTextInput = (event: Event) => {
  updateModel((event.target as HTMLTextAreaElement).value)
  resizeTextarea()
}

const resizeTextarea = () => {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 120)}px`
}

const startVoiceTimer = () => {
  stopVoiceTimer()
  voiceElapsedSeconds.value = 0
  voiceTimerId = setInterval(() => {
    voiceElapsedSeconds.value += 1
  }, 1000)
}

const stopVoiceTimer = () => {
  if (voiceTimerId) {
    clearInterval(voiceTimerId)
    voiceTimerId = null
  }
  voiceElapsedSeconds.value = 0
}

const stopMicVisual = () => {
  voiceBarRef.value?.stopWaveformCapture()
}

const releaseVoiceMicrophone = () => {
  stopMicVisual()
  microphoneLease?.release()
  microphoneLease = null
}

const emitSend = () => {
  if (!props.modelValue.trim() || props.disabled || props.loading) return
  if (isVoiceActive.value) {
    stopVoiceListening(false)
  }
  emit('send')
  requestAnimationFrame(() => resizeTextarea())
}

const startVoiceListening = async () => {
  const providerReady = await speech.prepareProviderForListening()
  if (!providerReady || !speech.isSupported()) {
    showToast(speech.getUnsupportedReason() || speech.errorMessage.value || '当前环境不支持语音听写')
    return
  }

  if (speech.providerLabel.value !== '科大讯飞听写') {
    showToast(`当前使用${speech.providerLabel.value}，如需讯飞请确认已登录且 backend/.env 已配置密钥`)
  }

  let mediaStream: MediaStream
  try {
    const lease = await acquireSharedMicrophoneLease()
    microphoneLease = lease
    mediaStream = lease.stream
  } catch {
    showToast('无法访问麦克风，请检查浏览器权限')
    return
  }

  voiceSessionBase.value = props.modelValue
  recognizedInSession.value = ''
  lastSessionDisplay.value = ''
  isVoiceActive.value = true
  speech.resetSession()
  startVoiceTimer()

  await nextTick()
  voiceBarRef.value?.startWaveformDisplay()

  const composeModel = (sessionText: string) => appendText(voiceSessionBase.value, sessionText)

  const applySessionDisplay = (sessionDisplay: string) => {
    const next = sessionDisplay.trim()
    if (!next) return

    lastSessionDisplay.value = next
    recognizedInSession.value = next
    updateModel(composeModel(next))
  }

  speech.startListening(
    {
      onInterim: (sessionDisplay) => {
        if (!isVoiceActive.value) return
        applySessionDisplay(sessionDisplay)
        requestAnimationFrame(() => resizeTextarea())
      },
      onAppendFinal: (chunk) => {
        if (!isVoiceActive.value) return
        const trimmed = chunk.trim()
        if (!trimmed) return
        applySessionDisplay(
          recognizedInSession.value ? appendText(recognizedInSession.value, trimmed) : trimmed
        )
        requestAnimationFrame(() => resizeTextarea())
      },
      onAutoEnd: () => {
        if (isVoiceActive.value) {
          stopVoiceListening(false)
        }
      },
      onError: () => {
        if (!isVoiceActive.value) return
        isVoiceActive.value = false
        stopVoiceTimer()
        releaseVoiceMicrophone()
        showToast(speech.errorMessage.value || '语音听写失败')
      },
    },
    {
      mediaStream,
      onAudioLevel: (level) => {
        voiceBarRef.value?.pushAudioLevel(level)
      },
    }
  )
}

const stopVoiceListening = (showEmptyHint: boolean) => {
  if (!isVoiceActive.value) return

  const pendingInterim = speech.stopListening()
  isVoiceActive.value = false
  stopVoiceTimer()
  releaseVoiceMicrophone()

  const interim = pendingInterim.trim()
  if (interim) {
    const merged = appendText(voiceSessionBase.value, interim)
    updateModel(merged)
    voiceSessionBase.value = merged
    requestAnimationFrame(() => resizeTextarea())
  }

  if (showEmptyHint && !props.modelValue.trim()) {
    showToast('未识别到语音内容，请重试')
  }
}

const cancelVoiceListening = () => {
  if (!isVoiceActive.value) return

  speech.cancelListening()
  isVoiceActive.value = false
  stopVoiceTimer()
  releaseVoiceMicrophone()
  updateModel(voiceSessionBase.value)
  recognizedInSession.value = ''
  lastSessionDisplay.value = ''
}

const confirmVoiceListening = () => {
  stopVoiceListening(true)
}

onBeforeUnmount(() => {
  if (isVoiceActive.value) {
    speech.cancelListening()
    isVoiceActive.value = false
  }
  stopVoiceTimer()
  releaseVoiceMicrophone()
})
</script>

<style scoped>
.training-input-bar {
  display: flex;
  flex-direction: column;
  gap: 8px;
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
  padding: 6px 6px 6px 12px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.06);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.input-shell:focus-within {
  border-color: rgba(18, 183, 245, 0.35);
  box-shadow: 0 0 0 2px rgba(18, 183, 245, 0.08);
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
  padding: 4px 8px 4px 0;
  background: transparent;
  font-size: 15px;
  line-height: 1.45;
  color: #0f172a;
  outline: none;
}

.input-box::placeholder {
  color: #94a3b8;
}

.input-box:disabled {
  color: #94a3b8;
  cursor: not-allowed;
}

.mic-btn {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  margin-bottom: 1px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #64748b;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s ease, color 0.15s ease;
}

.mic-btn__icon {
  width: 22px;
  height: 22px;
}

.mic-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
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
  line-height: 1;
  cursor: pointer;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(18, 183, 245, 0.28);
  transition: background 0.15s ease, opacity 0.15s ease, transform 0.12s ease;
}

.send-btn-card:not(:disabled):active {
  transform: scale(0.98);
  background: #0fa8e0;
}

.send-btn-card:disabled {
  background: #a8ddf3;
  color: rgba(255, 255, 255, 0.92);
  box-shadow: none;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .send-btn-card {
    min-width: 60px;
    padding: 0 14px;
  }
}
</style>
