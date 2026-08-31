/** Resolve AI/script role labels onto case person names for scene binding. */

const SPLIT_RE = /[、，,；;\/\|]|以及|及|和|与/

export const splitRoleLabel = (value: unknown): string[] => {
  const text = String(value || '').trim()
  if (!text) return []
  return text
    .split(SPLIT_RE)
    .map((part) => part.trim())
    .filter(Boolean)
}

export const collectCandidateRoleLabels = (scene: Record<string, any> | null | undefined): string[] => {
  if (!scene || typeof scene !== 'object') return []
  const labels: string[] = []
  const push = (value: unknown) => {
    if (Array.isArray(value)) {
      value.forEach((item) => {
        if (item && typeof item === 'object') {
          labels.push(...splitRoleLabel((item as any).role_name || (item as any).name))
        } else {
          labels.push(...splitRoleLabel(item))
        }
      })
      return
    }
    labels.push(...splitRoleLabel(value))
  }
  push(scene.role_names)
  push(scene.roles)
  push(scene.present_roles)
  push(scene.role_training_functions)
  return Array.from(new Set(labels.filter(Boolean)))
}

const personAliases = (person: Record<string, any>): string[] => {
  const names = [String(person?.name || '').trim()]
  const aliases = Array.isArray(person?.aliases) ? person.aliases : []
  aliases.forEach((alias: unknown) => {
    const text = String(alias || '').trim()
    if (text) names.push(text)
  })
  return names.filter(Boolean)
}

export const matchPersonName = (label: string, persons: any[]): string => {
  const needle = String(label || '').trim()
  if (!needle || !Array.isArray(persons) || !persons.length) return ''
  const exact = persons.find((person) => personAliases(person).includes(needle))
  if (exact?.name) return String(exact.name)
  const soft = persons.find((person) =>
    personAliases(person).some((alias) => alias.includes(needle) || needle.includes(alias)),
  )
  return soft?.name ? String(soft.name) : ''
}

export const resolveSceneRoleNames = (
  scene: Record<string, any> | null | undefined,
  persons: any[],
  options?: { fallbackToSpeakable?: boolean; maxRoles?: number },
): string[] => {
  const maxRoles = Math.max(1, Number(options?.maxRoles || 24))
  const fallbackToSpeakable = options?.fallbackToSpeakable !== false
  const matched = Array.from(
    new Set(
      collectCandidateRoleLabels(scene)
        .map((label) => matchPersonName(label, persons))
        .filter(Boolean),
    ),
  )
  if (matched.length) return matched.slice(0, maxRoles)
  if (!fallbackToSpeakable) return []
  const speakable = (persons || [])
    .filter((person) => {
      const status = String(person?.status || '正常')
      return !status.includes('无法交流') && status !== '死亡' && status !== '昏迷'
    })
    .map((person) => String(person?.name || '').trim())
    .filter(Boolean)
  return Array.from(new Set(speakable)).slice(0, Math.min(3, maxRoles))
}

export const normalizeScriptList = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    const items = value.map((item) => String(item || '').trim()).filter(Boolean)
    if (items.length >= 8 && items.every((item) => item.length === 1)) {
      const rejoined = items.join('').trim()
      return rejoined ? [rejoined] : []
    }
    return items.filter((item) => item !== '[object Object]')
  }
  const text = String(value || '').trim()
  if (!text) return []
  if (/[\n；;]/.test(text)) {
    return text
      .split(/[\n；;]+/)
      .map((part) => part.replace(/^\s*[\d一二三四五六七八九十]+[、.．)]\s*/, '').trim())
      .filter(Boolean)
  }
  return [text]
}

export const pickFilledText = (...values: unknown[]): string => {
  for (const value of values) {
    const text = String(value || '').trim()
    if (text) return text
  }
  return ''
}

export const pickFilledList = (...values: unknown[]): any[] => {
  for (const value of values) {
    if (Array.isArray(value) && value.length) return value
  }
  return []
}

const stageNarrativeScore = (stages: unknown): number => {
  if (!Array.isArray(stages) || !stages.length) return 0
  let score = stages.length
  for (const stage of stages) {
    if (!stage || typeof stage !== 'object') continue
    const row = stage as Record<string, any>
    if (Array.isArray(row.learner_actions) && row.learner_actions.length) score += 3
    if (Array.isArray(row.role_pressure_points) && row.role_pressure_points.length) score += 2
    if (Array.isArray(row.expected_stage_effects) && row.expected_stage_effects.length) score += 2
    if (Array.isArray(row.assessment_points) && row.assessment_points.length) score += 1
  }
  return score
}

export const pickRichestStages = (...values: unknown[]): any[] => {
  let best: any[] = []
  let bestScore = -1
  for (const value of values) {
    if (!Array.isArray(value) || !value.length) continue
    const score = stageNarrativeScore(value)
    if (score > bestScore) {
      best = value
      bestScore = score
    }
  }
  return best
}

/** Merge training_scripts / scene_scripts / blueprints onto a persisted scene row. */
export const hydrateSceneFromStructuredScripts = (
  scene: Record<string, any> | null | undefined,
  structuredData: Record<string, any> | null | undefined,
): Record<string, any> => {
  const row = scene && typeof scene === 'object' ? scene : {}
  const structured = structuredData && typeof structuredData === 'object' ? structuredData : {}
  const sceneName = String(row.name || row.scene_name || '').trim()
  const pickByName = (rows: unknown) => {
    if (!Array.isArray(rows)) return {}
    return (
      rows.find((item: any) => String(item?.scene_name || item?.name || '').trim() === sceneName) || {}
    )
  }
  const training: any = pickByName(structured.training_scripts)
  const script: any = pickByName(structured.scene_scripts)
  const blueprint: any = pickByName(structured.scene_blueprints || structured.necessary_scenes)
  return normalizeSceneScriptFields({
    ...blueprint,
    ...script,
    ...training,
    ...row,
    name: pickFilledText(row.name, training.scene_name, script.scene_name, blueprint.scene_name),
    scene_name: pickFilledText(row.scene_name, training.scene_name, script.scene_name, blueprint.scene_name, row.name),
    dispatch_brief: pickFilledText(row.dispatch_brief, training.scene_pack?.dispatch_brief, training.dispatch_brief, script.dispatch_brief, blueprint.dispatch_brief),
    first_impression: pickFilledText(row.first_impression, training.scene_pack?.first_impression, training.first_impression, script.first_impression, blueprint.first_impression),
    training_entry_phase: pickFilledText(row.training_entry_phase, training.scene_pack?.training_entry_phase, script.training_entry_phase, blueprint.training_entry_phase),
    student_role: pickFilledText(row.student_role, training.scene_pack?.student_role, script.student_role, blueprint.student_role, '民警'),
    training_goal: pickFilledText(row.training_goal, training.training_goal, script.training_goal, blueprint.training_goal),
    expected_outcomes: pickFilledList(row.expected_outcomes, training.expected_outcomes, script.expected_outcomes, blueprint.expected_outcomes),
    plot_arc: pickFilledText(row.plot_arc, training.plot_arc, script.plot_arc, blueprint.plot_arc, row.description),
    stages: pickRichestStages(training.stages, script.stages, blueprint.stages, row.stages),
    role_training_functions: pickFilledList(row.role_training_functions, training.role_training_functions, script.role_training_functions, blueprint.role_training_functions),
    completion_criteria: pickFilledList(row.completion_criteria, training.completion_criteria, script.completion_criteria, blueprint.completion_criteria),
    failure_patterns: pickFilledList(row.failure_patterns, training.failure_patterns, script.failure_patterns, blueprint.failure_patterns),
    opening_lines: pickFilledList(row.opening_lines, training.opening_lines, script.opening_lines, blueprint.opening_lines),
    fact_ids: pickFilledList(row.fact_ids, training.fact_ids, script.fact_ids, blueprint.fact_ids),
    roles: pickFilledList(row.roles, row.role_names, script.roles, training.role_training_functions?.map((item: any) => item?.role_name), blueprint.roles),
    role_names: pickFilledList(row.role_names, row.roles, script.role_names, script.roles, blueprint.role_names),
  })
}

export const normalizeSceneScriptFields = (scene: Record<string, any>): Record<string, any> => {
  const source = scene && typeof scene === 'object' ? scene : {}
  const scenePack = source.scene_pack && typeof source.scene_pack === 'object' ? source.scene_pack : {}
  const stages = Array.isArray(source.stages)
    ? source.stages.filter((item: any) => item && typeof item === 'object').map((stage: any) => {
        const learnerActions = normalizeScriptList(stage.learner_actions)
        const points = Array.isArray(stage.assessment_points)
          ? stage.assessment_points.map((point: any, index: number) => {
              if (point && typeof point === 'object') {
                const label = String(point.label || point.assessment_item || point.name || `考核点${index + 1}`).trim()
                const content = String(point.content || point.standard || point.description || label).trim()
                const keywords = normalizeScriptList(point.keywords)
                const relatedActions = normalizeScriptList(point.related_actions || point.actions)
                return {
                  ...point,
                  label,
                  content,
                  keywords: keywords.length ? keywords : (label ? [label] : []),
                  related_actions: relatedActions.length ? relatedActions : learnerActions.slice(0, 3),
                }
              }
              const text = String(point || '').trim()
              return text
                ? {
                    label: `考核点${index + 1}`,
                    content: text,
                    keywords: [text],
                    related_actions: learnerActions.slice(0, 3),
                  }
                : null
            }).filter(Boolean)
          : []
        return {
          ...stage,
          learner_actions: learnerActions,
          role_pressure_points: normalizeScriptList(stage.role_pressure_points),
          expected_stage_effects: normalizeScriptList(stage.expected_stage_effects),
          assessment_points: points,
        }
      })
    : []
  const roleTrainingFunctions = Array.isArray(source.role_training_functions)
    ? source.role_training_functions
        .filter((item: any) => item && typeof item === 'object')
        .flatMap((item: any) => {
          const names = splitRoleLabel(item.role_name)
          if (!names.length) return [{ ...item, role_name: String(item.role_name || '').trim() }]
          return names.map((roleName) => ({ ...item, role_name: roleName }))
        })
    : []
  return {
    ...source,
    scene_name: String(source.scene_name || source.name || '').trim(),
    name: String(source.name || source.scene_name || '').trim(),
    dispatch_brief: String(source.dispatch_brief || scenePack.dispatch_brief || '').trim(),
    first_impression: String(source.first_impression || scenePack.first_impression || '').trim(),
    training_entry_phase: String(source.training_entry_phase || scenePack.training_entry_phase || 'post_incident_onsite').trim(),
    student_role: String(source.student_role || scenePack.student_role || '民警').trim() || '民警',
    training_goal: String(source.training_goal || '').trim(),
    expected_outcomes: normalizeScriptList(source.expected_outcomes),
    plot_arc: String(source.plot_arc || source.scene_description || '').trim(),
    stages,
    role_training_functions: roleTrainingFunctions,
    completion_criteria: normalizeScriptList(source.completion_criteria),
    failure_patterns: normalizeScriptList(source.failure_patterns),
  }
}
