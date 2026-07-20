import { speechConfig } from '../../config/speech'
import { QwenRealtimeSpeechProvider } from './qwenRealtimeSpeechProvider'
import type { SpeechRecognitionCallbacks, SpeechRecognitionProvider, SpeechRecognitionStartOptions } from './types'
import { WebSpeechProvider } from './webSpeechProvider'

export type { SpeechRecognitionCallbacks, SpeechRecognitionProvider, SpeechRecognitionStatus } from './types'

class QwenPreferredSpeechProvider implements SpeechRecognitionProvider {
  readonly name = 'qwen-preferred'

  private readonly qwen = new QwenRealtimeSpeechProvider()
  private readonly web = new WebSpeechProvider()
  private active: SpeechRecognitionProvider = this.qwen
  private fallbackStarted = false

  isSupported() {
    return this.qwen.isSupported() || this.web.isSupported()
  }

  start(options: SpeechRecognitionStartOptions, callbacks: SpeechRecognitionCallbacks) {
    this.abort()
    this.fallbackStarted = false
    this.active = this.qwen

    if (!this.qwen.isSupported()) {
      this.startWebFallback(options, callbacks)
      return
    }

    this.qwen.start(options, {
      ...callbacks,
      onError: (message) => {
        if (this.web.isSupported() && !this.fallbackStarted) {
          this.startWebFallback(options, callbacks)
          return
        }
        callbacks.onError?.(message)
      },
    })
  }

  stop() {
    this.active.stop()
  }

  abort() {
    this.qwen.abort()
    this.web.abort()
  }

  private startWebFallback(options: SpeechRecognitionStartOptions, callbacks: SpeechRecognitionCallbacks) {
    this.fallbackStarted = true
    this.active = this.web
    callbacks.onStatusChange?.('processing')
    this.web.start(options, {
      ...callbacks,
      onError: (message) => callbacks.onError?.(message || '千问语音识别不可用，浏览器听写也未能启动'),
    })
  }
}

export const createSpeechProvider = (): SpeechRecognitionProvider => {
  const webProvider = new WebSpeechProvider()
  if (speechConfig.provider === 'web') {
    return webProvider
  }
  if (speechConfig.provider === 'auto') {
    return new QwenPreferredSpeechProvider()
  }
  return new QwenRealtimeSpeechProvider()
}

export const getActiveSpeechProviderLabel = (provider: SpeechRecognitionProvider) => {
  if (provider.name === 'qwen-preferred') return '千问实时语音识别'
  if (provider.name === 'qwen') return '千问实时语音识别'
  if (provider.name === 'web') return '浏览器听写'
  return provider.isSupported() ? '语音识别' : '听写不可用'
}
