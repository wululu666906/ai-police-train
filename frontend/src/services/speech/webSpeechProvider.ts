import type {
  SpeechRecognitionCallbacks,
  SpeechRecognitionProvider,
  SpeechRecognitionStartOptions,
  SpeechRecognitionStatus,
} from './types'

const getRecognitionCtor = () => window.SpeechRecognition || window.webkitSpeechRecognition

export class WebSpeechProvider implements SpeechRecognitionProvider {
  readonly name = 'web'

  private recognition: SpeechRecognition | null = null
  private callbacks: SpeechRecognitionCallbacks | null = null

  isSupported() {
    return typeof getRecognitionCtor() === 'function'
  }

  private setStatus(status: SpeechRecognitionStatus) {
    this.callbacks?.onStatusChange?.(status)
  }

  start(options: SpeechRecognitionStartOptions, callbacks: SpeechRecognitionCallbacks) {
    const Ctor = getRecognitionCtor()
    if (!Ctor) {
      callbacks.onError?.('当前浏览器不支持语音听写，请改用键盘输入或接入科大讯飞 API')
      return
    }

    this.abort()
    this.callbacks = callbacks

    const recognition = new Ctor()
    recognition.continuous = options.continuous ?? true
    recognition.interimResults = options.interimResults ?? true
    recognition.lang = options.lang || 'zh-CN'
    recognition.maxAlternatives = 1

    recognition.onstart = () => this.setStatus('listening')
    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = ''
      let finalChunk = ''

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index]
        const transcript = result[0]?.transcript || ''
        if (result.isFinal) {
          finalChunk += transcript
        } else {
          interim += transcript
        }
      }

      if (interim.trim()) {
        callbacks.onInterim?.(interim.trim())
      }
      if (finalChunk.trim()) {
        callbacks.onFinal?.(finalChunk.trim())
      }
    }
    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      const ignored = ['no-speech', 'aborted']
      if (ignored.includes(event.error)) {
        this.setStatus('idle')
        return
      }
      this.setStatus('error')
      callbacks.onError?.(`语音识别失败：${event.error}`)
    }
    recognition.onend = () => this.setStatus('idle')

    this.recognition = recognition
    try {
      recognition.start()
    } catch {
      callbacks.onError?.('无法启动语音识别，请检查麦克风权限')
    }
  }

  stop() {
    this.recognition?.stop()
  }

  abort() {
    if (!this.recognition) return
    try {
      this.recognition.abort()
    } catch {
      // noop
    }
    this.recognition = null
    this.callbacks = null
    this.setStatus('idle')
  }
}
