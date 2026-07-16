import type {
  SpeechRecognitionCallbacks,
  SpeechRecognitionProvider,
  SpeechRecognitionStartOptions,
  SpeechRecognitionStatus,
} from './types'

const TARGET_SAMPLE_RATE = 16000

const getApiBaseUrl = () =>
  import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '/api')

const getRealtimeHttpBase = () => {
  const apiBase = getApiBaseUrl().replace(/\/$/, '')
  if (!apiBase) return window.location.origin
  if (apiBase.startsWith('/')) return `${window.location.origin}${apiBase}`
  return apiBase
}

const getRealtimeWsUrl = (language = 'zh') => {
  const httpBase = getRealtimeHttpBase()
  const wsBase = httpBase.replace(/^http/i, 'ws')
  const token = encodeURIComponent(localStorage.getItem('token') || '')
  return `${wsBase}/speech/realtime?language=${encodeURIComponent(language)}&token=${token}`
}

const downsampleTo16k = (samples: Float32Array, sourceRate: number) => {
  if (sourceRate === TARGET_SAMPLE_RATE) return samples
  const ratio = sourceRate / TARGET_SAMPLE_RATE
  const nextLength = Math.max(1, Math.round(samples.length / ratio))
  const result = new Float32Array(nextLength)
  let sourceOffset = 0
  for (let i = 0; i < nextLength; i += 1) {
    const nextOffset = Math.round((i + 1) * ratio)
    let sum = 0
    let count = 0
    for (let j = sourceOffset; j < nextOffset && j < samples.length; j += 1) {
      sum += samples[j]
      count += 1
    }
    result[i] = count ? sum / count : 0
    sourceOffset = nextOffset
  }
  return result
}

const pcm16ToBase64 = (samples: Float32Array) => {
  const buffer = new ArrayBuffer(samples.length * 2)
  const view = new DataView(buffer)
  for (let i = 0; i < samples.length; i += 1) {
    const clamped = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true)
  }
  const bytes = new Uint8Array(buffer)
  let binary = ''
  const chunkSize = 0x8000
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize))
  }
  return window.btoa(binary)
}

export class QwenRealtimeSpeechProvider implements SpeechRecognitionProvider {
  readonly name = 'qwen'

  private ws: WebSocket | null = null
  private callbacks: SpeechRecognitionCallbacks | null = null
  private audioContext: AudioContext | null = null
  private audioSource: MediaStreamAudioSourceNode | null = null
  private audioProcessor: ScriptProcessorNode | null = null
  private ownedStream: MediaStream | null = null
  private started = false
  private finalText = ''
  private interimText = ''
  private finishTimer: ReturnType<typeof setTimeout> | null = null

  isSupported() {
    return typeof window !== 'undefined' && Boolean(window.WebSocket && navigator.mediaDevices?.getUserMedia && window.AudioContext)
  }

  private setStatus(status: SpeechRecognitionStatus) {
    this.callbacks?.onStatusChange?.(status)
  }

  private handleTranscriptDelta(text: string) {
    const delta = text.trim()
    if (!delta) return
    this.interimText = delta
    this.callbacks?.onInterim?.([this.finalText, this.interimText].filter(Boolean).join(''))
  }

  private handleTranscript(text: string) {
    const transcript = text.trim()
    if (!transcript) return
    this.finalText = `${this.finalText}${transcript}`.trim()
    this.interimText = ''
    this.callbacks?.onFinal?.(transcript)
    this.callbacks?.onInterim?.(this.finalText)
    this.callbacks?.onUtteranceEnd?.(transcript)
  }

  private async openAudio(stream: MediaStream) {
    const context = new AudioContext()
    if (context.state === 'suspended') await context.resume()

    const source = context.createMediaStreamSource(stream)
    const processor = context.createScriptProcessor(4096, 1, 1)
    processor.onaudioprocess = (event) => {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return
      const channel = event.inputBuffer.getChannelData(0)
      const downsampled = downsampleTo16k(channel, context.sampleRate)
      const audio = pcm16ToBase64(downsampled)
      if (audio) {
        this.ws.send(JSON.stringify({ type: 'audio', audio }))
      }
    }
    source.connect(processor)
    processor.connect(context.destination)
    this.audioContext = context
    this.audioSource = source
    this.audioProcessor = processor
  }

  async start(options: SpeechRecognitionStartOptions, callbacks: SpeechRecognitionCallbacks) {
    this.abort()
    this.callbacks = callbacks
    this.finalText = ''
    this.interimText = ''
    this.setStatus('processing')

    try {
      const language = options.lang?.toLowerCase().startsWith('zh') ? 'zh' : options.lang || 'zh'
      this.ws = new WebSocket(getRealtimeWsUrl(language))
    } catch (error: any) {
      this.setStatus('error')
      callbacks.onError?.(error?.message || '无法连接千问实时语音识别服务')
      return
    }

    this.ws.onopen = async () => {
      try {
        const stream = options.mediaStream || await navigator.mediaDevices.getUserMedia({ audio: true })
        if (!options.mediaStream) this.ownedStream = stream
        await this.openAudio(stream)
        this.started = true
        this.setStatus('listening')
      } catch (error: any) {
        this.setStatus('error')
        callbacks.onError?.(error?.message || '无法访问麦克风')
        this.abort()
      }
    }

    this.ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(String(event.data || '{}'))
        if (payload.type === 'ready') {
          this.setStatus('listening')
        } else if (payload.type === 'transcript_delta') {
          this.handleTranscriptDelta(String(payload.text || ''))
        } else if (payload.type === 'transcript') {
          this.handleTranscript(String(payload.text || ''))
        } else if (payload.type === 'error') {
          throw new Error(String(payload.message || '千问实时语音识别失败'))
        }
      } catch (error: any) {
        this.setStatus('error')
        callbacks.onError?.(error?.message || '千问实时语音识别失败')
      }
    }

    this.ws.onerror = () => {
      this.setStatus('error')
      callbacks.onError?.('千问实时语音识别连接异常')
    }

    this.ws.onclose = () => {
      if (this.started) {
        this.setStatus('idle')
      }
    }
  }

  stop() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify({ type: 'commit' }))
      } catch {
        // noop
      }
    }
    this.setStatus('processing')
    if (this.finishTimer) clearTimeout(this.finishTimer)
    this.finishTimer = setTimeout(() => {
      this.finishTimer = null
      const text = [this.finalText, this.interimText].filter(Boolean).join('').trim()
      const onAutoEnd = this.callbacks?.onAutoEnd
      if (this.ws?.readyState === WebSocket.OPEN) {
        try {
          this.ws.send(JSON.stringify({ type: 'close' }))
        } catch {
          // noop
        }
      }
      this.cleanup()
      if (text) onAutoEnd?.()
    }, 900)
  }

  abort() {
    this.cleanup()
  }

  private cleanup() {
    if (this.finishTimer) {
      clearTimeout(this.finishTimer)
      this.finishTimer = null
    }
    this.started = false
    try {
      this.audioProcessor?.disconnect()
      this.audioSource?.disconnect()
      void this.audioContext?.close()
    } catch {
      // noop
    }
    this.audioProcessor = null
    this.audioSource = null
    this.audioContext = null
    this.ownedStream?.getTracks().forEach((track) => track.stop())
    this.ownedStream = null
    try {
      this.ws?.close()
    } catch {
      // noop
    }
    this.ws = null
    this.setStatus('idle')
  }
}
