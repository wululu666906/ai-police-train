export const normalizeCaseTags = (value: any): string[] => {
  const raw = Array.isArray(value)
    ? value
    : typeof value === 'string'
      ? value.split(/[、，,\s]+/)
      : []
  const seen = new Set<string>()
  const result: string[] = []
  for (const item of raw) {
    const tag = String(item || '').replace(/[#[\]【】（）()]/g, '').trim()
    if (!tag || seen.has(tag) || tag === '未明确' || tag === '其他') continue
    seen.add(tag)
    result.push(tag.slice(0, 12))
    if (result.length >= 8) break
  }
  return result
}

export const parseEngineLabel = (payload: any) => {
  const workflow = payload?.ai_workflow || {}
  if (workflow.used_rule_fallback === true) return '规则兜底解析'
  const engine = String(payload?.parse_engine || '')
  if (engine === 'training_fast_path') return 'AI 智能解析 + 程序化事实装配'
  if (engine === 'ai_text_first') return 'AI 文档阅读 + 智能剧情整理'
  if (engine === 'ai') return 'AI 智能解析'
  if (engine === 'rule_text_first') return '程序化事实装配（AI 剧情未成功）'
  if (engine === 'heuristic') return '规则辅助解析'
  return '智能解析'
}

export const parseEngineIsFallback = (payload: any) => {
  if (typeof payload?.ai_workflow?.used_rule_fallback === 'boolean') {
    return payload.ai_workflow.used_rule_fallback
  }
  return String(payload?.parse_engine || '') === 'heuristic'
}

export const sceneGenerationLabel = (payload: any) => {
  const mode = String(payload?.scene_generation_mode || '')
  if (mode === 'ai_template_first') return 'AI 模板优先场景生成'
  if (mode === 'ai_case_driven' || mode === 'ai') return 'AI 案件驱动场景生成'
  if (mode === 'ai_text_template') return 'AI 纯文本剧本场景生成'
  if (mode === 'fallback_template_first') return '模板优先兜底场景'
  if (mode === 'fallback_case_driven' || mode === 'fallback_modules' || mode === 'fallback') return '案件驱动兜底场景'
  return '场景生成'
}

export const sceneGenerationIsFallback = (payload: any) =>
  String(payload?.scene_generation_mode || '').startsWith('fallback')

export const resolveParsedCaseTitle = (parsed: any, currentTitle = '') => {
  const aiTitle = String(parsed?.case_name || '').trim()
  if (!aiTitle || aiTitle === '未明确' || aiTitle === '解析失败') return String(currentTitle || '').trim()
  return aiTitle
}

export const aiWorkflowSummary = (workflow: any) => {
  if (!workflow) return ''
  const attempts = Array.isArray(workflow.attempts) ? workflow.attempts : []
  const primary = workflow.primary_provider || attempts[0]?.provider || 'AI'
  const final = workflow.final_provider || attempts.at(-1)?.provider || primary
  const failed = Number(workflow.failed_attempts || attempts.filter((item: any) => item?.status !== 'success').length || 0)
  if (workflow.used_rule_fallback) return `${primary} 已失败 ${failed || attempts.length} 次，当前为规则兜底。`
  return failed > 0 || primary !== final
    ? `${primary} 失败 ${failed} 次，已切换至 ${final} 并生成成功。`
    : `使用 ${final} 生成成功，共尝试 ${attempts.length || 1} 次。`
}

const STORY_ARTIFACT_RE = /(?:---\s*)?块\s*\d+\s*\/\s*(?:docx_xml_text|docx_xml|image_ocr|ocr|table|paragraph|body|段落|正文|图片OCR|表格)[^\n。；]*(?:---)?|(?:---\s*)?\d+\s*\/\s*(?:docx_xml_text|docx_xml|image_ocr|ocr|table|paragraph|body|段落|正文)[^\n。；]*(?:---)?|```(?:json|markdown|text)?|```/gi
const STORY_SECTION_NOISE_RE = /^\s*(?:（[一二三四五六七八九十]+）|\([一二三四五六七八九十]+\)|[一二三四五六七八九十]+[、.．]|第[一二三四五六七八九十]+组)[\s　]*(?:证据|书证|物证|证人证言|被害人供述|被告人供述|鉴定意见|勘验|检查|辨认|视听资料|电子数据|到案经过|户籍证明|前科材料|判决书|裁定书)[\s\S]{0,24}$/
const STORY_JUDICIAL_NOISE_RE = /^(?:审判长|审判员|人民陪审员|书记员|公诉机关|上诉人|原审被告人|关联文书|公告|如不服本判决|刑期从判决执行之日起|本判决为终审判决|审判委员会|代理审判员|附录|目录|证据目录)/

/** 弹窗展示层提纯：剔除文档识别标记、证据目录与文书套话，不改动其他模块数据。 */
export const purifyStoryMaterial = (value: unknown) => {
  let text = String(value || '').replace(/\r/g, '')
  text = text.replace(STORY_ARTIFACT_RE, '')
  text = text.replace(/【文档识别结果】/g, '')
  text = text.replace(/说明：以下内容按\s*(?:DOCX|PDF|OCR)[^\n]*/gi, '')
  const cleaned: string[] = []
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    if (!line) {
      cleaned.push('')
      continue
    }
    if (STORY_SECTION_NOISE_RE.test(line) || STORY_JUDICIAL_NOISE_RE.test(line)) continue
    if (/^(?:块\s*)?\d+$|^[一二三四五六七八九十]+$|^[（(][一二三四五六七八九十]+[）)]$/.test(line)) continue
    cleaned.push(line.replace(/\s*---\s*$/, '').trim())
  }
  return cleaned.join('\n').replace(/\n{3,}/g, '\n\n').trim()
}

export type StorySection = {
  level: 'title' | 'heading'
  title: string
  paragraphs: string[]
  charCount: number
}

/** 按大小标题切分为可收起章节，完整保留全部段落，不做条数截断。 */
export const splitStorySections = (content: unknown): StorySection[] => {
  const text = purifyStoryMaterial(content)
  if (!text) return []
  const lines = text.split('\n')
  const sections: StorySection[] = []
  let current: StorySection | null = null

  const pushParagraph = (paragraph: string) => {
    if (!current) {
      current = {
        level: 'title',
        title: '案件完整剧情',
        paragraphs: [],
        charCount: 0,
      }
      sections.push(current)
    }
    current.paragraphs.push(paragraph)
    current.charCount += paragraph.length
  }

  for (const raw of lines) {
    const line = raw.trim()
    if (!line) continue
    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/)
    const boldOnly = line.match(/^\*\*(.+)\*\*$/)
    const plain = line
      .replace(/^#{1,6}\s*/, '')
      .replace(/^\*\*(.+)\*\*$/, '$1')
      .replace(/\*\*(.+?)\*\*/g, '$1')
      .trim()
    const isTitle = (headingMatch && headingMatch[1].length === 1)
      || /^案件还原剧情$|^案件完整剧情$/.test(plain)
    const isHeading = !isTitle && (
      (headingMatch && headingMatch[1].length >= 2)
      || Boolean(boldOnly)
      || /^(事件全流程|人物证言与还原记忆|证据|案件背景|后续处置)/.test(plain)
      || /^\d+[、.．]/.test(plain)
      || /^第[一二三四五六七八九十百千]+[章节幕]/.test(plain)
    )
    if (isTitle || isHeading) {
      current = {
        level: isTitle ? 'title' : 'heading',
        title: plain,
        paragraphs: [],
        charCount: 0,
      }
      sections.push(current)
      continue
    }
    pushParagraph(plain)
  }

  return sections.filter((section) => section.title || section.paragraphs.length)
}
