export type SpeechProviderName = 'web' | 'iflytek' | 'auto'

export const speechConfig = {
  /** auto: 优先科大讯飞（由后端鉴权），失败时回退浏览器听写 */
  provider: (import.meta.env.VITE_SPEECH_PROVIDER || 'auto') as SpeechProviderName,
  /** 仅开发阶段使用：打印讯飞返回与解析拼接关键字段 */
  iflytekDebug: import.meta.env.DEV && import.meta.env.VITE_IFLYTEK_DEBUG === '1',
  iflytekDebugVerbose: import.meta.env.DEV && import.meta.env.VITE_IFLYTEK_DEBUG_VERBOSE === '1',
}
