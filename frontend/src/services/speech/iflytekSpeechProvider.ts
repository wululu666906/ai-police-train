import { IFlytekPcmRecorder } from '../../utils/iflytekPcmRecorder'
import { IFlytekResultAccumulator, parseIFlytekResultText, type IFlytekMessage } from '../../utils/iflytekResultParser'
import { fetchIFlytekStatus, fetchIFlytekWsUrl } from './iflytekAuth'
import { speechConfig } from '../../config/speech'
import type {
  SpeechRecognitionCallbacks,
  SpeechRecognitionProvider,
  SpeechRecognitionStartOptions,
  SpeechSessionMode,
} from './types'

let cachedConfigured: boolean | null = null

export class IFlytekSpeechProvider implements SpeechRecognitionProvider {
  readonly name = 'iflytek'

  private ws: WebSocket | null = null
  private recorder: IFlytekPcmRecorder | null = null
  private callbacks: SpeechRecognitionCallbacks | null = null
  private appId = ''
  private started = false
  private readonly resultAccumulator = new IFlytekResultAccumulator()
  private autoStopTimer: ReturnType<typeof setTimeout> | null = null
  private finalizeTimer: ReturnType<typeof setTimeout> | null = null
  private finalizeResolver: ((text: string) => void) | null = null
  private sessionMode: SpeechSessionMode = 'dictation'
  private sessionId = ''

  private logDebug(stage: string, detail: Record<string, unknown>) {
    if (!speechConfig.iflytekDebug) return
    const payload = speechConfig.iflytekDebugVerbose
      ? { ...detail, sessionId: this.sessionId || 'n/a', ts: Date.now() }
      : detail
    console.debug(`[iflytek-debug] ${stage}`, payload)
  }

  isSupported() {
    return typeof window !== 'undefined' && Boolean(window.WebSocket && navigator.mediaDevices?.getUserMedia)
  }

  private setStatus(status: 'idle' | 'listening' | 'processing' | 'error') {
    this.callbacks?.onStatusChange?.(status)
  }

  private async ensureConfigured() {
    try {
      const status = await fetchIFlytekStatus()
      this.appId = status.app_id || ''
      cachedConfigured = Boolean(status.configured && status.app_id)
      return cachedConfigured
    } catch {
      cachedConfigured = false
      return false
    }
  }

  private getVadEos() {
    return this.sessionMode === 'voice_call'
      ? speechConfig.iflytekVadEosVoiceCall
      : speechConfig.iflytekVadEosDictation
  }

  private buildPayload(base64Audio: string, status: 0 | 1 | 2) {
    if (status === 0) {
      return {
        common: { app_id: this.appId },
        business: {
          language: 'zh_cn',
          domain: 'iat',
          accent: 'mandarin',
          vad_eos: this.getVadEos(),
          dwa: 'wpgs',
        },
        data: {
          status: 0,
          format: 'audio/L16;rate=16000',
          encoding: 'raw',
          audio: base64Audio,
        },
      }
    }

    if (status === 2) {
      return { data: { status: 2 } }
    }

    return {
      data: {
        status: 1,
        format: 'audio/L16;rate=16000',
        encoding: 'raw',
        audio: base64Audio,
      },
    }
  }

  private handleMessage(raw: string) {
    let payload: IFlytekMessage
    try {
      payload = JSON.parse(raw)
    } catch {
      return
    }

    if (payload.code !== 0) {
      this.logDebug('error', {
        code: payload.code,
        message: payload.message || '',
      })
      this.callbacks?.onError?.(payload.message || `科大讯飞听写失败（${payload.code}）`)
      this.setStatus('error')
      this.abort()
      return
    }

    this.logDebug('raw-result', {
      status: payload.data?.status,
      sid: (payload as any).sid || '',
      sn: payload.data?.result?.sn,
      pgs: payload.data?.result?.pgs,
      rg: payload.data?.result?.rg,
      ls: payload.data?.result?.ls,
      piece: parseIFlytekResultText(payload.data?.result),
    })

    const { display, sentenceEnd, finalSentence, ignoreInterim } = this.resultAccumulator.feed(
      payload.data?.result
    )
    this.logDebug('accumulated', {
      sentenceEnd,
      finalSentence,
      ignoreInterim,
      display,
      snapshot: this.resultAccumulator.getDebugSnapshot(),
    })
    const streamEnded = payload.data?.status === 2

    if (sentenceEnd) {
      if (finalSentence) {
        this.callbacks?.onFinal?.(finalSentence)
      }
      if (this.sessionMode === 'voice_call') {
        const utterance = finalSentence.trim()
        if (utterance) {
          this.callbacks?.onUtteranceEnd?.(utterance)
        }
        this.resultAccumulator.reset()
        this.callbacks?.onInterim?.('')
        return
      }
      const fullDisplay = this.resultAccumulator.getDisplay()
      if (fullDisplay) {
        this.callbacks?.onInterim?.(fullDisplay)
      }
      this.scheduleAutoStop()
      return
    }

    if (streamEnded) {
      const tail = this.resultAccumulator.flushPartial()
      if (tail) {
        this.callbacks?.onFinal?.(tail)
      }
      const fullDisplay = this.resultAccumulator.getDisplay()
      if (fullDisplay) {
        this.callbacks?.onInterim?.(fullDisplay)
      }
      if (this.finalizeResolver) {
        this.completeFinalize()
        return
      }
      if (this.sessionMode !== 'voice_call') {
        this.scheduleAutoStop()
      }
      return
    }

    if (ignoreInterim) {
      return
    }

    if (display) {
      this.callbacks?.onInterim?.(display)
    }
  }

  private scheduleAutoStop() {
    if (this.sessionMode === 'voice_call') return
    if (this.autoStopTimer) {
      clearTimeout(this.autoStopTimer)
    }
    this.autoStopTimer = setTimeout(() => {
      this.autoStopTimer = null
      if (!this.started) return
      const onAutoEnd = this.callbacks?.onAutoEnd
      this.stop()
      onAutoEnd?.()
    }, 280)
  }

  private clearAutoStopTimer() {
    if (this.autoStopTimer) {
      clearTimeout(this.autoStopTimer)
      this.autoStopTimer = null
    }
  }

  private clearFinalizeTimer() {
    if (this.finalizeTimer) {
      clearTimeout(this.finalizeTimer)
      this.finalizeTimer = null
    }
  }

  private collectTranscript() {
    const display = this.resultAccumulator.getDisplay().trim()
    const tail = this.resultAccumulator.flushPartial().trim()
    if (!tail) return display
    if (!display) return tail
    if (display.endsWith(tail)) return display
    return `${display}${tail}`
  }

  private completeFinalize() {
    this.clearFinalizeTimer()
    const text = this.collectTranscript()
    const resolver = this.finalizeResolver
    this.finalizeResolver = null
    resolver?.(text)
    this.cleanupConnection()
  }

  private cleanupConnection() {
    this.clearAutoStopTimer()
    this.clearFinalizeTimer()
    this.started = false
    this.recorder = null
    if (this.ws) {
      try {
        if (this.ws.readyState === WebSocket.OPEN) {
          this.ws.close()
        }
      } catch {
        // noop
      }
    }
    this.ws = null
    this.callbacks = null
    this.sessionId = ''
    this.setStatus('idle')
  }

  /** 通话中尚未自动发送的尾部文本（挂断前可选补发） */
  peekPendingUtterance(): string {
    const tail = this.resultAccumulator.flushPartial().trim()
    const display = this.resultAccumulator.getDisplay().trim()
    return tail || display
  }

  /** 通话挂断：发送结束帧并等待最终转写 */
  async finalizeListening(): Promise<string> {
    if (!this.started) {
      return this.collectTranscript()
    }

    this.clearAutoStopTimer()
    this.setStatus('processing')

    return new Promise((resolve) => {
      this.finalizeResolver = resolve
      this.recorder?.stop()
      this.recorder = null

      this.finalizeTimer = setTimeout(() => {
        if (this.finalizeResolver) {
          this.completeFinalize()
        }
      }, 1500)
    })
  }

  async start(options: SpeechRecognitionStartOptions, callbacks: SpeechRecognitionCallbacks) {
    this.callbacks = callbacks
    this.sessionMode = options.sessionMode || 'dictation'

    const configured = await this.ensureConfigured()
    if (!configured) {
      callbacks.onError?.(
        '科大讯飞未配置完整：请在服务端 .env 填写 IFLYTEK_APP_ID、IFLYTEK_API_KEY、IFLYTEK_API_SECRET'
      )
      callbacks.onStatusChange?.('error')
      return
    }

    try {
      const { url } = await fetchIFlytekWsUrl()
      this.sessionId = Math.random().toString(36).slice(2, 10)
      this.logDebug('ws-url-ready', { hasUrl: Boolean(url) })
      this.ws = new WebSocket(url)
    } catch (error: any) {
      const detail = error?.response?.data?.detail || error?.message || '无法获取听写鉴权地址'
      callbacks.onError?.(String(detail))
      callbacks.onStatusChange?.('error')
      return
    }

    this.resultAccumulator.reset()
    this.clearAutoStopTimer()
    this.recorder = new IFlytekPcmRecorder()
    this.started = true
    this.setStatus('listening')

    this.ws.onopen = async () => {
      try {
        await this.recorder?.start(
          (audio, status) => {
            if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return
            this.ws.send(JSON.stringify(this.buildPayload(audio, status)))
          },
          options.mediaStream,
          this.callbacks?.onAudioLevel,
          (snapshot) => this.logDebug('recorder', snapshot)
        )
      } catch (error: any) {
        callbacks.onError?.(error?.message || '无法访问麦克风')
        this.setStatus('error')
        this.abort()
      }
    }

    this.ws.onmessage = (event) => {
      if (typeof event.data === 'string') {
        this.handleMessage(event.data)
      }
    }

    this.ws.onerror = () => {
      callbacks.onError?.('科大讯飞 WebSocket 连接异常')
      this.setStatus('error')
    }

    this.ws.onclose = () => {
      if (this.started) {
        this.setStatus('idle')
      }
    }
  }

  stop() {
    if (!this.started) return
    if (this.sessionMode === 'voice_call') {
      void this.finalizeListening()
      return
    }
    this.clearAutoStopTimer()
    this.clearFinalizeTimer()
    this.finalizeResolver = null
    this.started = false
    this.setStatus('processing')
    this.recorder?.stop()
    this.recorder = null

    window.setTimeout(() => {
      this.cleanupConnection()
    }, 400)
  }

  abort() {
    this.clearAutoStopTimer()
    this.clearFinalizeTimer()
    this.finalizeResolver = null
    this.started = false
    this.recorder?.stop()
    this.recorder = null
    if (this.ws) {
      try {
        this.ws.close()
      } catch {
        // noop
      }
    }
    this.ws = null
    this.callbacks = null
    this.sessionId = ''
    this.setStatus('idle')
  }
}

export const resetIFlytekConfigCache = () => {
  cachedConfigured = null
}
