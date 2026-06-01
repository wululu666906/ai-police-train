type IFlytekWord = { w?: string }
type IFlytekWs = { cw?: IFlytekWord[] }
type IFlytekResult = { ws?: IFlytekWs[] }

export type IFlytekResultMeta = IFlytekResult & {
  sn?: number
  ls?: boolean
  pgs?: string
  rg?: number[]
}

export const parseIFlytekResultText = (result?: IFlytekResult | null) => {
  if (!result?.ws?.length) return ''
  return result.ws
    // iat 每个词位 cw 是候选列表，这里只取 top1，避免把备选词一起拼进结果。
    .map((segment) => segment.cw?.[0]?.w || '')
    .join('')
}

const PUNCTUATION_ONLY = /^[。！？，、；：…．.?!,;:\s]+$/

export const isPunctuationOnly = (text: string) => {
  const trimmed = text.trim()
  return Boolean(trimmed) && PUNCTUATION_ONLY.test(trimmed)
}

const hasWpgsMeta = (result: IFlytekResultMeta) =>
  result.sn !== undefined || result.pgs !== undefined || result.rg !== undefined

/** 按 sn 下标存帧；pgs=rpl 时 rg 为需清空的 sn 区间（含端点）。 */
const applyWpgsFrame = (frames: Array<IFlytekResultMeta | null>, result: IFlytekResultMeta) => {
  const sn = result.sn ?? 0

  if (result.pgs === 'rpl' && Array.isArray(result.rg) && result.rg.length >= 2) {
    const start = Math.max(0, Math.floor(result.rg[0]))
    const end = Math.floor(result.rg[1])
    for (let i = start; i <= end; i++) {
      if (i < frames.length) {
        frames[i] = null
      }
    }
  }

  while (frames.length <= sn) {
    frames.push(null)
  }
  frames[sn] = result
}

const buildTextFromFrames = (frames: Array<IFlytekResultMeta | null>) => {
  let text = ''
  for (const frame of frames) {
    if (!frame) continue
    text += parseIFlytekResultText(frame)
  }
  return text
}

const mergeWithOverlap = (base: string, incoming: string) => {
  if (!incoming) return base
  if (!base) return incoming
  if (base.endsWith(incoming)) return base
  const maxOverlap = Math.min(base.length, incoming.length)
  for (let i = maxOverlap; i > 0; i--) {
    if (base.endsWith(incoming.slice(0, i))) {
      return base + incoming.slice(i)
    }
  }
  return base + incoming
}

/** 累积流式听写：已落句 + 当前句（wpgs 按 sn 拼接，非 wpgs 用最新帧覆盖）。 */
export class IFlytekResultAccumulator {
  private state = {
    committedText: '',
    activeSentenceFrames: [] as Array<IFlytekResultMeta | null>,
    simplePartial: '',
    sentenceClosed: false,
    terminalPunctuation: '',
  }

  reset() {
    this.state.committedText = ''
    this.state.activeSentenceFrames = []
    this.state.simplePartial = ''
    this.state.sentenceClosed = false
    this.state.terminalPunctuation = ''
  }

  private getPartial() {
    if (this.state.activeSentenceFrames.length) {
      return buildTextFromFrames(this.state.activeSentenceFrames)
    }
    return this.state.simplePartial
  }

  private appendPunctuationToCommitted(piece: string) {
    const punct = piece.trim()
    if (!punct || !this.state.committedText) return
    if (this.state.committedText.endsWith(punct)) return
    this.state.terminalPunctuation = punct
    this.state.committedText = mergeWithOverlap(this.state.committedText, punct)
  }

  feed(result?: IFlytekResultMeta | null) {
    const sentenceEnd = Boolean(result?.ls)
    const piece = parseIFlytekResultText(result)

    if (this.state.sentenceClosed) {
      if (piece && isPunctuationOnly(piece)) {
        this.appendPunctuationToCommitted(piece)
        return {
          display: this.getDisplay(),
          sentenceEnd: false,
          finalSentence: '',
          ignoreInterim: true,
        }
      }
      if (result && (piece || hasWpgsMeta(result))) {
        this.state.sentenceClosed = false
        this.state.activeSentenceFrames = []
        this.state.simplePartial = ''
        this.state.terminalPunctuation = ''
      } else if (!result) {
        return {
          display: this.getDisplay(),
          sentenceEnd: false,
          finalSentence: '',
          ignoreInterim: true,
        }
      }
    }

    if (result) {
      if (hasWpgsMeta(result)) {
        applyWpgsFrame(this.state.activeSentenceFrames, result)
        this.state.simplePartial = ''
      } else {
        if (piece) {
          this.state.simplePartial = piece
          this.state.activeSentenceFrames = []
        }
      }
    }

    const partial = this.getPartial()
    let finalSentence = ''
    if (sentenceEnd) {
      finalSentence = partial.trim()
      if (finalSentence) {
        this.state.committedText = mergeWithOverlap(this.state.committedText, finalSentence)
      }
      this.state.activeSentenceFrames = []
      this.state.simplePartial = ''
      this.state.sentenceClosed = true
    }

    return {
      display: this.getDisplay(),
      sentenceEnd,
      finalSentence,
      ignoreInterim: false,
    }
  }

  getDisplay() {
    return (this.state.committedText + this.getPartial()).trim()
  }

  flushPartial() {
    const text = this.getPartial().trim()
    if (text) {
      this.state.committedText = mergeWithOverlap(this.state.committedText, text)
      this.state.activeSentenceFrames = []
      this.state.simplePartial = ''
    }
    return text
  }

  getDebugSnapshot() {
    return {
      committedText: this.state.committedText,
      partialText: this.getPartial(),
      sentenceClosed: this.state.sentenceClosed,
      terminalPunctuation: this.state.terminalPunctuation,
      activeSnList: this.state.activeSentenceFrames
        .map((frame) => frame?.sn)
        .filter((sn) => typeof sn === 'number'),
    }
  }
}

export type IFlytekMessage = {
  code?: number
  message?: string
  data?: {
    status?: number
    result?: IFlytekResultMeta
  }
}
