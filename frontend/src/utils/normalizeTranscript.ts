/** 语音转写发送前轻量清洗（不调用 LLM） */
export const normalizeTranscript = (raw: string) => {
  let text = String(raw || '')
    .replace(/\s+/g, ' ')
    .trim()
  if (!text) return ''
  if (!/[。！？!?]$/.test(text)) {
    text += '。'
  }
  return text
}
