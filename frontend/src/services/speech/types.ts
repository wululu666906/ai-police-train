export type SpeechRecognitionStatus = 'idle' | 'listening' | 'processing' | 'error'

export interface SpeechRecognitionCallbacks {
  onInterim?: (text: string) => void
  onFinal?: (text: string) => void
  /** 检测到一句话结束（VAD 静音）时触发，用于自动结束本轮听写 */
  onAutoEnd?: () => void
  /** 通话模式：单轮发言结束（VAD/句末），可自动发送且会话不断开 */
  onUtteranceEnd?: (text: string) => void
  /** 同一路麦克风的音量采样，用于波形展示 */
  onAudioLevel?: (level: number) => void
  onError?: (message: string) => void
  onStatusChange?: (status: SpeechRecognitionStatus) => void
}

export type SpeechSessionMode = 'dictation' | 'voice_call'

export interface SpeechRecognitionStartOptions {
  lang?: string
  continuous?: boolean
  interimResults?: boolean
  /** 与波形共用的麦克风流，避免重复 getUserMedia */
  mediaStream?: MediaStream
  /** voice_call：连续通话，句末不自动结束，仅挂断时收口 */
  sessionMode?: SpeechSessionMode
}

export interface SpeechRecognitionProvider {
  readonly name: string
  isSupported(): boolean
  start(options: SpeechRecognitionStartOptions, callbacks: SpeechRecognitionCallbacks): void
  stop(): void
  abort(): void
}
