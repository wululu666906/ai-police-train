import { speechConfig } from '../../config/speech'
import { QwenRealtimeSpeechProvider } from './qwenRealtimeSpeechProvider'
import type { SpeechRecognitionProvider } from './types'
import { WebSpeechProvider } from './webSpeechProvider'

export type { SpeechRecognitionCallbacks, SpeechRecognitionProvider, SpeechRecognitionStatus } from './types'

export const createSpeechProvider = (): SpeechRecognitionProvider => {
  if (speechConfig.provider === 'web') {
    return new WebSpeechProvider()
  }
  return new QwenRealtimeSpeechProvider()
}

export const getActiveSpeechProviderLabel = (provider: SpeechRecognitionProvider) => {
  if (provider.name === 'qwen') return '千问实时语音识别'
  if (provider.name === 'web') return '浏览器听写'
  return provider.isSupported() ? '语音识别' : '听写不可用'
}
