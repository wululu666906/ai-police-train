export const normalizeCaseTags = (value: any): string[] => {
  const raw = Array.isArray(value)
    ? value
    : typeof value === 'string'
      ? value.split(/[、,，;\s]+/)
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
