type IFlytekWord = { w?: string }
type IFlytekWs = { cw?: IFlytekWord[] }
type IFlytekResult = { ws?: IFlytekWs[] }

export type IFlytekResultMeta = IFlytekResult & {
  ls?: boolean
  pgs?: string
  rg?: number[]
}

export const parseIFlytekResultText = (result?: IFlytekResult | null) => {
  if (!result?.ws?.length) return ''
  return result.ws
    .map((segment) => (segment.cw || []).map((item) => item.w || '').join(''))
    .join('')
}

const PUNCTUATION_ONLY = /^[。！？，、；：…．.?!,;:\s]+$/

export const isPunctuationOnly = (text: string) => {
  const trimmed = text.trim()
  return Boolean(trimmed) && PUNCTUATION_ONLY.test(trimmed)
}

/** 累积流式听写结果，区分已落句与当前句，避免 rpl 覆盖整段输入。 */
export class IFlytekResultAccumulator {
  private committed = ''
  private partial = ''
  /** 当前句内的分段（用于 pgs=rpl + rg 替换） */
  private partialSegments: string[] = []
  private sentenceClosed = false

  reset() {
    this.committed = ''
    this.partial = ''
    this.partialSegments = []
    this.sentenceClosed = false
  }

  private rebuildPartial() {
    this.partial = this.partialSegments.join('')
  }

  private appendPunctuationToCommitted(piece: string) {
    const punct = piece.trim()
    if (!punct || !this.committed) return
    if (this.committed.endsWith(punct)) return
    this.committed += punct
  }

  private applyPiece(piece: string, pgs?: string, rg?: number[]) {
    if (pgs === 'rpl' && Array.isArray(rg) && rg.length >= 2) {
      const start = Math.max(0, rg[0])
      const end = Math.min(this.partialSegments.length, rg[1] + 1)
      if (this.partialSegments.length) {
        this.partialSegments.splice(start, end - start + 1, piece)
      } else {
        this.partialSegments = [piece]
      }
      this.rebuildPartial()
      return
    }

    if (pgs === 'rpl') {
      if (isPunctuationOnly(piece)) {
        if (this.partial) {
          if (!this.partial.endsWith(piece.trim())) {
            this.partial += piece
            if (this.partialSegments.length) {
              this.partialSegments[this.partialSegments.length - 1] = this.partial
            }
          }
        } else if (this.committed) {
          this.appendPunctuationToCommitted(piece)
        } else {
          this.partial = piece
          this.partialSegments = [piece]
        }
      } else {
        this.partial = piece
        this.partialSegments = [piece]
      }
      return
    }

    if (pgs === 'apd') {
      this.partial += piece
      if (this.partialSegments.length) {
        this.partialSegments[this.partialSegments.length - 1] += piece
      } else {
        this.partialSegments = [piece]
      }
      return
    }

    this.partial = piece
    this.partialSegments = [piece]
  }

  feed(result?: IFlytekResultMeta | null) {
    const piece = parseIFlytekResultText(result)
    const sentenceEnd = Boolean(result?.ls)

    if (this.sentenceClosed) {
      if (piece && isPunctuationOnly(piece)) {
        this.appendPunctuationToCommitted(piece)
      }
      return {
        display: this.getDisplay(),
        sentenceEnd: false,
        finalSentence: '',
        ignoreInterim: true,
      }
    }

    if (piece) {
      this.applyPiece(piece, result?.pgs, result?.rg)
    }

    let finalSentence = ''
    if (sentenceEnd) {
      finalSentence = (this.partial || piece).trim()
      if (finalSentence) {
        this.committed += finalSentence
      }
      this.partial = ''
      this.partialSegments = []
      this.sentenceClosed = true
    }

    return {
      display: this.getDisplay(),
      sentenceEnd,
      finalSentence,
      ignoreInterim: false,
    }
  }

  getDisplay() {
    return (this.committed + this.partial).trim()
  }

  flushPartial() {
    const text = this.partial.trim()
    if (text) {
      this.committed += text
      this.partial = ''
      this.partialSegments = []
    }
    return text
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
