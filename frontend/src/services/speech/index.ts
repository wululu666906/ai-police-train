import { speechConfig } from '../../config/speech'
import { IFlytekSpeechProvider } from './iflytekSpeechProvider'
import type { SpeechRecognitionProvider } from './types'
import { WebSpeechProvider } from './webSpeechProvider'

export type { SpeechRecognitionCallbacks, SpeechRecognitionProvider, SpeechRecognitionStatus } from './types'

export const createSpeechProvider = (): SpeechRecognitionProvider => {
  if (speechConfig.provider === 'web') {
    return new WebSpeechProvider()
  }
  return new IFlytekSpeechProvider()
}

export const getActiveSpeechProviderLabel = (provider: SpeechRecognitionProvider) => {
  if (provider.name === 'iflytek') return '科大讯飞听写'
  if (provider.isSupported()) return '浏览器听写'
  return '听写不可用'
}
