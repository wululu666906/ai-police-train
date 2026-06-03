import { onBeforeUnmount, ref } from 'vue'
import { createSpeechProvider, getActiveSpeechProviderLabel } from '../services/speech'
import { fetchIFlytekStatus } from '../services/speech/iflytekAuth'
import { IFlytekSpeechProvider, resetIFlytekConfigCache } from '../services/speech/iflytekSpeechProvider'
import type { SpeechRecognitionStatus } from '../services/speech'
import { speechConfig } from '../config/speech'
import { WebSpeechProvider } from '../services/speech/webSpeechProvider'
import { normalizeTranscript } from '../utils/normalizeTranscript'

export const useSpeechInput = () => {
  const provider = ref(createSpeechProvider())
  const providerLabel = ref(getActiveSpeechProviderLabel(provider.value))

  const status = ref<SpeechRecognitionStatus>('idle')
  const interimText = ref('')
  const finalBuffer = ref('')
  const errorMessage = ref('')
  const sessionFinalized = ref(false)
  const voiceCallActive = ref(false)

  const appendFinalChunk = (chunk: string) => {
    const trimmed = chunk.trim()
    if (!trimmed) return
    if (!finalBuffer.value.endsWith(trimmed)) {
      finalBuffer.value += trimmed
    }
    interimText.value = ''
  }

  /** 每次听写前刷新：避免「先打开页面未登录 → 永久走浏览器听写」 */
  const prepareProviderForListening = async () => {
    if (speechConfig.provider === 'web') {
      provider.value = new WebSpeechProvider()
      providerLabel.value = '浏览器听写'
      return provider.value.isSupported()
    }

    resetIFlytekConfigCache()

    try {
      const iflytekStatus = await fetchIFlytekStatus()
      if (iflytekStatus.configured) {
        provider.value = createSpeechProvider()
        providerLabel.value = '科大讯飞听写'
        return true
      }
    } catch {
      // fallback below
    }

    if (speechConfig.requireIflytekInProd) {
      providerLabel.value = '听写不可用'
      errorMessage.value = '语音训练需要配置科大讯飞服务，请联系管理员'
      return false
    }

    const webProvider = new WebSpeechProvider()
    if (webProvider.isSupported()) {
      provider.value = webProvider
      providerLabel.value = '浏览器听写（讯飞未配齐）'
      return true
    }

    providerLabel.value = '听写不可用'
    return false
  }

  void prepareProviderForListening()

  const isSupported = () => {
    if (typeof window !== 'undefined' && !window.isSecureContext) {
      return false
    }
    return provider.value.isSupported()
  }

  const getUnsupportedReason = () => {
    if (typeof window !== 'undefined' && !window.isSecureContext) {
      return '语音功能需要 HTTPS 访问（请使用 https:// 打开系统）'
    }
    if (errorMessage.value) return errorMessage.value
    if (providerLabel.value === '听写不可用') {
      return '当前环境不支持语音，请检查是否已登录或讯飞配置是否完整'
    }
    return ''
  }

  const resetSession = () => {
    interimText.value = ''
    finalBuffer.value = ''
    errorMessage.value = ''
    sessionFinalized.value = false
  }

  const startListening = (
    handlers: {
      onAppendFinal?: (chunk: string) => void
      onInterim?: (text: string) => void
      onAutoEnd?: () => void
      onError?: () => void
    },
    options?: { mediaStream?: MediaStream; onAudioLevel?: (level: number) => void }
  ) => {
    if (status.value === 'listening') return false

    resetSession()

    provider.value.start(
      {
        lang: 'zh-CN',
        continuous: true,
        interimResults: true,
        mediaStream: options?.mediaStream,
        sessionMode: 'dictation',
      },
      {
        onStatusChange: (next) => {
          status.value = next
        },
        onInterim: (text) => {
          interimText.value = text
          const sessionDisplay =
            provider.value.name === 'web' ? `${finalBuffer.value}${text}`.trim() : text
          handlers.onInterim?.(sessionDisplay)
        },
        onFinal: (text) => {
          sessionFinalized.value = true
          appendFinalChunk(text)
          handlers.onAppendFinal?.(text.trim())
        },
        onAutoEnd: () => {
          handlers.onAutoEnd?.()
        },
        onAudioLevel: (level) => {
          options?.onAudioLevel?.(level)
        },
        onError: (message) => {
          errorMessage.value = message
          status.value = 'error'
          handlers.onError?.()
        },
      }
    )

    return true
  }

  const startVoiceCall = (
    handlers: {
      onInterim?: (text: string) => void
      onUtteranceEnd?: (text: string) => void
      onError?: () => void
    },
    options?: { mediaStream?: MediaStream; onAudioLevel?: (level: number) => void }
  ) => {
    if (status.value === 'listening') return false

    resetSession()
    voiceCallActive.value = true

    provider.value.start(
      {
        lang: 'zh-CN',
        continuous: true,
        interimResults: true,
        mediaStream: options?.mediaStream,
        sessionMode: 'voice_call',
      },
      {
        onStatusChange: (next) => {
          status.value = next
        },
        onInterim: (text) => {
          interimText.value = text
          const sessionDisplay =
            provider.value.name === 'web'
              ? `${finalBuffer.value}${text}`.trim()
              : text || finalBuffer.value
          handlers.onInterim?.(sessionDisplay)
        },
        onFinal: (text) => {
          appendFinalChunk(text)
          handlers.onInterim?.(getLivePreview() || text.trim())
        },
        onUtteranceEnd: (text) => {
          const utterance = normalizeTranscript(text)
          if (!utterance) return
          finalBuffer.value = ''
          interimText.value = ''
          handlers.onUtteranceEnd?.(utterance)
        },
        onAudioLevel: (level) => {
          options?.onAudioLevel?.(level)
        },
        onError: (message) => {
          errorMessage.value = message
          status.value = 'error'
          voiceCallActive.value = false
          handlers.onError?.()
        },
      }
    )

    return true
  }

  /** 结束通话：仅收尾未发送片段，不重复已自动发送的内容 */
  const hangUpVoiceCall = async (): Promise<string> => {
    voiceCallActive.value = false

    if (provider.value instanceof IFlytekSpeechProvider) {
      const pending = provider.value.peekPendingUtterance()
      provider.value.abort()
      status.value = 'idle'
      resetSession()
      const webTail = `${finalBuffer.value}${interimText.value}`.trim()
      return normalizeTranscript(pending || webTail)
    }

    if (provider.value.name === 'web') {
      const webProvider = provider.value as WebSpeechProvider
      const pending = webProvider.peekPendingUtterance?.() ?? ''
      webProvider.abort()
      status.value = 'idle'
      const raw = pending || `${finalBuffer.value}${interimText.value}`.trim()
      resetSession()
      return normalizeTranscript(raw)
    }

    provider.value.abort()
    status.value = 'idle'
    const raw = `${finalBuffer.value}${interimText.value}`.trim()
    resetSession()
    return normalizeTranscript(raw)
  }

  const endVoiceCall = async (): Promise<string> => {
    voiceCallActive.value = false

    if (provider.value instanceof IFlytekSpeechProvider) {
      const raw = await provider.value.finalizeListening()
      status.value = 'idle'
      resetSession()
      return normalizeTranscript(raw)
    }

    const pendingInterim = sessionFinalized.value ? '' : interimText.value
    provider.value.stop()
    status.value = 'idle'
    const raw = `${finalBuffer.value}${pendingInterim}`.trim()
    resetSession()
    return normalizeTranscript(raw)
  }

  const cancelVoiceCall = () => {
    voiceCallActive.value = false
    provider.value.abort()
    status.value = 'idle'
    resetSession()
  }

  const stopListening = () => {
    const pendingInterim = sessionFinalized.value ? '' : interimText.value
    provider.value.stop()
    status.value = 'idle'
    interimText.value = ''
    sessionFinalized.value = false
    return pendingInterim
  }

  const cancelListening = () => {
    voiceCallActive.value = false
    provider.value.abort()
    status.value = 'idle'
    interimText.value = ''
    finalBuffer.value = ''
  }

  const getLivePreview = () => {
    const parts = [finalBuffer.value, interimText.value].map((item) => item.trim()).filter(Boolean)
    return parts.join('')
  }

  onBeforeUnmount(() => {
    voiceCallActive.value = false
    provider.value.abort()
  })

  return {
    providerLabel,
    isSupported,
    getUnsupportedReason,
    status,
    interimText,
    finalBuffer,
    errorMessage,
    voiceCallActive,
    prepareProviderForListening,
    startListening,
    startVoiceCall,
    hangUpVoiceCall,
    endVoiceCall,
    cancelVoiceCall,
    stopListening,
    cancelListening,
    getLivePreview,
    resetSession,
  }
}
