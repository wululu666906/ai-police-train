<template>
  <div class="training-input-bar">
    <div v-if="voicePreview" class="voice-preview">
      <span class="voice-preview__label">听写中</span>
      <span class="voice-preview__text">{{ voicePreview }}</span>
    </div>

    <div class="composer-row">
      <div class="input-shell" :class="{ 'is-listening': isVoiceActive, 'is-disabled': disabled }">
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
          :class="{ 'is-active': isVoiceActive }"
          :disabled="disabled || !speech.isSupported()"
          :title="isVoiceActive ? '点击可提前结束听写' : '点击开始听写，说完约 2 秒自动结束'"
          @click="toggleVoiceListening"
        >
          <van-icon name="audio" size="22" color="currentColor" />
        </button>
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
import { computed, onBeforeUnmount, ref } from 'vue'
import { showToast } from 'vant'
import { useSpeechInput } from '../composables/useSpeechInput'

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

const speech = useSpeechInput()

const voicePreview = computed(() => {
  if (!isVoiceActive.value) return ''
  return speech.getLivePreview() || speech.interimText.value || '正在聆听，点击麦克风结束...'
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

const emitSend = () => {
  if (!props.modelValue.trim() || props.disabled || props.loading) return
  if (isVoiceActive.value) {
    stopVoiceListening(false)
  }
  emit('send')
  requestAnimationFrame(() => resizeTextarea())
}

const startVoiceListening = () => {
  if (props.disabled || !speech.isSupported()) {
    showToast(speech.getUnsupportedReason() || speech.errorMessage.value || '当前环境不支持语音听写')
    return
  }

  voiceSessionBase.value = props.modelValue
  recognizedInSession.value = ''
  lastSessionDisplay.value = ''
  isVoiceActive.value = true
  speech.resetSession()

  const composeModel = (sessionText: string) => appendText(voiceSessionBase.value, sessionText)

  const applySessionDisplay = (sessionDisplay: string) => {
    const next = sessionDisplay.trim()
    if (!next) return

    const prev = lastSessionDisplay.value
    if (prev) {
      if (next.length < prev.length && !prev.startsWith(next) && !next.startsWith(prev)) {
        const isPunctOnly = /^[。！？，、；：…．.?!,;:]+$/.test(next)
        if (isPunctOnly) {
          const merged = appendText(prev, next)
          lastSessionDisplay.value = merged
          recognizedInSession.value = merged
          updateModel(composeModel(merged))
          requestAnimationFrame(() => resizeTextarea())
        }
        return
      }
    }

    lastSessionDisplay.value = next
    recognizedInSession.value = next
    updateModel(composeModel(next))
    requestAnimationFrame(() => resizeTextarea())
  }

  speech.startListening({
    onInterim: (sessionDisplay) => {
      if (!isVoiceActive.value) return
      applySessionDisplay(sessionDisplay)
    },
    onAppendFinal: (chunk) => {
      if (!isVoiceActive.value) return
      const trimmed = chunk.trim()
      if (!trimmed) return
      let merged = recognizedInSession.value
      if (!merged.includes(trimmed)) {
        merged = appendText(merged, trimmed)
      }
      recognizedInSession.value = merged
      lastSessionDisplay.value = merged
      updateModel(composeModel(merged))
      requestAnimationFrame(() => resizeTextarea())
    },
    onAutoEnd: () => {
      if (isVoiceActive.value) {
        stopVoiceListening(false)
      }
    },
  })
}

const stopVoiceListening = (showEmptyHint: boolean) => {
  if (!isVoiceActive.value) return

  const pendingInterim = speech.stopListening()
  isVoiceActive.value = false

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

const toggleVoiceListening = () => {
  if (isVoiceActive.value) {
    stopVoiceListening(true)
    return
  }
  startVoiceListening()
}

onBeforeUnmount(() => {
  if (isVoiceActive.value) {
    stopVoiceListening(false)
  }
})
</script>

<style scoped>
.training-input-bar {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.voice-preview {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(18, 183, 245, 0.1);
  color: #0e9fe0;
  font-size: 13px;
  line-height: 1.5;
}

.voice-preview__label {
  flex-shrink: 0;
  font-weight: 700;
}

.voice-preview__text {
  flex: 1;
  color: #0f172a;
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

.input-shell.is-listening {
  border-color: rgba(18, 183, 245, 0.55);
  background: #f4fbff;
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

.mic-btn.is-active {
  background: rgba(18, 183, 245, 0.16);
  color: #12b7f5;
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
