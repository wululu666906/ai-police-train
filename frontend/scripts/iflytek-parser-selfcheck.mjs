/**
 * 讯飞 wpgs 解析自测（纯 JS，不依赖 TS 编译）
 * 运行：node frontend/scripts/iflytek-parser-selfcheck.mjs
 */
import assert from 'node:assert/strict'

const parseText = (result) => {
  if (!result?.ws?.length) return ''
  return result.ws
    .map((s) => s.cw?.[0]?.w || '')
    .join('')
}

const hasWpgsMeta = (r) => r.sn !== undefined || r.pgs !== undefined || r.rg !== undefined

const applyWpgsFrame = (frames, result) => {
  const sn = result.sn ?? 0
  if (result.pgs === 'rpl' && Array.isArray(result.rg) && result.rg.length >= 2) {
    const start = Math.max(0, Math.floor(result.rg[0]))
    const end = Math.floor(result.rg[1])
    for (let i = start; i <= end; i++) {
      if (i < frames.length) frames[i] = null
    }
  }
  while (frames.length <= sn) frames.push(null)
  frames[sn] = result
}

const buildFromFrames = (frames) => {
  let t = ''
  for (const f of frames) {
    if (f) t += parseText(f)
  }
  return t
}

const mergeWithOverlap = (base, incoming) => {
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

class Acc {
  constructor() {
    this.reset()
  }
  reset() {
    this.committed = ''
    this.frames = []
    this.simplePartial = ''
    this.sentenceClosed = false
  }
  getPartial() {
    return this.frames.length ? buildFromFrames(this.frames) : this.simplePartial
  }
  getDisplay() {
    return (this.committed + this.getPartial()).trim()
  }
  feed(result) {
    const sentenceEnd = Boolean(result?.ls)
    const piece = parseText(result)

    if (this.sentenceClosed) {
      if (result && (piece || hasWpgsMeta(result))) {
        this.sentenceClosed = false
        this.frames = []
        this.simplePartial = ''
      }
    }

    if (result) {
      if (hasWpgsMeta(result)) {
        applyWpgsFrame(this.frames, result)
        this.simplePartial = ''
      } else if (piece) {
        this.simplePartial = piece
        this.frames = []
      }
    }

    const partial = this.getPartial()
    if (sentenceEnd) {
      const final = partial.trim()
      if (final) this.committed = mergeWithOverlap(this.committed, final)
      this.frames = []
      this.simplePartial = ''
      this.sentenceClosed = true
    }
    return this.getDisplay()
  }
}

const ws = (words) => ({ ws: words.map((w) => ({ cw: [{ w }] })) })

{
  const acc = new Acc()
  acc.feed({ sn: 1, pgs: 'apd', ...ws(['你']) })
  acc.feed({ sn: 2, pgs: 'apd', ...ws(['好']) })
  acc.feed({ sn: 3, pgs: 'rpl', rg: [1, 2], ...ws(['您好']) })
  assert.equal(acc.getDisplay(), '您好')
}

{
  const acc = new Acc()
  acc.feed({ sn: 1, pgs: 'apd', ...ws(['我']) })
  acc.feed({ sn: 2, pgs: 'apd', ...ws(['在']) })
  acc.feed({ sn: 3, pgs: 'rpl', rg: [2, 2], ...ws(['现场']) })
  assert.equal(acc.getDisplay(), '我现场')
}

{
  const display = parseText({ ws: [{ cw: [{ w: '警察' }, { w: '经常' }] }] })
  assert.equal(display, '警察')
}

{
  const acc = new Acc()
  acc.feed({ sn: 1, pgs: 'apd', ls: true, ...ws(['你好']) })
  acc.feed({ sn: 2, pgs: 'apd', ls: true, ...ws(['好']) })
  assert.equal(acc.getDisplay(), '你好')
}

{
  const acc = new Acc()
  acc.feed(ws(['你']))
  acc.feed(ws(['你好']))
  acc.feed(ws(['你好世界']))
  assert.equal(acc.getDisplay(), '你好世界')
}

{
  const acc = new Acc()
  acc.feed({ sn: 1, pgs: 'apd', ls: true, ...ws(['第一句']) })
  assert.equal(acc.getDisplay(), '第一句')
  acc.feed({ sn: 1, pgs: 'apd', ...ws(['第二句']) })
  assert.equal(acc.getDisplay(), '第一句第二句')
}

console.log('iflytek-parser-selfcheck: OK')
