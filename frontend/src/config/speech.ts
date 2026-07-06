export type SpeechProviderName = 'web' | 'iflytek' | 'auto'

const parseVadEos = (value: string | undefined, fallback: number) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

export const speechConfig = {
  /** auto: 优先科大讯飞（由后端鉴权），失败时回退浏览器听写 */
  provider: (import.meta.env.VITE_SPEECH_PROVIDER || 'auto') as SpeechProviderName,
  /** 生产环境禁止静默回退浏览器听写（需 HTTPS + 讯飞密钥） */
  requireIflytekInProd: import.meta.env.PROD,
  /** 通话模式 VAD 尾静音（毫秒），对应环境变量 VITE_IFLYTEK_VAD_EOS */
  iflytekVadEosVoiceCall: parseVadEos(import.meta.env.VITE_IFLYTEK_VAD_EOS, 1400),
  /** 浏览器听写：合并连续 final 片段后再触发 utteranceEnd（毫秒） */
  webSpeechUtteranceMergeMs: 650,
  iflytekVadEosDictation: 2000,
  /** 仅开发阶段使用：打印讯飞返回与解析拼接关键字段 */
  iflytekDebug: import.meta.env.DEV && import.meta.env.VITE_IFLYTEK_DEBUG === '1',
  iflytekDebugVerbose: import.meta.env.DEV && import.meta.env.VITE_IFLYTEK_DEBUG_VERBOSE === '1',
}
