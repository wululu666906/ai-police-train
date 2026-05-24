export type SpeechProviderName = 'web' | 'iflytek' | 'auto'

export const speechConfig = {
  /** auto: 优先科大讯飞（由后端鉴权），失败时回退浏览器听写 */
  provider: (import.meta.env.VITE_SPEECH_PROVIDER || 'auto') as SpeechProviderName,
}
