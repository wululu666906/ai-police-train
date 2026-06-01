import { onBeforeUnmount, ref } from 'vue'
import { createSpeechProvider, getActiveSpeechProviderLabel } from '../services/speech'
import { fetchIFlytekStatus } from '../services/speech/iflytekAuth'
import { resetIFlytekConfigCache } from '../services/speech/iflytekSpeechProvider'
import type { SpeechRecognitionStatus } from '../services/speech'
import { speechConfig } from '../config/speech'
import { WebSpeechProvider } from '../services/speech/webSpeechProvider'

export const useSpeechInput = () => {
  const provider = ref(createSpeechProvider())
  const providerLabel = ref(getActiveSpeechProviderLabel(provider.value))

  const status = ref<SpeechRecognitionStatus>('idle')
  const interimText = ref('')
  const finalBuffer = ref('')
  const errorMessage = ref('')
  const sessionFinalized = ref(false)

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
      return '语音听写需要 HTTPS 访问（请使用 https:// 打开系统并在浏览器中信任证书）'
    }
    if (errorMessage.value) return errorMessage.value
    if (providerLabel.value === '听写不可用') {
      return '当前环境不支持听写，请检查是否已登录或讯飞配置是否完整'
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
          const chunk = text.trim()
          if (!chunk) return
          if (!finalBuffer.value.endsWith(chunk)) {
            finalBuffer.value += chunk
          }
          interimText.value = ''
          handlers.onAppendFinal?.(chunk)
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

  const stopListening = () => {
    const pendingInterim = sessionFinalized.value ? '' : interimText.value
    provider.value.stop()
    status.value = 'idle'
    interimText.value = ''
    sessionFinalized.value = false
    return pendingInterim
  }

  const cancelListening = () => {
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
    prepareProviderForListening,
    startListening,
    stopListening,
    cancelListening,
    getLivePreview,
    resetSession,
  }
}
