import { speechConfig } from '../../config/speech'
import type {
  SpeechRecognitionCallbacks,
  SpeechRecognitionProvider,
  SpeechRecognitionStartOptions,
  SpeechRecognitionStatus,
  SpeechSessionMode,
} from './types'

const getRecognitionCtor = () => window.SpeechRecognition || window.webkitSpeechRecognition

export class WebSpeechProvider implements SpeechRecognitionProvider {
  readonly name = 'web'

  private recognition: SpeechRecognition | null = null
  private callbacks: SpeechRecognitionCallbacks | null = null
  private sessionMode: SpeechSessionMode = 'dictation'
  private utteranceBuffer = ''
  private utteranceMergeTimer: ReturnType<typeof setTimeout> | null = null

  isSupported() {
    return typeof getRecognitionCtor() === 'function'
  }

  private setStatus(status: SpeechRecognitionStatus) {
    this.callbacks?.onStatusChange?.(status)
  }

  private clearUtteranceMergeTimer() {
    if (this.utteranceMergeTimer) {
      clearTimeout(this.utteranceMergeTimer)
      this.utteranceMergeTimer = null
    }
  }

  private scheduleVoiceCallUtteranceEnd() {
    this.clearUtteranceMergeTimer()
    this.utteranceMergeTimer = setTimeout(() => {
      this.utteranceMergeTimer = null
      const utterance = this.utteranceBuffer.trim()
      this.utteranceBuffer = ''
      if (utterance) {
        this.callbacks?.onUtteranceEnd?.(utterance)
        this.callbacks?.onInterim?.('')
      }
    }, speechConfig.webSpeechUtteranceMergeMs)
  }

  start(options: SpeechRecognitionStartOptions, callbacks: SpeechRecognitionCallbacks) {
    const Ctor = getRecognitionCtor()
    if (!Ctor) {
      callbacks.onError?.('当前浏览器不支持语音听写，请改用键盘输入或使用千问实时语音识别')
      return
    }

    this.abort()
    this.callbacks = callbacks
    this.sessionMode = options.sessionMode || 'dictation'
    this.utteranceBuffer = ''
    this.clearUtteranceMergeTimer()

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
        const piece = finalChunk.trim()
        callbacks.onFinal?.(piece)
        if (this.sessionMode === 'voice_call') {
          this.utteranceBuffer = this.utteranceBuffer ? `${this.utteranceBuffer}${piece}` : piece
          const sessionDisplay = `${this.utteranceBuffer}${interim}`.trim()
          if (sessionDisplay) {
            callbacks.onInterim?.(sessionDisplay)
          }
          this.scheduleVoiceCallUtteranceEnd()
        }
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
    recognition.onend = () => {
      if (this.sessionMode === 'voice_call' && this.recognition) {
        try {
          this.recognition.start()
          this.setStatus('listening')
        } catch {
          this.setStatus('idle')
        }
        return
      }
      this.setStatus('idle')
    }

    this.recognition = recognition
    try {
      recognition.start()
    } catch {
      callbacks.onError?.('无法启动语音识别，请检查麦克风权限')
    }
  }

  peekPendingUtterance(): string {
    this.clearUtteranceMergeTimer()
    const pending = this.utteranceBuffer.trim()
    this.utteranceBuffer = ''
    return pending
  }

  stop() {
    this.recognition?.stop()
  }

  abort() {
    this.clearUtteranceMergeTimer()
    this.utteranceBuffer = ''
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
