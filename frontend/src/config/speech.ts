export type SpeechProviderName = 'qwen' | 'web' | 'auto'

export const speechConfig = {
  // auto uses the backend Qwen realtime ASR proxy. Use web only for local browser fallback.
  provider: (import.meta.env.VITE_SPEECH_PROVIDER || 'auto') as SpeechProviderName,
  webSpeechUtteranceMergeMs: 650,
}
