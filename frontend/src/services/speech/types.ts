export type SpeechRecognitionStatus = 'idle' | 'listening' | 'processing' | 'error'

export interface SpeechRecognitionCallbacks {
  onInterim?: (text: string) => void
  onFinal?: (text: string) => void
  /** 检测到一句话结束（VAD 静音）时触发，用于自动结束本轮听写 */
  onAutoEnd?: () => void
  onError?: (message: string) => void
  onStatusChange?: (status: SpeechRecognitionStatus) => void
}

export interface SpeechRecognitionStartOptions {
  lang?: string
  continuous?: boolean
  interimResults?: boolean
}

export interface SpeechRecognitionProvider {
  readonly name: string
  isSupported(): boolean
  start(options: SpeechRecognitionStartOptions, callbacks: SpeechRecognitionCallbacks): void
  stop(): void
  abort(): void
}
