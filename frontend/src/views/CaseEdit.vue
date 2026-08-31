<script setup lang="ts">

import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import RoleCompactForm from '../components/RoleCompactForm.vue'
import SceneOpeningConfigForm from '../components/cases/SceneOpeningConfigForm.vue'
import CaseFactLedger from '../components/cases/CaseFactLedger.vue'
import SceneTrainingContract from '../components/cases/SceneTrainingContract.vue'
import { saveWithCaseQualityGate } from '../utils/caseQuality'
import { normalizeCasePipelineResult, useCasePipeline } from '../composables/useCasePipeline'
import { normalizeSceneScriptFields, resolveSceneRoleNames, hydrateSceneFromStructuredScripts } from '../utils/sceneRoleBinding'
import {
  parseEngineIsFallback,
  parseEngineLabel,
  sceneGenerationIsFallback,
} from '../utils/caseAnalysis'
import {
  buildRoleCompactSummary,
  expandRoleCompactToPerson,
  inferTrainingFocus,
  personToRoleCompact,
  trainingFocusToBehaviorMode,
} from '../utils/roleCompact'
import {
  MAX_ASSESSMENT_POINTS_PER_SCENE,
  assessmentPointCountLabel,
  expectedOutcomeCountLabel,
  buildCaseInfoForAssessment,
  buildSceneInfoForAssessment,
  canAddAssessmentPoint,
  capAssessmentPoints,
  dedupeAssessmentPointsByLabel,
  serializeExpectedOutcomesForSave,
  capExpectedOutcomes,
  dedupeExpectedOutcomes,
} from '../utils/assessmentPoints'
import {
  dedupeStringList,
  PERSON_ALIAS_TO_CANONICAL,
  PERSON_CANONICAL_FIELDS,
} from '../utils/personaTemplate'
import { sceneBucketLabel, SCENE_NAME_PLACEHOLDERS } from '../utils/sceneBucket'
import request from '../utils/request'

const router = useRouter()
const route = useRoute()

const showAdd = ref(false)
const showDetail = ref(false)
const showPreview = ref(false)
const previewCase = ref<any>(null)
const currentStep = ref(0)
const importMode = ref<'plain_case' | 'transcript_file'>('plain_case')
const cases = ref<any[]>([])
const caseSearchText = ref('')
const caseTypeFilter = ref('')
const caseIssueFilter = ref('')
const casesLoading = ref(false)
const casesError = ref('')
const parsing = ref(false)
const generating = ref(false)
const savingCreate = ref(false)
const savingDetail = ref(false)
const supplementingAi = ref(false)
const { job: pipelineJob, isRunning: pipelineIsRunning, startText: startTextPipeline, startFile: startFilePipeline, resume: resumeCasePipeline, clear: clearCasePipeline } = useCasePipeline()
type ReviewModule = 'basic' | 'roles' | 'scenes'
type SceneEditTab = 'overview' | 'roles_copy' | 'flow'

const activeReviewModule = ref<ReviewModule>('basic')
const activeSceneIndex = ref(0)
const activeSceneTab = ref<SceneEditTab>('overview')
const showOriginalExpanded = ref(false)
type LargeTextEditorTarget = {
  source: Record<string, any>
  key: string
  title: string
  fieldLabel: string
  placeholder?: string
}

const largeTextEditor = ref<LargeTextEditorTarget | null>(null)
const showLargeTextEditor = computed({
  get: () => largeTextEditor.value !== null,
  set: (value: boolean) => {
    if (!value) largeTextEditor.value = null
  },
})
const largeTextEditorValue = computed({
  get: () => {
    const target = largeTextEditor.value
    return target ? String(target.source?.[target.key] || '') : ''
  },
  set: (value: string) => {
    const target = largeTextEditor.value
    if (target) target.source[target.key] = value
  },
})

const openLargeTextEditor = (
  source: Record<string, any>,
  key: string,
  title: string,
  fieldLabel: string,
  placeholder = ''
) => {
  largeTextEditor.value = { source, key, title, fieldLabel, placeholder }
}

// ── 角色审核工作台 ────────────────────────────────────────────────
type RoleAuditTab = 'basic' | 'ai_review' | 'audit_log'
const activePersonEditorId = ref<number | null>(null)
const activeRoleAuditTab = ref<RoleAuditTab>('basic')

const roleAuditTabs: Array<{ id: RoleAuditTab; label: string }> = [
  { id: 'basic', label: '基础信息' },
  { id: 'ai_review', label: 'AI 审核建议' },
  { id: 'audit_log', label: '审核记录' },
]

const activeEditablePerson = computed(() => {
  if (activePersonEditorId.value == null) return null
  const persons = editableCase.value?.persons || []
  return persons.find((p: any) => (p._editor_id || null) === activePersonEditorId.value) || null
})

const selectPersonForAudit = (person: any) => {
  activePersonEditorId.value = person._editor_id ?? null
  activeRoleAuditTab.value = 'basic'
}

const addEditablePersonAndSelect = () => {
  addEditablePerson()
  const persons = editableCase.value?.persons || []
  if (persons.length) {
    const last = persons[persons.length - 1]
    activePersonEditorId.value = last._editor_id ?? null
    activeRoleAuditTab.value = 'basic'
  }
}

const removeEditablePersonById = async (editorId: number | null) => {
  if (editorId == null) return
  const persons = editableCase.value?.persons || []
  const index = persons.findIndex((p: any) => p._editor_id === editorId)
  if (index < 0) return
  await removeEditablePerson(index)
  // 删除后自动选中相邻角色
  const remaining = editableCase.value?.persons || []
  if (remaining.length) {
    const nextIndex = Math.min(index, remaining.length - 1)
    activePersonEditorId.value = remaining[nextIndex]?._editor_id ?? null
  } else {
    activePersonEditorId.value = null
  }
}

// 审核状态
type ReviewStatus = 'pending' | 'needs_update' | 'approved'

const REVIEW_STATUS_LABELS: Record<string, string> = {
  pending: '待审核',
  needs_update: '待补充',
  approved: '通过',
}

const REVIEW_STATUS_CLASSES: Record<string, string> = {
  pending: 'role-review-badge--pending',
  needs_update: 'role-review-badge--needs-update',
  approved: 'role-review-badge--approved',
}

const getReviewStatusLabel = (status: string | undefined) =>
  REVIEW_STATUS_LABELS[status || ''] || REVIEW_STATUS_LABELS.pending

const getReviewStatusClass = (status: string | undefined) =>
  REVIEW_STATUS_CLASSES[status || ''] || REVIEW_STATUS_CLASSES.pending

const setPersonReviewStatus = (person: any, status: string) => {
  if (!person) return
  person._review_status = status
  // 追加审核记录
  if (!Array.isArray(person._audit_logs)) person._audit_logs = []
  person._audit_logs.push({
    status,
    reviewer: '管理员',
    time: new Date().toLocaleString('zh-CN', { hour12: false }),
    note: `手动标记为「${REVIEW_STATUS_LABELS[status] || status}」`,
  })
}

// 角色完整度提示
const getPersonCompletenessHint = (person: any) => {
  if (!person) return '信息不完整'
  const missing: string[] = []
  if (!(Array.isArray(person.role_memories) && person.role_memories.length)) missing.push('人物线 / 证言')
  if (!(Array.isArray(person.response_constraints) && person.response_constraints.length)) missing.push('回答边界')
  if (missing.length === 0) return '信息较完整'
  return `缺少：${missing.join('、')}`
}

// AI 审核建议（前端临时实现，调用已有 AI 补全接口）
const runPersonAiReview = async (person: any) => {
  if (!person) return
  person._ai_review_loading = true
  person._ai_review_text = ''
  try {
    // 用已有接口生成角色摘要，这里先做前端简单分析
    await new Promise((resolve) => setTimeout(resolve, 800))
    const hints: string[] = []
    if (!(Array.isArray(person.role_memories) && person.role_memories.length)) hints.push('当前角色还没有来源人物线，请补充其陈述、亲历、所见所闻。')
    if (!(Array.isArray(person.response_constraints) && person.response_constraints.length)) hints.push('当前角色还没有回答边界，建议限制为本人可确认的证言与公开信息。')
    if (!hints.length) hints.push('当前角色人物线与回答边界已具备，可以进入场景配置环节。')
    person._ai_review_text = hints.join('\n\n')
  } finally {
    person._ai_review_loading = false
  }
}

// 时间格式化
const formatDateTime = (dt: string | null | undefined) => {
  if (!dt) return '暂无'
  try {
    return new Date(dt).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return String(dt)
  }
}

const reviewModules: Array<{ id: ReviewModule; label: string; step: string }> = [
  { id: 'basic', label: '基础信息', step: '01' },
  { id: 'roles', label: '角色审核', step: '02' },
  { id: 'scenes', label: '场景编辑', step: '03' },
]

const sceneEditTabs: Array<{ id: SceneEditTab; label: string }> = [
  { id: 'overview', label: '概览' },
  { id: 'roles_copy', label: '角色与文案' },
  { id: 'flow', label: '流程配置' },
]

const setReviewModule = (moduleId: ReviewModule) => {
  activeReviewModule.value = moduleId
}

const setActiveSceneIndex = (index: number) => {
  activeSceneIndex.value = index
  activeSceneTab.value = 'overview'
}

const resolvePersonSceneBehaviorMode = (person: any, caseItem: any = editableCase.value) => {
  const scenes = caseItem?.scenes || []
  const matched = scenes.find((scene: any) => Array.isArray(scene?.role_names) && scene.role_names.includes(person?.name))
  const scene = matched || scenes[activeSceneIndex.value] || scenes[0]
  if (!scene) return '核查取证型'
  return resolveSceneCompactMeta(scene).behavior_mode
}

const resolveSceneCompactMeta = (scene: any) => {
  const focus = inferTrainingFocus(String(scene?.name || ''), '')
  return {
    training_focus: focus,
    behavior_mode: trainingFocusToBehaviorMode(focus),
  }
}

const onSceneTabClick = (tabId: SceneEditTab) => {
  activeSceneTab.value = tabId
  if (tabId === 'flow') {
    const scene = editableCase.value?.scenes?.[activeSceneIndex.value]
    if (scene) ensureSceneAssessmentPointsModel(scene)
  }
}

const activeEditableScene = computed(() => {
  const scenes = editableCase.value?.scenes || []
  if (!scenes.length) return null
  const safeIndex = Math.min(Math.max(activeSceneIndex.value, 0), scenes.length - 1)
  return scenes[safeIndex] || null
})

const caseTypeFilterOptions = computed(() =>
  Array.from(new Set(cases.value.map((item) => String(item?.case_type || '').trim()).filter(Boolean))).sort()
)

const filteredCases = computed(() => {
  const keyword = caseSearchText.value.trim()
  return cases.value.filter((caseItem) => {
    if (caseTypeFilter.value && caseItem.case_type !== caseTypeFilter.value) return false
    const issueCount = getCaseIssueCount(caseItem.id)
    if (caseIssueFilter.value === 'issue' && issueCount <= 0) return false
    if (caseIssueFilter.value === 'ok' && issueCount > 0) return false
    if (!keyword) return true
    const haystack = [caseItem.title, caseItem.case_type, caseItem.background].join(' ')
    return haystack.includes(keyword)
  })
})

const getStageFlowStats = (stage: any) => {
  const points = Array.isArray(stage?.assessment_points) ? stage.assessment_points : []
  const actions = Array.isArray(stage?.action_catalog) ? stage.action_catalog : []
  return { pointCount: points.length, actionCount: actions.length, points, actions }
}

let assessmentPointSeed = 1

const normalizeAssessmentPointEditors = (points: any) => {
  if (!Array.isArray(points)) return []
  return points.map((point: any, index: number) => ({
    ...createPointEditor(point, index),
    _editor_id: Number(point?._editor_id) || assessmentPointSeed++,
    _collapsed: typeof point?._collapsed === 'boolean' ? point._collapsed : true,
    content: resolveAssessmentPointContent(point),
  }))
}

const normalizeAssessmentPointsFromStages = (stagesModel: any[]) => {
  const stages = stagesModel || []
  const primaryStage = stages[0]
  let points: any[] = Array.isArray(primaryStage?.assessment_points) ? [...primaryStage.assessment_points] : []
  if (!points.length && stages.length > 1) {
    for (const stage of stages.slice(1)) {
      if (Array.isArray(stage?.assessment_points)) {
        points.push(...stage.assessment_points)
      }
    }
  }
  points = capAssessmentPoints(dedupeAssessmentPointsByLabel(points))
  return normalizeAssessmentPointEditors(points)
}

const upgradeAssessmentPointEditorContent = (point: any) => {
  if (!point) return ''
  const next = resolveAssessmentPointContent(point)
  if (String(point.content || '').trim() !== next) {
    point.content = next
  }
  return next
}

const ensureSceneAssessmentPointsModel = (scene: any) => {
  if (!scene) return
  if (!Array.isArray(scene.expectedOutcomesModel)) {
    const source = Array.isArray(scene.expected_outcomes) ? scene.expected_outcomes : []
    scene.expectedOutcomesModel = capExpectedOutcomes(source).map((content: string, index: number) => ({
      _editor_id: assessmentPointSeed++,
      content,
      label: content,
    }))
  }
  // Keep legacy model unused; do not migrate old assessment_points for historical cases.
  if (!Array.isArray(scene.assessmentPointsModel)) {
    scene.assessmentPointsModel = []
  }
}

const addAssessmentPointToScene = (scene: any) => {
  if (!scene) return
  ensureSceneAssessmentPointsModel(scene)
  if (!canAddAssessmentPoint(scene)) {
    showToast(`每场景最多 ${MAX_ASSESSMENT_POINTS_PER_SCENE} 条考察点`)
    return
  }
  scene.expectedOutcomesModel.push({
    _editor_id: assessmentPointSeed++,
    content: '',
    label: '',
  })
}

const removeAssessmentPointFromScene = (scene: any, index: number) => {
  if (!scene) return
  ensureSceneAssessmentPointsModel(scene)
  scene.expectedOutcomesModel = (scene.expectedOutcomesModel || []).filter((_: any, i: number) => i !== index)
}

const toggleAssessmentPointCollapsed = (point: any) => {
  if (!point) return
  point._collapsed = !point._collapsed
}

const areAllSceneAssessmentPointsExpanded = (scene: any) => {
  const points = scene?.assessmentPointsModel || []
  return Array.isArray(points) && points.length > 0 && points.every((item: any) => !item?._collapsed)
}

const collapseAllSceneAssessmentPoints = (scene: any) => {
  ensureSceneAssessmentPointsModel(scene)
  for (const item of scene?.assessmentPointsModel || []) {
    item._collapsed = true
  }
}

const expandAllSceneAssessmentPoints = (scene: any) => {
  ensureSceneAssessmentPointsModel(scene)
  for (const item of scene?.assessmentPointsModel || []) {
    item._collapsed = false
  }
}

const toggleAllSceneAssessmentPoints = (scene: any) => {
  if (areAllSceneAssessmentPointsExpanded(scene)) {
    collapseAllSceneAssessmentPoints(scene)
    return
  }
  expandAllSceneAssessmentPoints(scene)
}

const serializeAssessmentPointsForSave = (pointsModel: any[]) => {
  return (Array.isArray(pointsModel) ? pointsModel : []).map((point: any, index: number) => ({
    id: String(point?.id || `ap_${index + 1}`).trim(),
    label: String(point?.label || '').trim(),
    content: resolveAssessmentPointContent(point),
    category: String(point?.category || 'procedure').trim(),
    required: point?.required !== false,
    weight: Number(point?.weight ?? 10),
    keywords: splitTextList(point?.keywordsText),
    knowledge_refs: splitTextList(point?.knowledgeRefsText),
  }))
}

const getApiErrorDetail = (error: any, fallback: string) => {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail.trim()
  if (Array.isArray(detail) && detail.length) {
    return detail.map((item: any) => item?.msg || item?.message || String(item)).filter(Boolean).join('；')
  }
  if (typeof error?.message === 'string' && error.message.trim() && !/^Network Error$/i.test(error.message)) {
    return error.message.trim()
  }
  return fallback
}

const mapApiPointsToEditors = (points: any[]) =>
  normalizeAssessmentPointEditors(points).map((point: any) => ({
    ...point,
    _collapsed: true,
  }))

const replaceSceneAssessmentPoints = (scene: any, points: any[]) => {
  ensureSceneAssessmentPointsModel(scene)
  const outcomes = capExpectedOutcomes(
    (Array.isArray(points) ? points : []).map((item: any) =>
      typeof item === 'string' ? item : String(item?.content || item?.label || item?.text || '').trim()
    )
  )
  scene.expectedOutcomesModel = outcomes.map((content: string) => ({
    _editor_id: assessmentPointSeed++,
    content,
    label: content,
  }))
  scene.expected_outcomes = outcomes
}

const sceneAssessmentFileInputRef = ref<HTMLInputElement | null>(null)
const pendingSceneForFileImport = ref<any>(null)
const sceneAssessmentLoadingKey = ref('')
const sceneAssessmentUploadingKey = ref('')

const sceneAssessmentKey = (scene: any, sceneIndex = -1) => String(scene?.id || sceneIndex)

const isSceneAssessmentLoading = (scene: any) => sceneAssessmentLoadingKey.value === sceneAssessmentKey(scene)
const isSceneAssessmentUploading = (scene: any) => sceneAssessmentUploadingKey.value === sceneAssessmentKey(scene)

const showAssessmentWarnings = (warnings: any) => {
  if (Array.isArray(warnings) && warnings.length) {
    showToast({ type: 'text', message: String(warnings[0]) })
  }
}

const generateAssessmentPointsForScene = async (scene: any, sceneIndex: number) => {
  if (!scene || !editableCase.value) return
  ensureSceneAssessmentPointsModel(scene)
  const key = sceneAssessmentKey(scene, sceneIndex)
  sceneAssessmentLoadingKey.value = key
  scene._assessmentMessage = ''
  try {
    const existing = serializeExpectedOutcomesForSave(scene.expectedOutcomesModel || [])
    const data: any = await request.post(
      '/cases/assessment-points/generate',
      {
        case_info: buildCaseInfoForAssessment(editableCase.value),
        scene_info: {
          ...buildSceneInfoForAssessment(scene, editableCase.value),
          expected_outcomes: existing,
        },
        existing_outcomes: existing,
        use_llm: true,
      },
      { _skipErrorToast: true } as any
    )
    const outcomes = data?.expected_outcomes || data?.outcomes || []
    replaceSceneAssessmentPoints(scene, outcomes)
    scene._assessmentMessage = data?.message || `已更新本场景考察点（${(scene.expectedOutcomesModel || []).length} 条）`
    showAssessmentWarnings(data?.warnings)
    if (!outcomes.length) {
      showToast(getApiErrorDetail(null, '未生成考察点，请检查剧本训练目标后重试'))
      return
    }
    showToast(scene._assessmentMessage)
  } catch (error: any) {
    showToast(getApiErrorDetail(error, '考察点生成失败'))
  } finally {
    if (sceneAssessmentLoadingKey.value === key) {
      sceneAssessmentLoadingKey.value = ''
    }
  }
}


const importAssessmentPasteForScene = async () => {
  showToast('考察点粘贴导入已下线，请使用 AI 追加/刷新或手工编辑考察点')
}


const openSceneAssessmentFilePicker = () => {
  showToast('考察点文件导入已下线，请使用 AI 追加/刷新或手工编辑考察点')
}


const onSceneAssessmentFileChange = async () => {
  showToast('考察点文件导入已下线')
}


const resetReviewWorkspace = () => {
  activeReviewModule.value = 'basic'
  activeSceneIndex.value = 0
  activeSceneTab.value = 'overview'
  showOriginalExpanded.value = false
  activePersonEditorId.value = null
  activeRoleAuditTab.value = 'basic'
}

const auditLoading = ref(false)
const repairing = ref(false)
const selectedCase = ref<any>(null)
const editableCase = ref<any>(null)
const aiParsedData = ref<any>({})
const generatedScenes = ref<any[]>([])
const auditCases = ref<any[]>([])
const fileInputRef = ref<HTMLInputElement | null>(null)
const uploadedFile = ref<File | null>(null)
const fileParseStatus = ref<'idle' | 'ready' | 'parsed' | 'error'>('idle')
const fileMeta = reactive({ name: '', type: '', size: 0 })

const auditSummary = reactive({
  caseCount: 0,
  issueSceneCount: 0,
  lastRepairCount: 0,
})

const caseTypeGroups = [
  { label: '纠纷求助类', options: ['邻里纠纷', '家庭纠纷', '情感纠纷', '劳资纠纷', '消费纠纷', '噪音扰民', '失踪求助', '自杀干预', '校园警情', '宠物纠纷'] },
  { label: '治安案件类', options: ['打架斗殴', '寻衅滋事', '故意伤害', '损毁财物', '醉酒闹事', '赌博', '卖淫嫖娼', '非法侵入住宅'] },
  { label: '刑事案件类', options: ['故意杀人', '盗窃', '抢夺', '诈骗', '电信网络诈骗', '入室盗窃', '抢劫', '敲诈勒索', '涉毒'] },
  { label: '交通警情类', options: ['交通事故', '酒驾醉驾', '肇事逃逸'] },
  { label: '其他', options: ['其他'] },
]

const form = reactive({
  title: '',
  caseTypeGroup: '',
  caseType: '',
  rawText: '',
})

const uploadedFileExtLabel = computed(() => {
  if (!uploadedFile.value) return ''
  return uploadedFile.value.name.split('.').pop()?.toUpperCase() || 'FILE'
})

const fileParseStatusText = computed(() => {
  if (fileParseStatus.value === 'parsed') return '已解析'
  if (fileParseStatus.value === 'ready') return '待解析'
  if (fileParseStatus.value === 'error') return '解析失败'
  return '未上传'
})

const fileParseStatusClass = computed(() => {
  if (fileParseStatus.value === 'parsed') return 'success'
  if (fileParseStatus.value === 'ready') return 'ready'
  if (fileParseStatus.value === 'error') return 'error'
  return ''
})

const canRunAiSupplement = computed(() => Boolean(String(editableCase.value?.original_content || '').trim()))
const areAllParsedPersonsExpanded = computed(() => {
  const persons = aiParsedData.value?.persons || []
  return persons.length > 0 && persons.every((person: any) => !person._collapsed)
})

const areAllEditablePersonsExpanded = computed(() => {
  const persons = editableCase.value?.persons || []
  return persons.length > 0 && persons.every((person: any) => !person._collapsed)
})

const toggleEditablePersonCollapsed = (target: any) => {
  const persons = editableCase.value?.persons || []
  if (!target) return
  const targetId = Number(target._editor_id)
  if (target._collapsed) {
    for (const person of persons) {
      person._collapsed = Number(person._editor_id) !== targetId
    }
    return
  }
  target._collapsed = true
}

const openEditablePersonCard = (target: any) => {
  const persons = editableCase.value?.persons || []
  const targetId = Number(target?._editor_id)
  for (const person of persons) {
    person._collapsed = Number(person._editor_id) !== targetId
  }
}

const expandAllEditablePersons = () => {
  for (const person of editableCase.value?.persons || []) {
    person._collapsed = false
  }
}

const collapseAllEditablePersons = () => {
  for (const person of editableCase.value?.persons || []) {
    person._collapsed = true
  }
}

const toggleAllEditablePersons = () => {
  if (areAllEditablePersonsExpanded.value) {
    collapseAllEditablePersons()
    return
  }
  expandAllEditablePersons()
}

const getEditablePersonCardStyle = (_index: number, person: any) => {
  return {
    marginTop: '0px',
    zIndex: String(person?._collapsed ? 1 : 2),
  }
}

const parseWarnings = (payload: any) => Array.isArray(payload?.parse_warnings) ? payload.parse_warnings : []
const sceneGenerationWarning = (payload: any) => String(payload?.scene_generation_warning || '').trim()

let personEditorSeed = 1

watch(
  () => form.caseType,
  (value) => {
    if (value) {
      form.caseTypeGroup = getCaseTypeGroup(value) || form.caseTypeGroup
    }
  }
)

const safeJsonParse = (value: any, fallback: any) => {
  if (value == null || value === '') return fallback
  if (typeof value !== 'string') return value
  try {
    return JSON.parse(value)
  } catch {
    return fallback
  }
}

const CASE_SCHEMA_VERSION = '2026.05.canonical-v1'

const normalizePersonEditors = (persons: any, options: { collapsed?: boolean } = {}) => {
  if (!Array.isArray(persons)) return []
  return persons.map((person: any) => {
    const sceneMode = resolvePersonSceneBehaviorMode(person, editableCase.value)
    const compactFields = expandRoleCompactToPerson(person, sceneMode)
    return {
      ...compactFields,
      name: String(compactFields?.name || person?.name || '').trim(),
      role: String(person?.role || '').trim(),
      role_type: String(compactFields.role_type || '相关人员').trim() || '相关人员',
      status: String(compactFields.status || '正常').trim() || '正常',
      role_memories: Array.isArray(compactFields.role_memories) ? compactFields.role_memories : [],
      knowledge_ledger: Array.isArray(compactFields.knowledge_ledger) ? compactFields.knowledge_ledger : [],
      response_constraints: Array.isArray(compactFields.response_constraints) ? compactFields.response_constraints : [],
      unresolved_claims: Array.isArray(compactFields.unresolved_claims) ? compactFields.unresolved_claims : [],
      _original_name: String(person?.name || '').trim(),
      _editor_id: Number(person?._editor_id) || personEditorSeed++,
      _collapsed: typeof person?._collapsed === 'boolean' ? person._collapsed : Boolean(options.collapsed),
      _review_status: String(person?._review_status || 'pending') as 'pending' | 'needs_update' | 'approved',
      _audit_logs: Array.isArray(person?._audit_logs) ? person._audit_logs : [],
    }
  })
}

const buildEmptyPerson = (index: number, options: { collapsed?: boolean } = {}) => normalizePersonEditors([{
  name: `新增角色${index}`,
  role: '相关人员',
  role_type: '相关人员',
  status: '正常',
  scene_behavior_mode: '核查取证型',
  role_memories: [],
  knowledge_ledger: [],
  response_constraints: ['只陈述本人亲历、亲眼所见或原文明确记载的内容。'],
  unresolved_claims: [],
  persona_source: 'source_grounded_role_memory',
  persona_contract_version: 'role_memory_v2',
}], options)[0]

const parsedPersons = (payload: any) => {
  if (!payload) return []
  if (!Array.isArray(payload.persons)) {
    payload.persons = []
  }
  return payload.persons
}
const getPersonListText = (value: any) => (Array.isArray(value) ? value : []).join('\n')

const toComparableList = (value: any) => {
  if (Array.isArray(value)) return dedupeStringList(value)
  const text = String(value || '').trim()
  return text ? [text] : []
}

const listEquals = (left: any, right: any) => {
  const leftList = toComparableList(left)
  const rightList = toComparableList(right)
  if (leftList.length !== rightList.length) return false
  return leftList.every((item, idx) => item === rightList[idx])
}

const getPersonDedupInsights = (person: any) => {
  const issues: string[] = []
  const memories = Array.isArray(person?.role_memories) ? person.role_memories : []
  const mergedPreview = [
    memories.length ? `人物线=${memories.length}条` : '',
    person?.unresolved_claims?.length ? `待核实=${person.unresolved_claims.length}项` : '',
    person?.response_constraints?.length ? `回答边界=${person.response_constraints.length}条` : '',
  ].filter(Boolean)

  return { issues, mergedPreview }
}

const getCompactPersonaSummary = (person: any) =>
  buildRoleCompactSummary(personToRoleCompact(person, resolvePersonSceneBehaviorMode(person)))

const togglePersonCollapsed = (target: any) => {
  const persons = aiParsedData.value?.persons || []
  if (!target) return
  const targetId = Number(target._editor_id)
  if (target._collapsed) {
    for (const person of persons) {
      person._collapsed = Number(person._editor_id) !== targetId
    }
    return
  }
  target._collapsed = true
}

const openParsedPersonCard = (target: any) => {
  const persons = aiParsedData.value?.persons || []
  const targetId = Number(target?._editor_id)
  for (const person of persons) {
    person._collapsed = Number(person._editor_id) !== targetId
  }
}

const expandAllParsedPersons = () => {
  for (const person of aiParsedData.value?.persons || []) {
    person._collapsed = false
  }
}

const collapseAllParsedPersons = () => {
  for (const person of aiParsedData.value?.persons || []) {
    person._collapsed = true
  }
}

const toggleAllParsedPersons = () => {
  if (areAllParsedPersonsExpanded.value) {
    collapseAllParsedPersons()
    return
  }
  expandAllParsedPersons()
}

const getParsedPersonCardStyle = (_index: number, person: any) => {
  return {
    marginTop: '0px',
    zIndex: String(person?._collapsed ? 1 : 2),
  }
}

const updateSceneNamesForPersonRename = (scenes: any[], oldName: string, nextName: string) => {
  for (const scene of scenes || []) {
    const roleNames = Array.isArray(scene?.role_names) ? scene.role_names : []
    scene.role_names = Array.from(new Set(roleNames.map((item: string) => item === oldName ? nextName : item).filter(Boolean)))
    if (scene.primary_role_name === oldName) {
      scene.primary_role_name = nextName
    }
    if (Array.isArray(scene?.roles)) {
      scene.roles = scene.roles.map((item: string) => item === oldName ? nextName : item).filter(Boolean)
    }
  }
}

const removePersonFromContainer = (container: any, index: number) => {
  const persons = Array.isArray(container?.persons) ? container.persons : []
  const removed = persons[index]
  if (!removed) return
  const removedName = String(removed.name || '').trim()
  persons.splice(index, 1)
  for (const scene of container?.scenes || []) {
    scene.role_names = (Array.isArray(scene?.role_names) ? scene.role_names : []).filter((item: string) => item !== removedName)
    if (scene.primary_role_name === removedName) {
      scene.primary_role_name = scene.role_names?.[0] || ''
    }
    if (Array.isArray(scene?.roles)) {
      scene.roles = scene.roles.filter((item: string) => item !== removedName)
    }
  }
}

const applyPersonCompactUpdate = (container: any, person: any, next: Record<string, any>) => {
  const oldName = String(person?._original_name || person?.name || '').trim()
  Object.assign(person, next)
  const nextName = String(person?.name || '').trim()
  if (oldName && nextName && oldName !== nextName) {
    updateSceneNamesForPersonRename(container?.scenes || [], oldName, nextName)
  }
  if (nextName) person._original_name = nextName
}

const removeParsedPerson = async (index: number) => {
  const target = parsedPersons(aiParsedData.value)?.[index]
  if (!target) return
  try {
    await showConfirmDialog({
      title: '删除角色',
      message: `确定删除角色“${target.name || '未命名角色'}”吗？删除后不会进入后续角色模板和训练场景。`,
      confirmButtonColor: '#dc2626',
    })
  } catch {
    return
  }
  removePersonFromContainer(aiParsedData.value, index)
}

const removeEditablePerson = async (index: number) => {
  const target = editableCase.value?.persons?.[index]
  if (!target) return
  try {
    await showConfirmDialog({
      title: '删除角色',
      message: `确定删除角色“${target.name || '未命名角色'}”吗？保存后它会从案件角色模板和场景分配里一并移除。`,
      confirmButtonColor: '#dc2626',
    })
  } catch {
    return
  }
  removePersonFromContainer(editableCase.value, index)
}

const addPersonToContainer = (container: any) => {
  if (!container) return
  if (!Array.isArray(container.persons)) container.persons = []
  const nextIndex = container.persons.length + 1
  container.persons.push(buildEmptyPerson(nextIndex, { collapsed: false }))
}

const addParsedPerson = () => addPersonToContainer(aiParsedData.value)
const addEditablePerson = () => addPersonToContainer(editableCase.value)

const validatePersonsBeforeSave = (persons: any[], caseItem: any = editableCase.value) => {
  const seenNames = new Set<string>()
  for (const person of persons || []) {
    const sceneMode = resolvePersonSceneBehaviorMode(person, caseItem)
    const normalized = expandRoleCompactToPerson(person, sceneMode)
    Object.assign(person, normalized, {
      role: String(person?.role || '').trim(),
      _original_name: String(normalized.name || person?.name || '').trim(),
    })

    const name = String(person.name || '').trim()
    if (!name) {
      showToast('角色姓名不能为空，请先完成人工审核')
      return false
    }
    if (seenNames.has(name)) {
      showToast(`角色姓名“${name}”重复，请先修正后再保存`)
      return false
    }
    seenNames.add(name)
  }
  return true
}

const serializePersonsForSave = (persons: any[]) => {
  return (persons || []).map((person: any) => {
    const sceneMode = resolvePersonSceneBehaviorMode(person)
    const normalized = expandRoleCompactToPerson(person, sceneMode) as Record<string, any>
    const cloned: Record<string, any> = { ...normalized, role: String(person?.role || '').trim() }
    for (const [alias, canonical] of Object.entries(PERSON_ALIAS_TO_CANONICAL)) {
      if (!cloned[canonical] && cloned[alias]) cloned[canonical] = cloned[alias]
    }
    delete cloned._editor_id
    delete cloned._original_name
    delete cloned._collapsed
    delete cloned._review_status
    delete cloned._audit_logs
    delete cloned._ai_review_text
    delete cloned._ai_review_loading
    for (const field of [
      'behavior_archetype', 'opening_preset', 'current_goal', 'current_need', 'core_concern', 'weakness',
      'relationship_pressure', 'surface_stance', 'pressure_response', 'trigger_points', 'calming_points',
      'police_attitude', 'interaction_style', 'personality', 'speaking_style', 'authority_attitude',
      'stress_response', 'public_mask', 'private_drive', 'self_image', 'known_key_points',
      'withheld_key_points', 'hidden_truths', 'does_not_know', 'cannot_answer',
    ]) delete cloned[field]
    cloned.role_template_version = 'source_memory_v2'
    return cloned
  })
}

const splitTextList = (value: any) =>
  String(value || '')
    .split(/[,，\n]/)
    .map((item) => item.trim())
    .filter(Boolean)

const inferAssessmentPointContent = (label: string, category = 'procedure') => {
  const text = String(label || '').trim()
  if (!text) return ''
  if (text.includes('结果可被对话关键词或执法动作核查')) {
    const head = text.split('，结果可被')[0].replace(/。$/, '').trim()
    const core = head.replace(/^学员在训练对话或现场处置中应做到：/, '').trim()
    return inferAssessmentPointContent(core || text, category)
  }
  if (text.includes('怎样算完成')) return text
  if (text.length >= 48 && /[。；?？]/.test(text)) return text
  const passTail =
    category === 'risk'
      ? `怎样算完成：回放训练记录时，能听出你已就「${text}」追问或说明了风险情况，并给出下一步处置思路，而不是只问一句「有没有事」就结束。`
      : category === 'evidence'
        ? `怎样算完成：回放训练记录时，能听出或看出你已就「${text}」提出取证/记录要求，并有相应话术或现场动作说明，而不是口头带过。`
        : `怎样算完成：回放训练记录时，能听出你已就「${text}」向当事人追问或说明了具体内容，对方也有相应回答；若只问一句、对方没展开、你也不追问，则视为未完成。`
  const detail =
    category === 'risk'
      ? '须结合本案判断风险是否仍在发生，追问受伤、持械、人员数量、是否需要增援等，并说明处置或上报倾向。'
      : category === 'evidence'
        ? '须告知取证/记录安排，说明将采取何种固定措施，并简要说明依据或目的。'
        : '须围绕本案追问与该项相关的具体细节，避免只核实姓名、电话等表层信息。'
  return `学员在训练对话或现场处置中应做到：${text}。\n具体要求：${detail}\n${passTail}`
}

const isShallowAssessmentContent = (label: string, content: string) => {
  const cleanLabel = String(label || '').trim()
  const cleanContent = String(content || '').trim()
  if (!cleanContent) return true
  if (cleanContent.length < 36) return true
  if (cleanContent.includes('结果可被对话关键词或执法动作核查')) return true
  if (cleanContent.includes('可被对话或现场动作中可被核查') || cleanContent.includes('在对话或现场处置中可被观察到')) return true
  if (
    cleanLabel &&
    (cleanContent === `学员应完成：${cleanLabel}。` ||
      cleanContent === `学员在训练对话或现场处置中应做到：${cleanLabel}，结果可被对话关键词或执法动作核查。`)
  ) {
    return true
  }
  return Boolean(cleanLabel && cleanContent.includes(cleanLabel) && cleanContent.length <= cleanLabel.length + 18)
}

const resolveAssessmentPointContent = (point: any) => {
  const label = String(point?.label || '').trim()
  const category = String(point?.category || 'procedure')
  const direct = String(point?.content || point?.requirement || point?.description || '').trim()
  if (!direct || isShallowAssessmentContent(label, direct)) {
    return inferAssessmentPointContent(label, category)
  }
  return direct
}

const createPointEditor = (point: any = {}, index = 0) => ({
  id: String(point?.id || `ap_${index + 1}`),
  label: String(point?.label || ''),
  content: resolveAssessmentPointContent(point),
  category: String(point?.category || 'procedure'),
  required: point?.required !== false,
  weight: Number(point?.weight ?? 10),
  keywordsText: Array.isArray(point?.keywords) ? point.keywords.join(', ') : '',
  knowledgeRefsText: Array.isArray(point?.knowledge_refs) ? point.knowledge_refs.join(', ') : '',
})

const createActionEditor = (action: any = {}, index = 0) => ({
  id: String(action?.id || `act_${index + 1}`),
  label: String(action?.label || ''),
  type: String(action?.type || 'physical'),
  aliasesText: Array.isArray(action?.aliases) ? action.aliases.join(', ') : '',
  countsForText: Array.isArray(action?.counts_for) ? action.counts_for.join(', ') : '',
})

const createStageEditor = (stage: any = {}, index = 0) => ({
  stage_name: String(stage?.stage_name || stage?.name || `阶段 ${index + 1}`),
  stage_goal: String(stage?.stage_goal || stage?.goal || stage?.description || ''),
  recommended_prompts_text: Array.isArray(stage?.recommended_prompts)
    ? stage.recommended_prompts.join('\n')
    : '',
  assessment_points: Array.isArray(stage?.assessment_points) ? stage.assessment_points.map((point: any, pointIndex: number) => createPointEditor(point, pointIndex)) : [],
  action_catalog: Array.isArray(stage?.action_catalog) ? stage.action_catalog.map((action: any, actionIndex: number) => createActionEditor(action, actionIndex)) : [],
  completion_rules: {
    min_user_turns: Number(stage?.completion_rules?.min_user_turns ?? 3),
    required_point_ids_text: Array.isArray(stage?.completion_rules?.required_point_ids) ? stage.completion_rules.required_point_ids.join(', ') : '',
    required_action_ids_text: Array.isArray(stage?.completion_rules?.required_action_ids) ? stage.completion_rules.required_action_ids.join(', ') : '',
  },
  end_conditions: {
    must_complete_current_stage: stage?.end_conditions?.must_complete_current_stage !== false,
    required_point_ids_text: Array.isArray(stage?.end_conditions?.required_point_ids) ? stage.end_conditions.required_point_ids.join(', ') : '',
    required_action_ids_text: Array.isArray(stage?.end_conditions?.required_action_ids) ? stage.end_conditions.required_action_ids.join(', ') : '',
    closure_actions_text: Array.isArray(stage?.end_conditions?.closure_actions) ? stage.end_conditions.closure_actions.join(', ') : '',
    closing_script: String(stage?.end_conditions?.closing_script || ''),
  },
})

const normalizeStageEditors = (value: any) => {
  const stages = safeJsonParse(value, [])
  return Array.isArray(stages) ? stages.map((stage: any, index: number) => createStageEditor(stage, index)) : []
}

const splitPromptLines = (value: string) =>
  String(value || '')
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)

const serializeStageEditors = (stages: any[]) =>
  (Array.isArray(stages) ? stages : []).map((stage: any) => ({
    stage_name: String(stage?.stage_name || '').trim(),
    stage_goal: String(stage?.stage_goal || '').trim(),
    recommended_prompts: splitPromptLines(stage?.recommended_prompts_text),
    assessment_points: (Array.isArray(stage?.assessment_points) ? stage.assessment_points : []).map((point: any, index: number) => ({
      id: String(point?.id || `ap_${index + 1}`).trim(),
      label: String(point?.label || '').trim(),
      category: String(point?.category || 'procedure').trim(),
      required: point?.required !== false,
      weight: Number(point?.weight ?? 10),
      keywords: splitTextList(point?.keywordsText),
      knowledge_refs: splitTextList(point?.knowledgeRefsText),
    })),
    action_catalog: (Array.isArray(stage?.action_catalog) ? stage.action_catalog : []).map((action: any, index: number) => ({
      id: String(action?.id || `act_${index + 1}`).trim(),
      label: String(action?.label || '').trim(),
      type: String(action?.type || 'physical').trim(),
      aliases: splitTextList(action?.aliasesText),
      counts_for: splitTextList(action?.countsForText),
    })),
    completion_rules: {
      min_user_turns: Number(stage?.completion_rules?.min_user_turns ?? 3),
      required_point_ids: splitTextList(stage?.completion_rules?.required_point_ids_text),
      required_action_ids: splitTextList(stage?.completion_rules?.required_action_ids_text),
    },
    end_conditions: {
      must_complete_current_stage: stage?.end_conditions?.must_complete_current_stage !== false,
      required_point_ids: splitTextList(stage?.end_conditions?.required_point_ids_text),
      required_action_ids: splitTextList(stage?.end_conditions?.required_action_ids_text),
      closure_actions: splitTextList(stage?.end_conditions?.closure_actions_text),
      closing_script: String(stage?.end_conditions?.closing_script || '').trim(),
    },
  }))

const syncSceneStagesText = (scene: any) => {
  scene.stagesText = JSON.stringify(serializeStageEditors(scene?.stagesModel || []), null, 2)
}

const addStageToScene = (scene: any) => {
  scene.stagesModel = [...(scene?.stagesModel || []), createStageEditor({}, (scene?.stagesModel || []).length)]
  syncSceneStagesText(scene)
}

const removeStageFromScene = (scene: any, stageIndex: number) => {
  scene.stagesModel = (scene?.stagesModel || []).filter((_: any, index: number) => index !== stageIndex)
  syncSceneStagesText(scene)
}

void activeEditableScene
void getStageFlowStats
void getPersonDedupInsights
void addStageToScene
void removeStageFromScene

const normalizeSceneEditors = (scenes: any, structuredData: any, persons: any[]) => {
  const sceneRoleMap = structuredData?.scene_role_map || {}
  return (scenes || []).map((scene: any) => {
    const sceneName = String(scene?.name || '').trim()
    const source = hydrateSceneFromStructuredScripts(scene, structuredData)
    const mapped = sceneRoleMap?.[sceneName] || {}
    const mappedRoles = Array.isArray(mapped?.role_names) ? mapped.role_names.filter(Boolean) : []
    const normalizedRoleNames = resolveSceneRoleNames(
      {
        ...source,
        role_names: mappedRoles.length ? mappedRoles : source.role_names,
        roles: mappedRoles.length ? mappedRoles : source.roles,
      },
      persons,
    )
    const mappedPrimaryRoleName = String(mapped?.primary_role_name || '').trim()
    const recommendedPrimaryRoleName = pickRecommendedPrimaryRoleName(persons, normalizedRoleNames)
    const stagesModel = normalizeStageEditors(source.stages)
    return {
      ...source,
      _assessmentPaste: String(scene?._assessmentPaste || ''),
      _assessmentMessage: String(scene?._assessmentMessage || ''),
      stagesText: stringifyStages(source.stages),
      stagesModel,
      stagesAdvanced: false,
      assessmentPointsModel: [],
      expectedOutcomesModel: capExpectedOutcomes(source.expected_outcomes || []).map((content: string) => ({
        _editor_id: assessmentPointSeed++,
        content,
        label: content,
      })),
      role_names: normalizedRoleNames,
      roles: normalizedRoleNames,
      present_roles: normalizedRoleNames,
      primary_role_name: normalizedRoleNames.includes(mappedPrimaryRoleName)
        ? mappedPrimaryRoleName
        : (recommendedPrimaryRoleName || normalizedRoleNames[0] || ''),
    }
  })
}

const pickRecommendedPrimaryRoleName = (persons: any[], roleNames: string[]) => {
  const candidates = (persons || []).filter((person: any) => roleNames.includes(person.name))
  if (!candidates.length) return ''

  const ranked = candidates
    .map((person: any) => {
      let score = 0
      const status = String(person.status || '正常')
      const roleType = String(person.role_type || person.role || '')
      const knowsFactsCount = Array.isArray(person.knows_facts) ? person.knows_facts.length : 0
      const hiddenTruthsCount = Array.isArray(person.hidden_truths) ? person.hidden_truths.length : 0
      const interactionStyle = String(person.interaction_style || '')

      if (!status.includes('无法交流') && !['死亡', '昏迷'].includes(status)) score += 3
      if (['证人', '嫌疑人', '被害人'].includes(roleType)) score += 2
      score += Math.min(knowsFactsCount, 3)
      score += Math.min(hiddenTruthsCount, 2)
      if (interactionStyle.includes('观察') || interactionStyle.includes('情绪') || interactionStyle.includes('对抗')) score += 1

      return { name: person.name, score }
    })
    .sort((a: { score: number }, b: { score: number }) => b.score - a.score)

  return ranked[0]?.name || roleNames[0] || ''
}

const toggleSceneRole = (scene: any, roleName: string) => {
  const current = Array.isArray(scene?.role_names) ? scene.role_names : []
  if (current.includes(roleName)) {
    scene.role_names = current.filter((item: string) => item !== roleName)
  } else {
    scene.role_names = [...current, roleName]
  }
  scene.roles = [...(scene.role_names || [])]
  scene.present_roles = [...(scene.role_names || [])]
  if (!scene.role_names.length) {
    scene.primary_role_name = ''
  } else if (!scene.role_names.includes(scene.primary_role_name)) {
    scene.primary_role_name = scene.role_names[0]
  }
}

const getSceneRoleCandidates = (caseItem: any, scene: any) => {
  const selectedNames = Array.isArray(scene?.role_names) ? scene.role_names : []
  return (caseItem?.persons || []).filter((person: any) => selectedNames.includes(person.name))
}

const getSceneRoleRecommendation = (caseItem: any, scene: any) => {
  const candidates = getSceneRoleCandidates(caseItem, scene)
  if (!candidates.length) return null

  const scored = candidates.map((person: any) => {
    let score = 0
    const reasons: string[] = []
    const roleType = String(person.role_type || person.role || '')
    const knowsFactsCount = Array.isArray(person.knows_facts) ? person.knows_facts.length : 0
    const hiddenTruthsCount = Array.isArray(person.hidden_truths) ? person.hidden_truths.length : 0
    const status = String(person.status || '正常')

    if (!status.includes('无法交流') && status !== '死亡' && status !== '昏迷') {
      score += 3
      reasons.push('可正常交流')
    }
    if (knowsFactsCount > 0) {
      score += Math.min(knowsFactsCount, 3)
      reasons.push(`掌握 ${knowsFactsCount} 条已知事实`)
    }
    if (hiddenTruthsCount > 0) {
      score += Math.min(hiddenTruthsCount, 2)
      reasons.push(`带有 ${hiddenTruthsCount} 个可压实隐瞒点`)
    }
    if (['证人', '嫌疑人', '被害人'].includes(roleType)) {
      score += 2
      reasons.push(`角色类型是${roleType}`)
    }
    if (String(person.interaction_style || '').includes('观察') || String(person.interaction_style || '').includes('情绪')) {
      score += 1
      reasons.push('有明显问询反应特征')
    }

    return {
      name: person.name,
      score,
      reason: reasons.join('，') || '信息相对完整',
    }
  }).sort((a: { score: number }, b: { score: number }) => b.score - a.score)

  return scored[0] || null
}

const getSceneUnsuitableRoleHints = (caseItem: any, scene: any) => {
  return getSceneRoleCandidates(caseItem, scene)
    .filter((person: any) => {
      const status = String(person.status || '正常')
      return status.includes('无法交流') || status === '死亡' || status === '昏迷' || !(Array.isArray(person.knows_facts) && person.knows_facts.length)
    })
    .map((person: any) => {
      const status = String(person.status || '正常')
      if (status.includes('无法交流') || status === '死亡' || status === '昏迷') {
        return `${person.name} 当前状态为“${status}”，不适合作为主对话人。`
      }
      return `${person.name} 当前可直接输出的已知事实较少，更适合作为辅助角色或补充对象。`
    })
}

const getScenePrimaryRoleSummary = (caseItem: any, scene: any) => {
  const person = (caseItem?.persons || []).find((item: any) => item.name === scene?.primary_role_name)
  if (!person) return '当前未匹配到对应角色模板。'
  const memories = Array.isArray(person.role_memories) ? person.role_memories : []
  const first = memories[0]
  const latest = memories[memories.length - 1]
  return `主对话人有 ${memories.length} 条来源人物线。${first?.statement || '暂无可直接引用的证言'}${latest && latest !== first ? `；后续：${latest.statement}` : ''}`
}

const stringifyStages = (value: any) => JSON.stringify(safeJsonParse(value, []), null, 2)
const getStructuredData = (caseItem: any) => safeJsonParse(caseItem?.structured_data, {})
const resolveOriginalContent = (payload: any, fallback = '') => {
  const structuredData = getStructuredData(payload)
  return String(
    payload?.original_content
      || structuredData?.rawText
      || structuredData?.original_content
      || structuredData?.extracted_text_full
      || structuredData?.extracted_text_preview
      || fallback
      || ''
  )
}

const getTypesByGroup = (groupLabel: string) => caseTypeGroups.find((item) => item.label === groupLabel)?.options || []
const getCaseTypeGroup = (caseType: string) => caseTypeGroups.find((group) => group.options.includes(caseType))?.label || ''
const showTypeNormalizationHint = (payload: any) => Boolean(payload?.ai_case_type_raw && payload?.case_type && payload.ai_case_type_raw !== payload.case_type)
const shouldWarnOnTitle = (title: string) => !/[\p{L}\p{N}]/u.test(String(title || '').trim())

const formatFileSize = (size: number) => {
  if (!size) return '0 B'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

const normalizeEditableCase = (caseItem: any) => {
  const structuredData = getStructuredData(caseItem)
  const cloned = JSON.parse(JSON.stringify(caseItem))
  const normalizedPersons = normalizePersonEditors(structuredData.persons || [], { collapsed: true })
  return {
    ...cloned,
    original_content: resolveOriginalContent(cloned),
    ai_case_type_raw: structuredData.ai_case_type_raw || '',
    parse_engine: structuredData.parse_engine || '',
    parse_warnings: Array.isArray(structuredData.parse_warnings) ? structuredData.parse_warnings : [],
    scene_generation_mode: structuredData.scene_generation_mode || '',
    scene_generation_warning: structuredData.scene_generation_warning || '',
    case_type_group: getCaseTypeGroup(cloned.case_type),
    persons: normalizedPersons,
    scenes: normalizeSceneEditors(cloned.scenes || [], structuredData, normalizedPersons),
  }
}

const refreshCasesPage = async () => {
  await Promise.all([fetchCases(), fetchSceneRoleAudit()])
}

const fetchCases = async () => {
  casesLoading.value = true
  casesError.value = ''
  try {
    let res: any = await request.get('/cases/', { _skipErrorToast: true } as any)
    if (typeof res === 'string' && res.toLowerCase().includes('<!doctype html')) {
      res = await request.get('/cases/', { _skipErrorToast: true } as any)
    }
    cases.value = Array.isArray(res) ? [...res] : []
    const focusId = Number(route.query.case_id)
    if (focusId) {
      const target = cases.value.find((item: any) => item.id === focusId)
      if (target) {
        editCase(target)
      }
    }
  } catch (error) {
    console.error('Fetch cases error:', error)
    cases.value = []
    casesError.value = '案件列表加载失败，请稍后重试。'
  } finally {
    casesLoading.value = false
  }
}

const fetchSceneRoleAudit = async () => {
  auditLoading.value = true
  try {
    const res: any = await request.get('/cases/scene-role-audit', { _skipErrorToast: true } as any)
    auditCases.value = res.cases || []
    auditSummary.caseCount = res.case_count || 0
    auditSummary.issueSceneCount = res.issue_scene_count || 0
  } catch {
    showToast('场景人物校验加载失败')
  } finally {
    auditLoading.value = false
  }
}

const repairSceneRoles = async () => {
  repairing.value = true
  try {
    const res: any = await request.post('/cases/scene-role-repair', {}, { _skipErrorToast: true } as any)
    auditSummary.lastRepairCount = res.repaired_scene_count || 0
    if (res.audit) {
      auditCases.value = res.audit.cases || []
      auditSummary.caseCount = res.audit.case_count || 0
      auditSummary.issueSceneCount = res.audit.issue_scene_count || 0
    }
    showToast({ type: 'success', message: `已修复 ${auditSummary.lastRepairCount} 个场景` })
  } catch {
    showToast('场景人物修复失败')
  } finally {
    repairing.value = false
  }
}

const getCaseAudit = (caseId: number) => auditCases.value.find((item: any) => item.case_id === caseId)
const getCaseIssueCount = (caseId: number) => getCaseAudit(caseId)?.issue_scene_count || 0

const resetCreateState = () => {
  currentStep.value = 0
  form.title = ''
  form.caseTypeGroup = ''
  form.caseType = ''
  form.rawText = ''
  importMode.value = 'plain_case'
  aiParsedData.value = {}
  generatedScenes.value = []
  clearUploadedFile()
}

const openAddModal = () => {
  if (pipelineIsRunning.value || pipelineJob.value) {
    currentStep.value = 1
    showAdd.value = true
    return
  }
  resetCreateState()
  showAdd.value = true
}

const switchImportMode = (mode: 'plain_case' | 'transcript_file') => {
  importMode.value = mode
  aiParsedData.value = {}
  generatedScenes.value = []
  currentStep.value = 0
}

const chooseFile = () => fileInputRef.value?.click()

const clearUploadedFile = () => {
  uploadedFile.value = null
  fileParseStatus.value = 'idle'
  fileMeta.name = ''
  fileMeta.type = ''
  fileMeta.size = 0
  if (fileInputRef.value) fileInputRef.value.value = ''
}

const handleFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  const lowerName = file.name.toLowerCase()
  if (!['.pdf', '.docx', '.txt', '.md', '.markdown'].some((ext) => lowerName.endsWith(ext))) {
    fileParseStatus.value = 'error'
    showToast('仅支持 PDF、DOCX、TXT、MD 文件')
    target.value = ''
    return
  }
  if (file.size > 20 * 1024 * 1024) {
    fileParseStatus.value = 'error'
    showToast('文件大小不能超过 20MB')
    target.value = ''
    return
  }

  uploadedFile.value = file
  fileParseStatus.value = 'ready'
  fileMeta.name = file.name
  fileMeta.type = file.name.split('.').pop()?.toUpperCase() || ''
  fileMeta.size = file.size
}

const normalizeGeneratedScenesFromPipeline = (scenes: any[], persons: any[]) => {
  return (Array.isArray(scenes) ? scenes : []).map((scene: any) => {
    const baseRoleNames = Array.isArray(scene?.roles)
      ? scene.roles
      : Array.isArray(scene?.role_names)
        ? scene.role_names
        : []
    const presentRoleNames = Array.isArray(scene?.present_roles) ? scene.present_roles : []
    const isOnsiteScene = String(scene?.training_entry_phase || scene?.scene_kind || scene?.scene_name || '').includes('现场')
      || String(scene?.training_entry_phase || '') === 'post_incident_onsite'
    const roleNames = Array.from(new Set((isOnsiteScene ? [...presentRoleNames, ...baseRoleNames] : baseRoleNames).filter(Boolean)))
    return {
      ...scene,
      roles: roleNames,
      role_names: roleNames,
      present_roles: presentRoleNames.length ? presentRoleNames : roleNames,
      opening_config: scene.opening_config || {
        enabled: true,
        mode: 'dynamic',
        speaker_role_ids: [],
        speaker_names: roleNames.slice(0, 3),
        director_note: '',
        preset_turns: [],
      },
      primary_role_name: scene.primary_role_name || pickRecommendedPrimaryRoleName(persons || [], roleNames) || roleNames[0] || '',
    }
  })
}

const applyPipelineJobResult = (rawResult: any) => {
  const normalized = normalizeCasePipelineResult(rawResult)
  const res: any = normalized.caseInfo || {}
  aiParsedData.value = {
    ...res,
    scene_ai_workflow: normalized.sceneAiWorkflow,
    ai_workflows: normalized.aiWorkflows,
  }
  aiParsedData.value.persons = normalizePersonEditors(aiParsedData.value.persons || [], { collapsed: true })
  generatedScenes.value = normalizeGeneratedScenesFromPipeline(normalized.scenes, aiParsedData.value.persons || [])
  return res
}

const startParsing = async () => {
  parsing.value = true
  try {
    clearCasePipeline()
    generatedScenes.value = []
    if (importMode.value === 'transcript_file') {
      if (!uploadedFile.value) {
        showToast('请先上传笔录文件')
        return
      }
      const job = await startFilePipeline(uploadedFile.value)
      const res: any = applyPipelineJobResult(job.result || {})
      if (parseEngineIsFallback(res)) {
        showToast('本次为规则兜底解析，请人工复核后再发布')
      }
      fileParseStatus.value = 'parsed'
      if (!form.title) form.title = res.case_name || ''
      if (!form.caseType) form.caseType = res.case_type || ''
      form.caseTypeGroup = getCaseTypeGroup(form.caseType)
      fileMeta.name = res.file_meta?.name || fileMeta.name
      fileMeta.type = res.file_meta?.type || fileMeta.type
      fileMeta.size = res.file_meta?.size || fileMeta.size
      return
    }

    const job = await startTextPipeline(form.rawText)
    const res: any = applyPipelineJobResult(job.result || {})
    if (parseEngineIsFallback(res)) {
      showToast('本次为规则兜底解析，请人工复核后再发布')
    }
    if (!form.caseType) form.caseType = res.case_type || ''
    form.caseTypeGroup = getCaseTypeGroup(form.caseType)
  } catch (error: any) {
    if (importMode.value === 'transcript_file') fileParseStatus.value = 'error'
    showToast(getApiErrorDetail(error, 'AI 解析失败'))
    throw new Error('parse-failed')
  } finally {
    parsing.value = false
  }
}

const startGenerating = async () => {
  generating.value = true
  try {
    if (generatedScenes.value.length) {
      aiParsedData.value = {
        ...aiParsedData.value,
        scene_ai_workflow: aiParsedData.value.scene_ai_workflow || aiParsedData.value.ai_workflow || null,
      }
      if (sceneGenerationIsFallback(aiParsedData.value)) {
        showToast('本次为规则兜底场景，请人工复核场景与角色分配')
      }
      return
    }
    const caseInfo = {
      ...aiParsedData.value,
      case_name: form.title || aiParsedData.value.case_name,
      case_type: form.caseType || aiParsedData.value.case_type,
      case_background: aiParsedData.value.case_background,
    }
    const res: any = await request.post(
      '/cases/generate-scenes',
      { case_info: caseInfo, scene_generation_strategy: 'case_driven' },
      { timeout: 600000, _skipErrorToast: true } as any,
    )
    generatedScenes.value = normalizeGeneratedScenesFromPipeline(res.scenes || [], aiParsedData.value.persons || [])
    if (!generatedScenes.value.length) {
      showToast('场景生成未产生可发布场景，请返回检查案件内容后重试')
      throw new Error('empty-scenes')
    }
    aiParsedData.value = {
      ...aiParsedData.value,
      scene_generation_mode: res.scene_generation_mode || '',
      scene_generation_warning: res.scene_generation_warning || '',
      scene_blueprints: res.scene_blueprints || [],
      training_tasks: res.training_tasks || [],
      state_machine: res.state_machine || null,
      observable_scoring_rules: res.observable_scoring_rules || [],
      scene_ai_workflow: res.ai_workflow || null,
    }
    if (sceneGenerationIsFallback(res)) {
      showToast('本次为规则兜底场景，请人工复核场景与角色分配')
    }
  } catch {
    showToast('场景生成失败')
    throw new Error('generate-failed')
  } finally {
    generating.value = false
  }
}

const submitFinal = async () => {
  if (!validatePersonsBeforeSave(aiParsedData.value?.persons || [], aiParsedData.value)) return
  if (!generatedScenes.value.length) {
    showToast('请先生成至少一个训练场景')
    return
  }
  savingCreate.value = true
  try {
    const personsPayload = serializePersonsForSave(aiParsedData.value.persons || [])
    const createdCase: any = await saveWithCaseQualityGate((qualityAcknowledgements) => request.post('/cases/full-create', {
      case: {
        ...aiParsedData.value,
        persons: personsPayload,
        title: form.title || aiParsedData.value.case_name,
        case_type: form.caseType || aiParsedData.value.case_type,
        background: aiParsedData.value.case_background,
        original_content: importMode.value === 'plain_case'
          ? form.rawText
          : resolveOriginalContent(aiParsedData.value),
        source_mode: importMode.value,
        source_file_name: fileMeta.name || '',
        source_file_type: fileMeta.type || '',
        source_file_size: fileMeta.size || 0,
        extracted_text_preview: aiParsedData.value.extracted_text_preview || '',
      },
      scenes: generatedScenes.value,
      quality_acknowledgements: qualityAcknowledgements,
    }, { _skipErrorToast: true } as any))
    showToast({ type: 'success', message: '案件发布成功' })
    showAdd.value = false
    await refreshCasesPage()
    await handlePublishedCaseNextStep(createdCase)
  } catch {
    showToast('案件发布失败')
  } finally {
    savingCreate.value = false
  }
}

const handlePublishedCaseNextStep = async (createdCase: any) => {
  const caseId = Number(createdCase?.id)
  const firstSceneId = Number((createdCase?.scenes || [])[0]?.id)
  if (!caseId) return

  try {
    await showConfirmDialog({
      title: '案件发布成功',
      message: firstSceneId
        ? '是否立即进入学员端试训？取消则留在管理端继续检查案件配置。'
        : '该案件暂无可试训场景，是否打开案件详情继续配置？',
      confirmButtonText: firstSceneId ? '立即试训' : '打开详情',
      cancelButtonText: '继续编辑',
    })
    if (firstSceneId) {
      const session: any = await request.post(`/training/start/${firstSceneId}`, null, { _skipErrorToast: true } as any)
      if (session?.id) {
        router.push(`/student/training/${session.id}`)
        return
      }
      router.push('/student/hall')
      return
    }
  } catch {
    // 用户选择继续编辑，下面会打开案件详情。
  }

  const target = cases.value.find((item: any) => Number(item?.id) === caseId)
  if (target) {
    editCase(target)
  } else {
    router.replace(`/admin/cases?case_id=${caseId}`)
  }
}

const handleNext = async () => {
  if (currentStep.value === 0) {
    if (importMode.value === 'plain_case') {
      if (!form.title || !form.rawText.trim()) {
        showToast('请填写完整案件标题和原始文本')
        return
      }
      if (shouldWarnOnTitle(form.title)) {
        try {
          await showConfirmDialog({
            title: '标题提示',
            message: '当前案件标题看起来是纯数字或纯符号。系统允许继续保存，但建议确认这就是最终展示标题。',
          })
        } catch {
          return
        }
      }
    } else if (!uploadedFile.value) {
      showToast('请先上传笔录文件')
      return
    }

    currentStep.value = 1
    try {
      await startParsing()
    } catch {
      currentStep.value = 0
    }
    return
  }

  if (currentStep.value === 1) {
    if (!form.title) form.title = aiParsedData.value.case_name || ''
    if (!form.caseType) form.caseType = aiParsedData.value.case_type || ''
    currentStep.value = 2
    try {
      await startGenerating()
    } catch {
      currentStep.value = 1
    }
    return
  }

  await submitFinal()
}

const reparse = async () => {
  await startParsing()
}

const viewCaseDetail = (caseItem: any) => {
  previewCase.value = caseItem
  showPreview.value = true
}

const goEditCase = (caseItem: any) => {
  router.push(`/admin/cases/${caseItem.id}/edit`)
}

const editCase = (caseItem: any) => {
  selectedCase.value = caseItem
  editableCase.value = normalizeEditableCase(caseItem)
  resetReviewWorkspace()
  if (Array.isArray(editableCase.value?.persons)) {
    editableCase.value.persons.forEach((person: any) => {
      person._collapsed = true
    })
  }
  showDetail.value = true
  router.replace(`/admin/cases?case_id=${caseItem.id}`)
}

const closeDetail = () => {
  showDetail.value = false
  selectedCase.value = null
  editableCase.value = null
  resetReviewWorkspace()
  router.replace('/admin/cases')
}

const resetEditableCase = () => {
  if (!selectedCase.value) return
  editableCase.value = normalizeEditableCase(selectedCase.value)
}

const buildCaseInfoForCompletion = (caseItem: any) => {
  const structured = getStructuredData(caseItem)
  return {
    case_name: caseItem?.title || structured.case_name || '',
    case_type: caseItem?.case_type || structured.case_type || '',
    case_background: caseItem?.background || structured.case_background || '',
    fact_sheet: structured.fact_sheet || {},
    persons: serializePersonsForSave(caseItem?.persons || structured.persons || []),
    conflict_points: structured.conflict_points || [],
    key_facts: structured.key_facts || [],
    hidden_info: structured.hidden_info || [],
    evidence_points: structured.evidence_points || [],
    dispatch_brief_suggestion: structured.dispatch_brief_suggestion || '',
    first_impression_suggestion: structured.first_impression_suggestion || '',
    transcript_summary: structured.transcript_summary || '',
  }
}

const isBlankFormValue = (value: any) => {
  const text = String(value ?? '').trim()
  if (!text) return true
  return ['未明确', '未提取到案件背景', '待核实', '暂无', '解析失败'].includes(text)
}

const pickFilled = (current: any, incoming: any) => (isBlankFormValue(current) ? incoming : current)

const mergePersonEditors = (currentPersons: any[], incomingPersons: any[]) => {
  if (!incomingPersons?.length) return currentPersons
  const byName = new Map((currentPersons || []).map((person: any) => [String(person?.name || '').trim(), person]))
  incomingPersons.forEach((incoming: any) => {
    const name = String(incoming?.name || '').trim()
    if (!name) return
    const existing = byName.get(name)
    if (!existing) {
      byName.set(name, incoming)
      return
    }
    Object.keys(incoming).forEach((key) => {
      const nextValue = incoming[key]
      if (Array.isArray(nextValue)) {
        if (!Array.isArray(existing[key]) || !existing[key].length) existing[key] = nextValue
        return
      }
      if (isBlankFormValue(existing[key]) && !isBlankFormValue(nextValue)) {
        existing[key] = nextValue
      }
    })
  })
  return normalizePersonEditors(Array.from(byName.values()), { collapsed: true })
}

const applyCaseCompletionPayload = (target: any, payload: any, rawText: string) => {
  const parsed = payload?.case_info || {}
  const generatedScenes = Array.isArray(payload?.scenes) ? payload.scenes : []
  const sceneByName = Object.fromEntries(
    generatedScenes
      .map((scene: any) => [String(scene?.scene_name || '').trim(), scene])
      .filter(([name]: [string, any]) => name),
  )

  if (isBlankFormValue(target.title)) target.title = parsed.case_name || target.title
  target.background = pickFilled(target.background, parsed.case_background)
  target.ai_case_type_raw = parsed.ai_case_type_raw || target.ai_case_type_raw
  if (isBlankFormValue(target.case_type) && parsed.case_type) target.case_type = parsed.case_type
  target.case_type_group = getCaseTypeGroup(target.case_type)
  target.persons = mergePersonEditors(target.persons || [], parsed.persons || [])

  target.scenes = (target.scenes || []).map((scene: any, index: number) => {
    const aiScene = normalizeSceneScriptFields(sceneByName[String(scene?.name || '').trim()] || generatedScenes[index] || {})
    const nextRoleNames = resolveSceneRoleNames(aiScene, target.persons || [])
    const nextStages = Array.isArray(aiScene.stages) && aiScene.stages.length ? aiScene.stages : null
    return {
      ...scene,
      ...aiScene,
      description: pickFilled(scene.description, aiScene.scene_description || aiScene.plot_arc),
      dispatch_brief: pickFilled(scene.dispatch_brief, aiScene.dispatch_brief),
      first_impression: pickFilled(scene.first_impression, aiScene.first_impression),
      training_goal: pickFilled(scene.training_goal, aiScene.training_goal),
      expected_outcomes: Array.isArray(aiScene.expected_outcomes) && aiScene.expected_outcomes.length
        ? aiScene.expected_outcomes
        : (scene.expected_outcomes || []),
      plot_arc: pickFilled(scene.plot_arc, aiScene.plot_arc),
      role_training_functions: Array.isArray(aiScene.role_training_functions) && aiScene.role_training_functions.length
        ? aiScene.role_training_functions
        : (scene.role_training_functions || []),
      completion_criteria: Array.isArray(aiScene.completion_criteria) && aiScene.completion_criteria.length
        ? aiScene.completion_criteria
        : (scene.completion_criteria || []),
      failure_patterns: Array.isArray(aiScene.failure_patterns) && aiScene.failure_patterns.length
        ? aiScene.failure_patterns
        : (scene.failure_patterns || []),
      opening_config: scene.opening_config || aiScene.opening_config || null,
      difficulty: pickFilled(scene.difficulty, aiScene.difficulty),
      stagesModel: nextStages ? normalizeStageEditors(nextStages) : scene.stagesModel,
      stagesText: nextStages ? stringifyStages(nextStages) : scene.stagesText,
      roles: nextRoleNames.length ? nextRoleNames : scene.role_names || [],
      role_names: nextRoleNames.length ? nextRoleNames : scene.role_names || [],
      present_roles: nextRoleNames.length ? nextRoleNames : scene.role_names || [],
      primary_role_name:
        pickFilled(
          scene.primary_role_name,
          pickRecommendedPrimaryRoleName(target.persons || [], nextRoleNames) || nextRoleNames[0] || '',
        ) || scene.primary_role_name,
    }
  })

  const previousStructured = getStructuredData(target)
  const mergedFactSheet = { ...(previousStructured.fact_sheet || {}) }
  const incomingFactSheet = parsed.fact_sheet || {}
  Object.keys(incomingFactSheet).forEach((key) => {
    if (isBlankFormValue(mergedFactSheet[key]) && !isBlankFormValue(incomingFactSheet[key])) {
      mergedFactSheet[key] = incomingFactSheet[key]
    }
  })

  const mergeListField = (key: string) => {
    const current = Array.isArray(previousStructured[key]) ? previousStructured[key] : []
    const incoming = Array.isArray(parsed[key]) ? parsed[key] : []
    return current.length ? current : incoming
  }

  const structuredData = {
    ...previousStructured,
    ...parsed,
    fact_sheet: mergedFactSheet,
    conflict_points: mergeListField('conflict_points'),
    key_facts: mergeListField('key_facts'),
    hidden_info: mergeListField('hidden_info'),
    evidence_points: mergeListField('evidence_points'),
    inconsistencies: mergeListField('inconsistencies'),
    scene_generation_mode: payload.scene_generation_mode || previousStructured.scene_generation_mode || '',
    scene_generation_warning: payload.scene_generation_warning || previousStructured.scene_generation_warning || '',
    completion_engine: payload.completion_engine || '',
    completion_agent: payload.completion_agent || '',
    filled_field_paths: payload.filled_field_paths || [],
    field_evidence: payload.field_evidence || {},
    completion_warnings: payload.completion_warnings || [],
    case_name: target.title,
    case_type: target.case_type,
    case_background: target.background,
    persons: serializePersonsForSave(target.persons || []),
    schema_version: CASE_SCHEMA_VERSION,
    canonical_person_fields: PERSON_CANONICAL_FIELDS,
    canonical_alias_map: PERSON_ALIAS_TO_CANONICAL,
    rawText,
  }
  target.structured_data = JSON.stringify(structuredData, null, 2)
  target.parse_engine = parsed.parse_engine || ''
  target.parse_warnings = Array.isArray(parsed.parse_warnings) ? parsed.parse_warnings : []
  target.scene_generation_mode = payload.scene_generation_mode || ''
  target.scene_generation_warning = payload.scene_generation_warning || ''
}

const runAiSupplement = async () => {
  if (!editableCase.value) return
  const rawText = String(editableCase.value.original_content || '').trim()
  if (!rawText) {
    showToast('请先保留案件原始文本，再执行信息补全')
    return
  }

  supplementingAi.value = true
  try {
    const payload: any = await request.post(
      '/cases/ai-complete',
      {
        source_text: rawText,
        source_mode: 'plain_case',
        mode: 'fill_gaps',
        include_scenes: true,
        scene_generation_strategy: 'case_driven',
        target_groups: ['case_basic', 'fact_sheet', 'lists', 'persons', 'scenes'],
        case_info: buildCaseInfoForCompletion(editableCase.value),
      },
      { _skipErrorToast: true } as any,
    )
    applyCaseCompletionPayload(editableCase.value, payload, rawText)

    const hasWarnings = Array.isArray(payload?.completion_warnings) && payload.completion_warnings.length > 0
    const isFallback = String(payload?.completion_engine || '') !== 'deepseek-case-officer'
    showToast({
      type: !isFallback && !hasWarnings ? 'success' : 'fail',
      message: isFallback
        ? '已兜底补全，请人工复核后再保存'
        : hasWarnings
          ? 'AI 已补全空白项，部分字段原文无依据，请复核'
          : 'AI 已根据原文补全案件全部空白信息',
    })
  } catch {
    showToast('AI 补全失败')
  } finally {
    supplementingAi.value = false
  }
}

const rebuildingRoleMemories = ref(false)

const rebuildRoleMemoriesFromSource = async () => {
  if (!editableCase.value?.id) return
  if (!String(editableCase.value.original_content || '').trim()) {
    showToast('请先保留案件原始文本，再回填人物线')
    return
  }

  rebuildingRoleMemories.value = true
  try {
    const rebuilt: any = await request.post(
      `/cases/${editableCase.value.id}/rebuild-role-memories`,
      { replace_legacy_roles: true },
      { timeout: 600000, _skipErrorToast: true } as any,
    )
    selectedCase.value = rebuilt
    editableCase.value = normalizeEditableCase(rebuilt)
    showToast('已按原文回填人物线和角色记忆')
  } catch (error: any) {
    showToast(getApiErrorDetail(error, '人物线回填失败'))
  } finally {
    rebuildingRoleMemories.value = false
  }
}

const saveCaseDetail = async () => {
  if (!editableCase.value?.id) return
  if (!editableCase.value.title?.trim()) {
    showToast('案件标题不能为空')
    return
  }
  if (!validatePersonsBeforeSave(editableCase.value.persons || [])) return

  const scenesPayload = []
  for (const scene of editableCase.value.scenes || []) {
    ensureSceneAssessmentPointsModel(scene)
    let parsedStages = serializeStageEditors(scene.stagesModel || [])
    if (!parsedStages.length) {
      parsedStages = [
        {
          stage_name: '考察点',
          stage_goal: scene.training_goal || '完成当前场景警务处置目标',
          fact_ids: Array.isArray(scene.fact_ids) ? scene.fact_ids : [],
          recommended_prompts: [],
          assessment_points: serializeExpectedOutcomesForSave(scene.expectedOutcomesModel || []).map((content: string, index: number) => ({
        id: `eo_${index + 1}`,
        label: content.slice(0, 40),
        content,
        category: 'procedure',
        required: true,
        weight: 12,
        keywords: [],
        knowledge_refs: [],
      })),
          action_catalog: [],
          completion_rules: {
            min_user_turns: 3,
            required_point_ids: [],
            required_action_ids: [],
          },
          end_conditions: {
            must_complete_current_stage: true,
            required_point_ids: [],
            required_action_ids: [],
            closure_actions: [],
            closing_script: '',
          },
        },
      ]
    }
    scene.stagesText = JSON.stringify(parsedStages, null, 2)

    const sceneMeta = resolveSceneCompactMeta(scene)
    scenesPayload.push({
      id: scene.id,
      name: scene.name,
      description: scene.description,
      difficulty: scene.difficulty,
      dispatch_brief: scene.dispatch_brief,
      first_impression: scene.first_impression,
      training_goal: scene.training_goal || '',
      expected_outcomes: serializeExpectedOutcomesForSave(scene.expectedOutcomesModel || scene.expected_outcomes || []),
      plot_arc: scene.plot_arc || '',
      role_training_functions: Array.isArray(scene.role_training_functions) ? scene.role_training_functions : [],
      completion_criteria: Array.isArray(scene.completion_criteria) ? scene.completion_criteria : [],
      failure_patterns: Array.isArray(scene.failure_patterns) ? scene.failure_patterns : [],
      fact_ids: Array.isArray(scene.fact_ids) ? scene.fact_ids : [],
      opening_config: scene.opening_config || null,
      training_focus: sceneMeta.training_focus,
      behavior_mode: sceneMeta.behavior_mode,
      assessment_points: serializeExpectedOutcomesForSave(scene.expectedOutcomesModel || []).map((content: string, index: number) => ({
        id: `eo_${index + 1}`,
        label: content.slice(0, 40),
        content,
        category: 'procedure',
        required: true,
        weight: 12,
        keywords: [],
        knowledge_refs: [],
      })),
      stages: parsedStages,
      roles: Array.isArray(scene.role_names) ? scene.role_names : [],
      role_names: Array.isArray(scene.role_names) ? scene.role_names : [],
      present_roles: Array.isArray(scene.present_roles) && scene.present_roles.length
        ? scene.present_roles
        : (Array.isArray(scene.role_names) ? scene.role_names : []),
      primary_role_name: scene.primary_role_name || '',
    })
  }

  savingDetail.value = true
  try {
    const personsPayload = serializePersonsForSave(editableCase.value.persons || [])
    const structuredData = {
      ...getStructuredData(editableCase.value),
      case_name: editableCase.value.title,
      case_type: editableCase.value.case_type,
      case_background: editableCase.value.background,
      persons: personsPayload,
      schema_version: CASE_SCHEMA_VERSION,
      canonical_person_fields: PERSON_CANONICAL_FIELDS,
      canonical_alias_map: PERSON_ALIAS_TO_CANONICAL,
      rawText: editableCase.value.original_content,
      scene_scripts: scenesPayload.map((scene: any) => ({
        scene_name: scene.name,
        scene_ref: scene.id ? `db:${scene.id}` : undefined,
        dispatch_brief: scene.dispatch_brief || '',
        first_impression: scene.first_impression || '',
        training_goal: scene.training_goal || '',
        expected_outcomes: scene.expected_outcomes || [],
        plot_arc: scene.plot_arc || '',
        stages: scene.stages || [],
        role_training_functions: scene.role_training_functions || [],
        completion_criteria: scene.completion_criteria || [],
        failure_patterns: scene.failure_patterns || [],
        opening_lines: scene.opening_lines || [],
        fact_ids: scene.fact_ids || [],
        roles: scene.role_names || [],
        role_names: scene.role_names || [],
        primary_role_name: scene.primary_role_name || '',
      })),
    }

    const res: any = await saveWithCaseQualityGate((qualityAcknowledgements) => request.put(`/cases/${editableCase.value.id}`, {
      case: {
        title: editableCase.value.title,
        case_type: editableCase.value.case_type,
        background: editableCase.value.background,
        original_content: editableCase.value.original_content,
        structured_data: structuredData,
      },
      scenes: scenesPayload,
      quality_acknowledgements: qualityAcknowledgements,
    }, { _skipErrorToast: true } as any))

    showToast({ type: 'success', message: '案件已更新' })
    selectedCase.value = res
    editableCase.value = normalizeEditableCase(res)
    await refreshCasesPage()
  } catch {
    showToast('保存失败')
  } finally {
    savingDetail.value = false
  }
}

const deleteCase = (caseItem: any) => {
  showConfirmDialog({
    title: '确认删除',
    message: `确定要删除《${caseItem.title}》吗？此操作不可撤销。`,
  }).then(async () => {
    try {
      await request.delete(`/cases/${caseItem.id}`, { _skipErrorToast: true } as any)
      showToast({ type: 'success', message: '案件已删除' })
      if (selectedCase.value?.id === caseItem.id) closeDetail()
      await refreshCasesPage()
    } catch {
      showToast('删除失败')
    }
  }).catch(() => {})
}

const getTagType = (type: string) => {
  if (['邻里纠纷', '家庭纠纷', '情感纠纷', '劳资纠纷', '消费纠纷'].includes(type)) return 'success'
  if (['打架斗殴', '寻衅滋事', '故意伤害', '故意杀人'].includes(type)) return 'danger'
  if (['盗窃', '诈骗', '电信网络诈骗', '入室盗窃', '抢劫'].includes(type)) return 'warning'
  return 'primary'
}

const loadingCase = ref(false)
const loadError = ref('')

const loadCaseForEdit = async () => {
  const id = route.params.id
  if (!id) { loadError.value = '缺少案件 ID'; return }
  loadingCase.value = true
  loadError.value = ''
  try {
    const res: any = await request.get(`/cases/${id}`)
    if (!res) { loadError.value = '案件不存在'; return }
    selectedCase.value = res
    editableCase.value = normalizeEditableCase(res)
    resetReviewWorkspace()
    if (Array.isArray(editableCase.value?.persons)) {
      editableCase.value.persons.forEach((p: any) => { p._collapsed = true })
    }
  } catch {
    loadError.value = '案件加载失败，请重试'
    showToast('加载失败')
  } finally {
    loadingCase.value = false
  }
}

const goBack = () => router.push('/admin/cases')

// Override saveCaseDetail to redirect after save
const _saveCaseDetailAndBack = async () => {
  await saveCaseDetail()
  // if save succeeded, editableCase still valid but navigate back
}

onMounted(async () => {
  await loadCaseForEdit()
  if (localStorage.getItem('case_pipeline_job_id')) {
    currentStep.value = 1
    showAdd.value = true
    parsing.value = true
    try {
      const resumed = await resumeCasePipeline()
      if (resumed?.status === 'completed') {
        const res: any = applyPipelineJobResult(resumed.result || {})
        if (!form.title) form.title = res.case_name || ''
        if (!form.caseType) form.caseType = res.case_type || ''
        form.caseTypeGroup = getCaseTypeGroup(form.caseType)
        showToast({ type: 'success', message: '案件整理任务已恢复完成' })
      }
    } catch (error: any) {
      showToast(getApiErrorDetail(error, '案件整理任务恢复失败'))
    } finally {
      parsing.value = false
    }
  }
})

// ── 案件预览弹窗辅助 ────────────────────────────────────────────────
const previewStructuredData = computed(() => {
  if (!previewCase.value?.structured_data) return {}
  try {
    return typeof previewCase.value.structured_data === 'string'
      ? JSON.parse(previewCase.value.structured_data)
      : previewCase.value.structured_data
  } catch { return {} }
})

const previewPersons = computed(() => {
  const p = previewStructuredData.value?.persons
  return Array.isArray(p) ? p : []
})

const previewFormatDate = (dt: string | null | undefined) => {
  if (!dt) return '—'
  try { return new Date(dt).toLocaleDateString('zh-CN') } catch { return String(dt) }
}

</script>

<template>
  <div class="ce-page">
    <div class="ce-topbar">
      <button class="ce-back-btn" @click="goBack"><van-icon name="arrow-left" /><span>返回列表</span></button>
      <div class="ce-topbar__center"><span class="ce-topbar__title">{{ editableCase?.title || '案件编辑' }}</span></div>
      <div class="ce-topbar__actions">
        <van-button plain size="small" :disabled="!editableCase || loadingCase" @click="resetEditableCase">重置修改</van-button>
        <van-button plain size="small" :loading="rebuildingRoleMemories" :disabled="!editableCase || loadingCase" @click="rebuildRoleMemoriesFromSource">回填人物线</van-button>
        <van-button type="primary" size="small" class="!bg-[#1D3557] !border-none" :loading="savingDetail" :disabled="!editableCase || loadingCase" @click="saveCaseDetail">保存修改</van-button>
      </div>
    </div>
    <div v-if="loadingCase" class="ce-loading"><van-loading color="#1D3557" vertical>加载案件中...</van-loading></div>
    <div v-else-if="loadError" class="ce-error"><p>{{ loadError }}</p><van-button plain @click="goBack">返回列表</van-button></div>
    <div v-else-if="editableCase" class="ce-content">
      <nav class="review-module-nav" aria-label="审核模块">
            <button
              v-for="module in reviewModules"
              :key="module.id"
              type="button"
              class="review-module-nav__item"
              :class="{ 'is-active': activeReviewModule === module.id }"
              @click="setReviewModule(module.id)"
            >
              <span class="review-module-nav__step">{{ module.step }}</span>
              <span class="review-module-nav__label">{{ module.label }}</span>
            </button>
          </nav>

          <section v-show="activeReviewModule === 'basic'" class="wp">
            <div class="wp__header">
              <div class="wp__header-left">
                <span class="wp__step">01</span>
                <div>
                  <div class="wp__title">案件标题、分类与背景</div>
                  <div class="wp__sub">审核并调整案件基本信息</div>
                </div>
              </div>
            </div>
            <div class="wp__body">
              <div v-if="showTypeNormalizationHint(editableCase)" class="wp-alert wp-alert--blue">
                AI 原始识别为「{{ editableCase.ai_case_type_raw || '未识别' }}」，当前标准化类型为「{{ editableCase.case_type || '其他' }}」。
              </div>
              <div v-if="parseWarnings(editableCase).length || sceneGenerationWarning(editableCase)" class="wp-alert wp-alert--amber">
                <div class="wp-alert__title">AI 解析复核提醒</div>
                <div class="wp-alert__row">解析来源：{{ parseEngineLabel(editableCase) }}</div>
                <div v-for="warning in parseWarnings(editableCase)" :key="warning" class="wp-alert__row">{{ warning }}</div>
                <div v-if="sceneGenerationWarning(editableCase)" class="wp-alert__row">{{ sceneGenerationWarning(editableCase) }}</div>
              </div>
              <div class="wp-card">
                <div class="wp-card__header">
                  <span class="wp-card__title">案件信息</span>
                  <van-tag type="primary" round class="!text-[11px]">{{ editableCase.case_type || '未分类' }}</van-tag>
                </div>
                <div class="wp-card__body">
                  <div class="wp-grid wp-grid--3">
                    <div class="wp-field">
                      <label class="wp-label">案件标题 <span class="wp-required">*</span></label>
                      <input v-model="editableCase.title" type="text" class="wp-input" />
                    </div>
                    <div class="wp-field">
                      <label class="wp-label">案件大类</label>
                      <select v-model="editableCase.case_type_group" class="wp-input">
                        <option value="">请选择案件大类</option>
                        <option v-for="group in caseTypeGroups" :key="group.label" :value="group.label">{{ group.label }}</option>
                      </select>
                    </div>
                    <div class="wp-field">
                      <label class="wp-label">案件类型</label>
                      <select v-model="editableCase.case_type" class="wp-input">
                        <option value="">请选择案件类型</option>
                        <option v-for="type in getTypesByGroup(editableCase.case_type_group)" :key="type" :value="type">{{ type }}</option>
                      </select>
                    </div>
                  </div>
                  <div class="wp-field wp-mt">
                    <label class="wp-label">案件背景</label>
                    <textarea v-model="editableCase.background" rows="3" class="wp-textarea"></textarea>
                  </div>
                </div>
              </div>
              <CaseFactLedger :case-data="editableCase" />
              <div class="wp-card">
                <div class="wp-card__header">
                  <span class="wp-card__title">案件原始文本</span>
                  <span class="wp-card__meta">{{ String(editableCase.original_content || '').trim() ? `${String(editableCase.original_content || '').trim().length} 字` : '暂无内容' }}</span>
                  <van-button size="mini" plain type="primary" @click="showOriginalExpanded = !showOriginalExpanded">
                    {{ showOriginalExpanded ? '收起' : '展开全文' }}
                  </van-button>
                </div>
                <div class="wp-card__body">
                  <p v-if="!showOriginalExpanded" class="wp-hint">原文已保留；需要校对或补全失败时再展开全文。</p>
                  <textarea v-else v-model="editableCase.original_content" rows="10" class="wp-textarea wp-textarea--mono" placeholder="导入文件提取出的案件原文会保留在这里，支持继续人工整理。"></textarea>
                </div>
              </div>
            </div>
          </section>
            <section v-show="activeReviewModule === 'roles'" class="wp">
            <div class="wp__header">
              <div class="wp__header-left">
                <span class="wp__step">02</span>
                <div>
                  <div class="wp__title">角色信息审核与调整</div>
                  <div class="wp__sub">逐一复核角色设定与行为动机</div>
                </div>
              </div>
              <span class="wp__badge">人工复核</span>
            </div>
            <div class="wp__body">

              <!-- 角色审核工作台：左侧列表 + 右侧工作区 -->
              <div class="role-audit-workspace">

                <!-- 左侧角色列表 -->
                <aside class="role-audit-sidebar">
                  <div class="role-audit-sidebar__header">
                    <span class="role-audit-sidebar__title">角色列表</span>
                    <span class="role-audit-sidebar__count">{{ (editableCase.persons || []).length }} 个角色</span>
                  </div>

                  <div class="role-audit-sidebar__list">
                    <button
                      v-for="(person, index) in editableCase.persons || []"
                      :key="person._editor_id || `sidebar-role-${index}`"
                      type="button"
                      class="role-sidebar-item"
                      :class="{ 'is-active': activePersonEditorId === (person._editor_id || index) }"
                      @click="selectPersonForAudit(person)"
                    >
                      <div class="role-sidebar-item__avatar">{{ String(person.name || '?').charAt(0) }}</div>
                      <div class="role-sidebar-item__info">
                        <div class="role-sidebar-item__name">{{ person.name || '未命名角色' }}</div>
                        <div class="role-sidebar-item__meta">
                          <span>{{ person.role_type || person.role || '相关人员' }}</span>
                          <span v-if="person.role && person.role !== person.role_type" class="role-sidebar-item__sub">{{ person.role }}</span>
                        </div>
                      </div>
                      <div class="role-sidebar-item__status">
                        <span
                          class="role-review-badge"
                          :class="getReviewStatusClass(person._review_status)"
                        >{{ getReviewStatusLabel(person._review_status) }}</span>
                      </div>
                    </button>
                  </div>

                  <div class="role-audit-sidebar__footer">
                    <button type="button" class="role-sidebar-add-btn" @click="addEditablePersonAndSelect">
                      <span>＋ 新增角色</span>
                    </button>
                  </div>

                  <!-- 审核说明 -->
                  <div class="role-audit-sidebar__note">
                    <div class="role-audit-sidebar__note-title">审核说明</div>
                    <p class="role-audit-sidebar__note-text">请逐一审核并调整案件中的角色信息，确保角色定位准确、行为动机设置符合训练目标。</p>
                  </div>
                </aside>

                <!-- 右侧工作区 -->
                <main class="role-audit-main">
                  <!-- 未选中任何角色时的空状态 -->
                  <div v-if="!activeEditablePerson" class="role-audit-main__empty">
                    <div class="role-audit-main__empty-icon">👤</div>
                    <div class="role-audit-main__empty-title">
                      {{ (editableCase.persons || []).length ? '点击左侧角色开始审核' : '当前案件还没有角色模板' }}
                    </div>
                    <div class="role-audit-main__empty-desc">
                      {{ (editableCase.persons || []).length ? '从左侧角色列表中选择一个角色，在此处查看和编辑角色详情。' : '可以点击左侧「新增角色」手动创建角色，再继续做场景分配和最终审核。' }}
                    </div>
                  </div>

                  <!-- 选中角色后的工作台 -->
                  <template v-else>
                    <!-- 角色详情头部 -->
                    <div class="role-audit-header">
                      <div class="role-audit-header__avatar">{{ String(activeEditablePerson.name || '?').charAt(0) }}</div>
                      <div class="role-audit-header__info">
                        <div class="role-audit-header__name-row">
                          <span class="role-audit-header__name">{{ activeEditablePerson.name || '未命名角色' }}</span>
                          <van-tag plain type="primary" class="ml-2">{{ activeEditablePerson.role_type || activeEditablePerson.role || '相关人员' }}</van-tag>
                          <van-tag v-if="activeEditablePerson.role && activeEditablePerson.role !== activeEditablePerson.role_type" plain>{{ activeEditablePerson.role }}</van-tag>
                        </div>
                        <div class="role-audit-header__meta-row">
                          <span>角色 ID：R{{ String(activePersonEditorId).padStart(3, '0') }}</span>
                          <span class="role-audit-header__sep">·</span>
                          <span>创建时间：{{ editableCase.created_at ? formatDateTime(editableCase.created_at) : '暂无' }}</span>
                          <span class="role-audit-header__sep">·</span>
                          <span>人物线：{{ Array.isArray(activeEditablePerson.role_memories) ? activeEditablePerson.role_memories.length : 0 }} 条</span>
                        </div>
                      </div>
                      <div class="role-audit-header__actions">
                        <div class="flex items-center gap-2">
                          <!-- 审核状态切换 -->
                          <select
                            class="role-review-status-select"
                            :value="activeEditablePerson._review_status || 'pending'"
                            @change="setPersonReviewStatus(activeEditablePerson, ($event.target as HTMLSelectElement).value)"
                          >
                            <option value="pending">待审核</option>
                            <option value="needs_update">待补充</option>
                            <option value="approved">通过</option>
                          </select>
                          <span
                            class="role-review-badge role-review-badge--lg"
                            :class="getReviewStatusClass(activeEditablePerson._review_status)"
                          >{{ getReviewStatusLabel(activeEditablePerson._review_status) }}</span>
                        </div>
                        <van-button size="small" type="danger" plain @click="removeEditablePersonById(activePersonEditorId)">删除角色</van-button>
                      </div>
                    </div>

                    <!-- 子标签页 -->
                    <div class="role-audit-tabs">
                      <button
                        v-for="tab in roleAuditTabs"
                        :key="tab.id"
                        type="button"
                        class="role-audit-tab"
                        :class="{ 'is-active': activeRoleAuditTab === tab.id }"
                        @click="activeRoleAuditTab = tab.id"
                      >{{ tab.label }}</button>
                    </div>

                    <!-- 标签页内容容器（固定高度 + 内部各 tab 绝对定位独立滚动） -->
                    <div class="role-audit-tab-content">
                      <!-- 基础信息 tab -->
                      <div v-show="activeRoleAuditTab === 'basic'" class="role-audit-tab-body">
                        <!-- 人物身份独立行（在案称谓，不同于 role_type） -->
                        <div class="rcf-identity-row">
                          <label class="rcf-identity-label">人物身份（在本案中的称谓）</label>
                          <input v-model="activeEditablePerson.role" type="text" class="rcf-identity-input" placeholder="如报警人、家属、同事" />
                        </div>
                        <RoleCompactForm
                          :model-value="activeEditablePerson"
                          :scene-behavior-mode="resolvePersonSceneBehaviorMode(activeEditablePerson, editableCase)"
                          @update:model-value="(next) => applyPersonCompactUpdate(editableCase, activeEditablePerson, next)"
                        />
                      </div>

                      <!-- AI 审核建议 tab -->
                      <div v-show="activeRoleAuditTab === 'ai_review'" class="role-audit-tab-body">
                        <div class="role-ai-review-card">
                          <div class="role-ai-review-card__header">
                            <span class="role-ai-review-card__badge">AI</span>
                            <span class="role-ai-review-card__title">AI 审核建议</span>
                            <van-button size="small" plain class="ml-auto" @click="runPersonAiReview(activeEditablePerson)">重新分析</van-button>
                          </div>
                          <div v-if="activeEditablePerson._ai_review_loading" class="role-ai-review-card__loading">
                            <van-loading size="18px">正在分析中...</van-loading>
                          </div>
                          <div v-else-if="activeEditablePerson._ai_review_text" class="role-ai-review-card__body">
                            {{ activeEditablePerson._ai_review_text }}
                          </div>
                          <div v-else class="role-ai-review-card__empty">
                            当前角色画像{{ getPersonCompletenessHint(activeEditablePerson) }}，建议先补充基础信息后再运行 AI 分析。
                          </div>
                        </div>
                      </div>

                      <!-- 审核记录 tab -->
                      <div v-show="activeRoleAuditTab === 'audit_log'" class="role-audit-tab-body">
                        <div class="role-audit-log">
                          <div class="role-audit-log__header">
                            <span>审核记录</span>
                          </div>
                          <div v-if="!(activeEditablePerson._audit_logs || []).length" class="role-audit-log__empty">
                            暂无审核记录，保存后系统会自动记录状态变更。
                          </div>
                          <table v-else class="role-audit-log__table">
                            <thead>
                              <tr>
                                <th>状态</th>
                                <th>审核人</th>
                                <th>时间</th>
                                <th>说明</th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr v-for="(log, li) in activeEditablePerson._audit_logs" :key="li">
                                <td>
                                  <span class="role-review-badge" :class="getReviewStatusClass(log.status)">
                                    {{ getReviewStatusLabel(log.status) }}
                                  </span>
                                </td>
                                <td>{{ log.reviewer || '系统' }}</td>
                                <td>{{ log.time || '' }}</td>
                                <td>{{ log.note || '' }}</td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                  </template>
                </main>

              </div>

            </div>
            </section>

          <section v-show="activeReviewModule === 'scenes'" class="wp">
            <div class="wp__header">
              <div class="wp__header-left">
                <span class="wp__step">03</span>
                <div>
                  <div class="wp__title">训练场景与流程配置</div>
                  <div class="wp__sub">配置场景角色、文案与考察流程</div>
                </div>
              </div>
              <span class="wp__badge wp__badge--count">{{ (editableCase.scenes || []).length }} 个场景</span>
            </div>
            <div class="wp__body">
            <section class="scene-studio">
            <div v-if="!(editableCase.scenes || []).length" class="scene-studio__empty py-8 text-center text-sm text-slate-500">暂无场景</div>
            <div v-else class="scene-studio__layout">
              <aside class="wp__nav">
                <button
                  v-for="(scene, idx) in editableCase.scenes || []"
                  :key="'nav-' + scene.id"
                  type="button"
                  class="wp__nav-item"
                  :class="{ 'is-active': activeSceneIndex === idx }"
                  @click="setActiveSceneIndex(Number(idx))"
                >
                  <span class="wp__nav-index">场景 {{ Number(idx) + 1 }}</span>
                  <span class="wp__nav-name">{{ scene.name || '未命名' }}</span>
                  <span v-if="(scene.assessmentPointsModel || []).length" class="wp__nav-meta">
                    {{ (scene.expectedOutcomesModel || scene.expected_outcomes || []).length }} 考察点
                  </span>
                </button>
              </aside>
              <div class="scene-studio__main">
                <div class="wp__tabs">
                  <button
                    v-for="tab in sceneEditTabs"
                    :key="tab.id"
                    type="button"
                    class="wp__tab"
                    :class="{ 'is-active': activeSceneTab === tab.id }"
                    @click="onSceneTabClick(tab.id)"
                  >{{ tab.label }}</button>
                </div>
            <div
              v-for="(scene, idx) in editableCase.scenes || []"
              v-show="activeSceneIndex === idx"
              :key="scene.id"
              class="scene-editor-card scene-editor-card--studio"
            >
              <div v-show="activeSceneTab === 'overview'" class="scene-editor-card__panel scene-editor-card__panel--summary">
                <div class="scene-editor-card__section-head">
                  <div>
                    <div class="scene-editor-card__section-title">场景名称、难度与描述</div>
                  </div>
                </div>
                <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div>
                    <label class="form-label">场景名称</label>
                    <input
                      v-model="scene.name"
                      type="text"
                      class="form-input"
                      :placeholder="SCENE_NAME_PLACEHOLDERS[Number(idx)] || '须含：接警 / 现场 / 询问 关键词'"
                    />
                    <p class="mt-1 text-xs text-slate-400">
                      类型：{{ sceneBucketLabel(scene.name, Number(idx), (editableCase.scenes || []).length) }} · 剧本驱动考察点
                    </p>
                  </div>
                  <div>
                    <label class="form-label">难度</label>
                    <select v-model="scene.difficulty" class="form-input">
                      <option value="简单">简单</option>
                      <option value="中等">中等</option>
                      <option value="困难">困难</option>
                    </select>
                  </div>
                </div>
                <div class="mt-4">
                  <label class="form-label">场景描述</label>
                  <textarea v-model="scene.description" rows="2" class="form-textarea"></textarea>
                </div>
                <SceneTrainingContract :scene="scene" :case-data="editableCase" />
              </div>

              <div v-show="activeSceneTab === 'roles_copy'" v-if="editableCase.persons?.length" class="scene-editor-card__panel scene-editor-card__panel--roles">
                <div class="scene-editor-card__section-head">
                  <div>
                    <div class="scene-editor-card__section-title">参与角色与主对话人</div>
                  </div>
                </div>
                <div class="mt-3 flex flex-wrap gap-2">
                  <button
                    v-for="person in editableCase.persons"
                    :key="`${scene.id}-${person.name}`"
                    type="button"
                    class="rounded-full border px-3 py-1.5 text-xs font-bold transition-colors"
                    :class="scene.role_names?.includes(person.name) ? 'border-[#1D3557] bg-[#1D3557] text-white' : 'border-slate-200 bg-white text-slate-600'"
                    @click="toggleSceneRole(scene, person.name)"
                  >
                    {{ person.name }}
                  </button>
                </div>
                <div class="mt-4">
                  <label class="form-label form-label--muted">主对话人</label>
                  <select v-model="scene.primary_role_name" class="form-input">
                    <option value="">请选择主对话人</option>
                    <option v-for="roleName in scene.role_names || []" :key="roleName" :value="roleName">{{ roleName }}</option>
                  </select>
                </div>
                <div v-if="getSceneRoleRecommendation(editableCase, scene)" class="mt-3 rounded-xl border border-sky-200 bg-sky-50 px-3 py-3 text-xs text-sky-700">
                  <div class="font-bold">推荐主对话人：{{ getSceneRoleRecommendation(editableCase, scene)?.name }}</div>
                  <div class="mt-1">{{ getSceneRoleRecommendation(editableCase, scene)?.reason }}</div>
                </div>
                <div v-if="getSceneUnsuitableRoleHints(editableCase, scene).length" class="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-3 text-xs text-amber-700">
                  <div class="font-bold">不优先建议</div>
                  <div v-for="hint in getSceneUnsuitableRoleHints(editableCase, scene)" :key="hint" class="mt-1">{{ hint }}</div>
                </div>
                <div v-if="scene.primary_role_name" class="mt-3 rounded-xl bg-slate-50 px-3 py-3 text-xs text-slate-500">
                  {{ getScenePrimaryRoleSummary(editableCase, scene) }}
                </div>
              </div>

              <div v-show="activeSceneTab === 'flow'" class="space-y-4">
                <div class="scene-editor-card__panel scene-editor-card__panel--copy">
                  <div class="scene-editor-card__section-head">
                    <div></div>
                  </div>
                  <div class="mt-3 grid grid-cols-1 gap-4">
                    <div>
                      <label class="form-label">接警简报</label>
                      <textarea v-model="scene.dispatch_brief" rows="3" class="form-textarea"></textarea>
                    </div>
                    <div>
                      <label class="form-label">现场第一印象</label>
                      <textarea v-model="scene.first_impression" rows="3" class="form-textarea"></textarea>
                    </div>
                  </div>
                </div>
                <SceneOpeningConfigForm
                  v-model="scene.opening_config"
                  :roles="editableCase.persons || []"
                />

                <div class="scene-flow-panel">
                  <div class="scene-flow-panel__toolbar">
                    <span class="scene-flow-panel__badge scene-flow-panel__badge--bucket">
                      本场景考察点 · 已配置 {{ expectedOutcomeCountLabel(scene) }}
                    </span>
                    <div class="scene-flow-panel__actions">
                      <van-button
                        type="primary"
                        size="small"
                        class="!bg-[#1D3557] !border-none"
                        :loading="isSceneAssessmentLoading(scene)"
                        @click="generateAssessmentPointsForScene(scene, Number(idx))"
                      >
                        {{ (scene.expectedOutcomesModel || []).length >= MAX_ASSESSMENT_POINTS_PER_SCENE ? 'AI 刷新考察点' : ((scene.expectedOutcomesModel || []).length ? 'AI 追加考察点' : 'AI 生成考察点') }}
                      </van-button>
                      <van-button plain size="small" @click="addAssessmentPointToScene(scene)">补一条</van-button>
                    </div>
                  </div>

                  <p class="mt-2 text-xs text-slate-500">考察点以剧本为唯一数据源（1-6 条）。未满可追加，已满仅刷新替换；粘贴/上传/分派入口已下线。</p>
                  <p v-if="scene._assessmentMessage" class="mt-2 text-xs text-emerald-700">{{ scene._assessmentMessage }}</p>

                  <div v-if="!(scene.expectedOutcomesModel || []).length" class="scene-flow-panel__empty">
                    暂无考察点。请使用「AI 生成考察点」或手动新增（每场景最多 {{ MAX_ASSESSMENT_POINTS_PER_SCENE }} 条）。新整理案件由剧本自动带入。
                  </div>

                  <div
                    v-for="(point, pointIndex) in scene.expectedOutcomesModel || []"
                    :key="`${scene.id}-eo-${point._editor_id || pointIndex}`"
                    class="scene-flow-stage"
                  >
                    <div class="scene-flow-stage__head">
                      <span class="scene-flow-stage__index">考察点 {{ Number(pointIndex) + 1 }}</span>
                      <van-button plain size="mini" class="!text-rose-600" @click="removeAssessmentPointFromScene(scene, Number(pointIndex))">删除</van-button>
                    </div>
                    <div class="scene-flow-stage__core">
                      <label class="form-label form-label--muted">考察点</label>
                      <textarea
                        v-model="point.content"
                        rows="2"
                        class="form-textarea"
                        placeholder="如：能够安全控制现场，避免冲突升级"
                      ></textarea>
                    </div>
                  </div>
                </div>
              </div>

            </div>
              </div>
            </div>
            </section>
          </div>
          </section>
    </div>
</div>
  <van-popup
    v-model:show="showLargeTextEditor"
    position="center"
    round
    teleport="body"
    class="large-text-editor-popup"
  >
    <div class="large-text-editor">
      <div class="large-text-editor__head">
        <div>
          <div class="large-text-editor__eyebrow">{{ largeTextEditor?.fieldLabel || '长文本编辑' }}</div>
          <h3>{{ largeTextEditor?.title || '放大编辑' }}</h3>
        </div>
        <van-button plain size="small" icon="cross" @click="showLargeTextEditor = false">关闭</van-button>
      </div>
      <textarea
        v-model="largeTextEditorValue"
        class="large-text-editor__textarea"
        :placeholder="largeTextEditor?.placeholder"
      ></textarea>
    </div>
  </van-popup>
</template>

<style scoped>

/* ── CaseEdit 页面布局 ──────────────────────────────── */
.ce-page {
  height: 100vh;
  overflow: hidden;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
}
.ce-topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 24px;
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #f1f5f9;
  z-index: 20;
  flex-shrink: 0;
}
.ce-back-btn {
  display: flex; align-items: center; gap: 5px; padding: 6px 10px;
  border-radius: 8px; border: none; background: transparent;
  color: #64748b; font-size: 13px; font-weight: 600; cursor: pointer;
  transition: all 0.14s; white-space: nowrap;
}
.ce-back-btn:hover { background: #f1f5f9; color: #1e293b; }
.ce-topbar__center { flex: 1; text-align: center; }
.ce-topbar__title { font-size: 15px; font-weight: 700; color: #0f172a; }
.ce-topbar__actions { display: flex; align-items: center; gap: 8px; }
.ce-loading, .ce-error {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 16px; padding: 80px 20px; color: #94a3b8; font-size: 14px;
}
/* 主内容区：固定高度，不滚动 */
.ce-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 16px 20px 0;
  min-height: 0;
}
/* 导航条固定 */
.ce-content .review-module-nav {
  flex-shrink: 0;
  margin-bottom: 12px;
}
/* 三个 wp section 各自铺满剩余高度并内部滚动 */
.ce-content .wp {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.ce-content .wp__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 14px;
}
/* 角色审核工作台高度适应剩余空间 */
.ce-content .role-audit-workspace {
  height: 100%;
  max-height: none;
}

.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.case-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--police-border);
  border-radius: var(--police-radius-lg);
  background: #fff;
  box-shadow: var(--police-shadow-sm);
}

.admin-list-header,
.admin-list-panel,
.admin-filter-panel {
  border: 1px solid var(--police-border);
  border-radius: var(--police-radius-lg);
  background: #fff;
}

.admin-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
}

.admin-list-header h1 {
  margin: 0;
  color: var(--police-text-primary);
  font-size: 22px;
  font-weight: 800;
}

.admin-list-header p {
  margin: 4px 0 0;
  color: var(--police-text-muted);
  font-size: 13px;
}

.admin-list-panel,
.admin-filter-panel {
  padding: 16px 20px;
}

.admin-list-section-title {
  margin: 0;
  color: var(--police-text-primary);
  font-size: 16px;
  font-weight: 700;
}

.admin-stat-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.admin-stat-card {
  border: 1px solid var(--police-border-light);
  border-radius: var(--police-radius);
  background: #f8fafc;
  padding: 16px 18px;
}

.admin-filter-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.admin-filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.admin-filter-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--police-text-secondary);
  font-size: 13px;
}

.admin-filter-item select {
  min-width: 112px;
  height: 34px;
  border: 1px solid var(--police-border);
  border-radius: var(--police-radius);
  background: #fff;
  padding: 0 10px;
  color: var(--police-text-primary);
}

.admin-search-box {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: min(340px, 100%);
  height: 34px;
  border: 1px solid var(--police-border);
  border-radius: var(--police-radius);
  background: #fff;
  padding: 0 12px;
  color: var(--police-text-muted);
}

.admin-search-box input {
  min-width: 0;
  flex: 1;
  border: none;
  background: transparent;
  color: var(--police-text-primary);
  font-size: 13px;
  outline: none;
}

.admin-filter-summary {
  color: var(--police-text-muted);
  font-size: 13px;
}

.case-table {
  width: 100%;
  min-width: 960px;
  table-layout: fixed;
  border-collapse: collapse;
}

.case-table th {
  background: #f8fafc;
  border-bottom: 1px solid var(--police-border);
  padding: 12px 14px;
  text-align: left;
  font-size: 13px;
  font-weight: 700;
  color: var(--police-text-secondary);
  white-space: nowrap;
}

.case-table td {
  border-bottom: 1px solid var(--police-border-light);
  height: 92px;
  padding: 12px 14px;
  vertical-align: middle;
  font-size: 13px;
  color: var(--police-text-primary);
  overflow: hidden;
}

.case-table tr:last-child td {
  border-bottom: none;
}

.case-table tbody tr {
  cursor: pointer;
  transition: background 0.12s;
}

.case-table tbody tr:hover td {
  background: #f8fafc;
}

.case-action-cell {
  padding-left: 10px;
  padding-right: 10px;
}

.case-action-group {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 124px;
  min-width: 124px;
  margin: 0 auto;
}

.case-action-button {
  width: 56px;
  height: 36px;
  padding: 0;
  border-radius: 6px;
}

.case-action-button--primary {
  background: #1d3557;
  border-color: #1d3557;
}

.case-title-cell {
  width: 25%;
}

.case-row-title {
  display: -webkit-box;
  height: 44px;
  overflow: hidden;
  font-weight: 700;
  line-height: 1.55;
  color: #1e293b;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.case-row-id {
  margin-top: 4px;
  font-size: 11px;
  color: var(--police-text-muted);
}

.case-summary-cell {
  color: #475569;
}

.case-summary-text {
  display: -webkit-box;
  height: 42px;
  overflow: hidden;
  line-height: 1.62;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.case-metric-cell {
  font-size: 16px;
  font-weight: 800;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.case-type-cell,
.case-status-cell {
  text-align: center;
}

.case-type-tag {
  max-width: 92px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.case-issue {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 46px;
  height: 26px;
  border-radius: 20px;
  background: #fff7ed;
  color: #c2410c;
  padding: 0 9px;
  font-size: 12px;
  font-weight: 700;
}

.case-ok {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 46px;
  height: 26px;
  color: var(--police-success);
  font-size: 12px;
  font-weight: 700;
}

.stat-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-weight: 900;
  color: #94a3b8;
}

.stat-value {
  margin-top: 10px;
  font-size: 28px;
  line-height: 1;
  font-weight: 900;
}

.form-label {
  display: block;
  margin-bottom: 0.2rem;
  font-size: 12px;
  line-height: 1.3;
  font-weight: 700;
  color: #334155;
}

.form-label--muted {
  color: #64748b;
  font-weight: 600;
}

.form-field-row {
  display: grid;
  grid-template-columns: minmax(6.5rem, 8.5rem) minmax(0, 1fr);
  gap: 0.25rem 0.5rem;
  align-items: center;
}

.form-field-row .form-label {
  margin-bottom: 0;
  text-align: right;
  font-size: 11px;
}

.form-field-row--stack {
  grid-template-columns: 1fr;
  align-items: stretch;
}

.form-field-row--stack .form-label {
  text-align: left;
}

.form-field-stack {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.form-field-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}

.form-field-head .form-label {
  margin-bottom: 0;
}

.textarea-expand-button {
  flex: 0 0 auto;
  height: 26px;
  padding: 0 8px;
  color: #1d3557;
  border-color: #cbd5e1;
}

.form-input,
.form-textarea {
  width: 100%;
  padding: 0.35rem 0.6rem;
  font-size: 13px;
  line-height: 1.4;
  background: #fff;
  border: 1px solid rgb(229 231 235);
  border-radius: 0.5rem;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.form-input:focus,
.form-textarea:focus {
  border-color: #1d3557;
  box-shadow: 0 0 0 3px rgb(29 53 87 / 10%);
}

.form-textarea {
  resize: vertical;
  min-height: 2.75rem;
}

.large-text-editor-popup {
  width: min(920px, calc(100vw - 32px));
  max-height: calc(100vh - 48px);
  overflow: hidden;
}

.large-text-editor {
  display: flex;
  flex-direction: column;
  height: min(720px, calc(100vh - 48px));
  background: #fff;
}

.large-text-editor__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border-bottom: 1px solid #e2e8f0;
}

.large-text-editor__head h3 {
  margin: 2px 0 0;
  font-size: 18px;
  font-weight: 800;
  color: #0f172a;
}

.large-text-editor__eyebrow {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
}

.large-text-editor__textarea {
  flex: 1;
  width: 100%;
  min-height: 0;
  padding: 18px 20px;
  border: 0;
  outline: none;
  resize: none;
  font: inherit;
  font-size: 15px;
  line-height: 1.8;
  color: #0f172a;
}

.cases-compact .space-y-6 > :not([hidden]) ~ :not([hidden]) {
  margin-top: 0.875rem;
}

.cases-compact .space-y-5 > :not([hidden]) ~ :not([hidden]) {
  margin-top: 0.75rem;
}

.cases-compact .space-y-4 > :not([hidden]) ~ :not([hidden]) {
  margin-top: 0.625rem;
}

.cases-compact .gap-4 {
  gap: 0.625rem;
}

.cases-compact .gap-3 {
  gap: 0.5rem;
}

.cases-compact .p-6 {
  padding: 0.875rem;
}

.cases-compact .p-5 {
  padding: 0.75rem;
}

.cases-compact .mt-2.text-xs {
  margin-top: 0.25rem;
  font-size: 11px;
  line-height: 1.35;
}

.cases-compact .rounded-xl.border.px-4.py-3 {
  padding: 0.5rem 0.65rem;
  font-size: 12px;
  line-height: 1.45;
}

.section-block {
  border: 1px solid #e5e7eb;
  border-radius: 24px;
  background: #ffffff;
  padding: 18px;
}

.section-block--blue {
  background: #ffffff;
  border-color: #e5e7eb;
}

.section-block--neutral {
  background: #ffffff;
  border-color: #e5e7eb;
}

.section-block--violet {
  background: #ffffff;
  border-color: #e5e7eb;
}

.section-block__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.section-block__eyebrow {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #64748b;
}

.section-block__title {
  margin-top: 4px;
  font-size: 20px;
  line-height: 1.2;
  font-weight: 800;
  color: #0f172a;
}

.section-block__hint {
  max-width: 260px;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  padding: 8px 12px;
  font-size: 12px;
  line-height: 1.5;
  color: #475569;
}


.review-module-nav {
  display: flex;
  justify-content: center;
  align-items: stretch;
  gap: 12px;
  margin-bottom: 8px;
}

.review-module-nav__item {
  flex: 1;
  max-width: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 14px 16px;
  border-radius: 14px;
  border: 2px solid #e2e8f0;
  background: #fff;
  transition: all 0.2s ease;
  cursor: pointer;
}

.review-module-nav__item.is-active {
  border-color: #1d3557;
  background: #1d3557;
  box-shadow: 0 8px 20px rgba(29, 53, 87, 0.18);
}

.review-module-nav__step {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #94a3b8;
}

.review-module-nav__label {
  font-size: 17px;
  font-weight: 800;
  color: #334155;
}

.review-module-nav__item.is-active .review-module-nav__step,
.review-module-nav__item.is-active .review-module-nav__label {
  color: #fff;
}

.review-module-nav__hint {
  text-align: center;
  font-size: 12px;
  color: #64748b;
  margin-bottom: 12px;
}

.scene-studio__layout {
  display: grid;
  grid-template-columns: 168px 1fr;
  gap: 16px;
  align-items: start;
}

.scene-studio__nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scene-studio__nav-item {
  text-align: left;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  cursor: pointer;
}

.scene-studio__nav-item.is-active {
  border-color: #1d3557;
  background: #eff6ff;
}

.scene-studio__nav-index {
  display: block;
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
}

.scene-studio__nav-name {
  display: block;
  margin-top: 2px;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.scene-studio__nav-meta {
  display: block;
  margin-top: 4px;
  font-size: 10px;
  color: #64748b;
}

.scene-studio__tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.scene-studio__tab {
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid #e2e8f0;
  background: #fff;
  font-size: 13px;
  font-weight: 700;
  color: #475569;
  cursor: pointer;
}

.scene-studio__tab.is-active {
  border-color: #1d3557;
  background: #1d3557;
  color: #fff;
}

.scene-editor-card--studio {
  border: none;
  box-shadow: none;
  padding: 0;
}

.assessment-import-card {
  margin-bottom: 12px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px dashed #cbd5e1;
  background: #f8fafc;
}

.assessment-import-card--case {
  margin-bottom: 16px;
}

.assessment-import-card__rule {
  margin: 8px 0 10px;
  line-height: 1.5;
}

.assessment-import-card__head {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 10px;
}

.assessment-import-file {
  cursor: pointer;
}

.scene-flow-panel {
  padding: 4px 0;
}

.scene-flow-panel__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.scene-flow-panel__badge--bucket {
  color: #1d3557;
  font-weight: 700;
}

.scene-flow-panel__badge {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}

.scene-flow-panel__actions {
  display: flex;
  gap: 8px;
}

.scene-flow-panel__empty {
  padding: 24px 12px;
  text-align: center;
  font-size: 13px;
  color: #64748b;
  border: 1px dashed #e2e8f0;
  border-radius: 12px;
}

.scene-flow-panel__json {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scene-flow-stage {
  padding: 14px;
  margin-bottom: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #f8fafc;
  width: 100%;
  max-width: 100%;
  transition: max-width 0.2s ease, padding 0.2s ease;
}

.scene-flow-stage--collapsed {
  max-width: 100%;
  padding: 8px 12px;
}

.scene-flow-stage__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.scene-flow-stage__index {
  font-size: 13px;
  font-weight: 800;
  color: #1d3557;
}

.scene-flow-stage__core {
  display: block;
}

.scene-flow-stage__audit {
  margin-top: 6px;
  padding-top: 0;
  border-top: none;
}

.scene-flow-stage__stats {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 4px;
}

.scene-flow-stage__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  align-items: start;
}

.scene-flow-stage__row .form-input,
.scene-flow-stage__row .form-textarea {
  min-height: 44px;
}

.scene-flow-stage__row .form-textarea {
  resize: vertical;
}

.scene-flow-stage__col {
  min-width: 0;
}

.scene-flow-stage__hint {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.5;
}

.scene-flow-tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.scene-flow-tag {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
  background: #fff;
  border: 1px solid #e2e8f0;
}

.scene-flow-tag--required {
  border-color: #f59e0b;
  background: #fffbeb;
  color: #b45309;
}

.scene-flow-stage__advanced {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
}

.scene-flow-advanced-block + .scene-flow-advanced-block {
  margin-top: 14px;
}

.scene-flow-advanced-block__title {
  font-size: 12px;
  font-weight: 800;
  color: #475569;
  margin-bottom: 8px;
}

.scene-flow-advanced-row {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.scene-flow-advanced-row--single {
  grid-template-columns: 1fr auto;
}

.scene-flow-check {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
}

.detail-hero {
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #ffffff;
  padding: 12px 14px;
  box-shadow: none;
}

.detail-hero__eyebrow {
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #64748b;
}

.detail-hero__title {
  margin-top: 4px;
  font-size: 16px;
  line-height: 1.35;
  font-weight: 800;
  color: #0f172a;
}

.detail-hero__desc {
  margin-top: 4px;
  max-width: 760px;
  font-size: 12px;
  line-height: 1.5;
  color: #475569;
}

.detail-hero__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.detail-hero__chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  color: #475569;
  padding: 4px 8px;
  font-size: 11px;
  font-weight: 700;
}

.detail-hero__chip--blue {
  background: #f8fafc;
  color: #475569;
}

.detail-hero__chip--amber {
  background: #f8fafc;
  color: #475569;
}

.detail-hero__chip--cyan {
  background: #f8fafc;
  color: #475569;
}

.detail-hero__chip--emerald {
  background: #f8fafc;
  color: #475569;
}

.workspace-panel {
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #ffffff;
  padding: 12px;
  box-shadow: none;
}

.workspace-panel--indigo {
  background: #ffffff;
  border-color: #e5e7eb;
}

.workspace-panel--cyan {
  background: #ffffff;
  border-color: #e5e7eb;
}

.workspace-panel--amber {
  background: #ffffff;
  border-color: #e5e7eb;
}

.workspace-panel--emerald {
  background: #ffffff;
  border-color: #e5e7eb;
}

.wp__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.wp__eyebrow {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #64748b;
}

.workspace-panel__title {
  margin-top: 2px;
  font-size: 15px;
  line-height: 1.3;
  font-weight: 800;
  color: #0f172a;
}

.supplement-toolbar--inline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.supplement-toolbar--inline .supplement-toolbar__desc {
  flex: 1;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.source-panel--compact .source-panel__header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.role-compact-table .role-compact-row {
  background: #fff;
}

.workspace-panel__desc {
  margin-top: 4px;
  max-width: 760px;
  font-size: 12px;
  line-height: 1.45;
  color: #64748b;
}

.workspace-panel__badge {
  flex-shrink: 0;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  padding: 4px 8px;
  font-size: 11px;
  font-weight: 700;
  color: #334155;
}

.workspace-panel__body {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.scene-workbench {
  border: 0;
  border-radius: 0;
  background: transparent;
  padding: 0;
}

.scene-workbench__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.scene-workbench__eyebrow {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #64748b;
}

.scene-workbench__title {
  margin-top: 6px;
  font-size: 20px;
  line-height: 1.3;
  font-weight: 800;
  color: #0f172a;
}

.scene-workbench__hint {
  max-width: 300px;
  border-radius: 18px;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.6;
  color: #475569;
}

.scene-workbench__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.scene-workbench__chip {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  color: #475569;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 700;
}

.scene-workbench__chip--slate {
  background: #f8fafc;
  color: #475569;
}

.scene-workbench__chip--blue {
  background: #f8fafc;
  color: #475569;
}

.scene-workbench__chip--violet {
  background: #f8fafc;
  color: #475569;
}

.scene-workbench__chip--amber {
  background: #f8fafc;
  color: #475569;
}

.scene-editor-card {
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #ffffff;
  padding: 12px;
  box-shadow: none;
}

.scene-editor-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.scene-editor-card__index {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  color: #475569;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 800;
}

.scene-editor-card__panel {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #ffffff;
  padding: 10px;
}

.scene-editor-card__panel + .scene-editor-card__panel {
  margin-top: 8px;
}

.scene-editor-card__panel--summary {
  background: #ffffff;
  border-color: #e5e7eb;
}

.scene-editor-card__panel--roles {
  background: #ffffff;
  border-color: #e5e7eb;
}

.scene-editor-card__panel--copy {
  background: #ffffff;
  border-color: #e5e7eb;
}

.scene-editor-card__panel--json {
  background: #ffffff;
  border-color: #e5e7eb;
}

.scene-editor-card__section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.scene-editor-card__eyebrow {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #64748b;
}

.scene-editor-card__title {
  margin-top: 2px;
  font-size: 15px;
  line-height: 1.3;
  font-weight: 800;
  color: #0f172a;
}

.scene-editor-card__section-title {
  margin-top: 4px;
  font-size: 16px;
  line-height: 1.35;
  font-weight: 800;
  color: #0f172a;
}

.scene-editor-card__helper {
  max-width: 260px;
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}

.scene-stage-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
}

.scene-stage-toolbar__meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.scene-stage-toolbar__badge {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  color: #475569;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 800;
}

.scene-stage-toolbar__hint {
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}

.scene-stage-toolbar__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.scene-stage-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scene-stage-empty {
  border: 1px dashed #cbd5e1;
  border-radius: 12px;
  background: #ffffff;
  padding: 10px;
  font-size: 12px;
  line-height: 1.5;
  color: #64748b;
}

.scene-stage-card {
  border-radius: 14px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  padding: 10px;
  box-shadow: none;
}

.scene-stage-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.scene-stage-card__eyebrow {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #64748b;
}

.scene-stage-card__title {
  margin-top: 2px;
  font-size: 14px;
  line-height: 1.3;
  font-weight: 800;
  color: #0f172a;
}

.scene-stage-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 8px;
}

.scene-stage-grid--rules {
  margin-top: 8px;
}

.scene-stage-meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.scene-stage-block {
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  padding: 10px;
}

.scene-stage-block--sky {
  background: #ffffff;
  border-color: #e5e7eb;
}

.scene-stage-block--violet {
  background: #ffffff;
  border-color: #e5e7eb;
}

.scene-stage-block--amber {
  background: #ffffff;
  border-color: #e5e7eb;
}

.scene-stage-block--emerald {
  background: #ffffff;
  border-color: #e5e7eb;
}

.scene-stage-block__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.scene-stage-block__eyebrow {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #64748b;
}

.scene-stage-block__title {
  margin-top: 2px;
  font-size: 13px;
  line-height: 1.3;
  font-weight: 800;
  color: #0f172a;
}

.scene-stage-block__empty {
  border: 1px dashed rgba(148, 163, 184, 0.4);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.66);
  padding: 8px;
  font-size: 11px;
  line-height: 1.45;
  color: #64748b;
}

.scene-stage-item + .scene-stage-item {
  margin-top: 6px;
}

.scene-stage-item {
  border-radius: 10px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.88);
  padding: 8px;
}

.scene-stage-item__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.scene-stage-item__title {
  font-size: 13px;
  font-weight: 800;
  color: #334155;
}

.scene-stage-checkbox {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 6px 0;
  font-size: 12px;
  font-weight: 700;
  color: #334155;
}

.scene-stage-checkbox--compact {
  margin: 4px 0 6px;
}

.scene-stage-checkbox input {
  width: 16px;
  height: 16px;
  accent-color: #1d3557;
}

.persona-stack-list {
  position: relative;
  padding-top: 8px;
  padding-bottom: 8px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.persona-stack-card {
  position: relative;
  cursor: default;
  transition: transform 0.24s ease, z-index 0.24s ease;
}

.persona-stack-shell {
  position: relative;
  padding-top: 0;
}

.persona-stack-layer {
  position: absolute;
  left: 18px;
  right: 18px;
  height: 100%;
  border-radius: 26px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.86) 0%, rgba(241, 245, 249, 0.92) 100%);
  pointer-events: none;
  transition: all 0.24s ease;
  display: none;
}

.persona-stack-layer--back {
  top: 0;
  transform: scale(0.985);
  opacity: 0.6;
}

.persona-stack-layer--mid {
  top: 5px;
  transform: scale(0.992);
  opacity: 0.82;
}

.persona-stack-surface {
  position: relative;
  border-radius: 14px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  box-shadow: none;
  padding: 10px 12px;
  transition: transform 0.24s ease, box-shadow 0.24s ease, border-color 0.24s ease;
}

.persona-stack-surface--clickable {
  cursor: pointer;
}

.persona-stack-card.is-collapsed:hover .persona-stack-surface,
.persona-stack-card.is-collapsed .persona-stack-surface--clickable:hover {
  transform: translateY(-1px);
  border-color: #cbd5e1;
  box-shadow: none;
}

.persona-stack-card.is-expanded .persona-stack-layer {
  opacity: 0;
  transform: scale(0.98);
}

.persona-stack-card.is-expanded {
  transform: translateY(-2px);
}

.persona-stack-card.is-expanded .persona-stack-surface {
  border-color: #cbd5e1;
  box-shadow: none;
}

.persona-stack-header {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.persona-stack-toggle {
  color: #94a3b8;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}

.persona-stack-summary {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.45;
}

.persona-stack-expanded {
  padding-bottom: 2px;
}

.persona-role-summary {
  border-radius: 16px;
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  padding: 12px 14px;
  font-size: 13px;
  line-height: 1.6;
  color: #475569;
}

.persona-compact-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 6px;
}

.persona-compact-panel {
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  padding: 8px 10px;
}

.persona-compact-panel__title {
  font-size: 12px;
  line-height: 1.3;
  font-weight: 800;
  color: #0f172a;
}

.form-textarea--compact {
  min-height: 2.5rem;
}

.persona-toolbar-button {
  white-space: nowrap;
}

.persona-toolbar-button:deep(.van-button__text) {
  white-space: nowrap;
}

.persona-toolbar-button:deep(.van-button) {
  min-width: 96px;
}

@media (max-width: 768px) {
  .persona-toolbar-button {
    min-width: auto;
  }
}

@media (max-width: 768px) {
  .section-block__header,
  .wp__header,
  .scene-workbench__header,
  .scene-editor-card__section-head {
    flex-direction: column;
  }

  .section-block__hint,
  .workspace-panel__badge,
  .scene-workbench__hint,
  .scene-editor-card__helper {
    max-width: none;
  }

  .detail-hero__title,
  .workspace-panel__title,
  .section-block__title,
  .scene-workbench__title,
  .scene-editor-card__title {
    font-size: 18px;
  }

  .persona-stack-surface {
    padding: 18px;
  }

  .persona-stack-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .persona-compact-grid {
    grid-template-columns: 1fr;
  }

  .scene-stage-toolbar,
  .scene-stage-card__header,
  .scene-stage-block__header {
    flex-direction: column;
  }

  .scene-stage-toolbar__actions {
    width: 100%;
    justify-content: flex-start;
  }

  .scene-stage-grid {
    grid-template-columns: 1fr;
  }

  .scene-stage-meta-grid {
    grid-template-columns: 1fr;
  }

  .scene-flow-stage__core {
    grid-template-columns: 1fr;
  }

  .scene-flow-advanced-row {
    grid-template-columns: 1fr;
  }
}

.mode-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  background: #fff;
  text-align: left;
  transition: all 0.2s ease;
}

.mode-card.active {
  border-color: #1d3557;
  box-shadow: 0 0 0 3px rgb(29 53 87 / 8%);
  background: #f8fbff;
}

.mode-card__title {
  font-size: 15px;
  font-weight: 800;
  color: #1f2937;
}

.mode-card__desc {
  font-size: 13px;
  line-height: 1.7;
  color: #64748b;
}

.file-hint {
  border: 1px solid #e5e7eb;
  background: #ffffff;
  border-radius: 16px;
  padding: 14px 16px;
}

.file-dropzone {
  border: 1px dashed #cbd5e1;
  background: #ffffff;
  border-radius: 20px;
  padding: 28px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  background: #f1f5f9;
  color: #64748b;
}

.status-pill.ready {
  background: #fff7ed;
  color: #c2410c;
}

.status-pill.success {
  background: #ecfdf5;
  color: #047857;
}

.status-pill.error {
  background: #fef2f2;
  color: #dc2626;
}

.preview-card {
  border: 1px solid #eef2f7;
  border-radius: 16px;
  background: #fff;
  padding: 14px 16px;
}

.preview-label,
.section-title {
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #94a3b8;
}

.preview-value {
  margin-top: 8px;
  color: #1f2937;
  font-weight: 700;
}

.preview-body {
  margin-top: 10px;
  color: #475569;
  line-height: 1.8;
  white-space: pre-wrap;
}

.supplement-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  border-radius: 16px;
  padding: 14px 16px;
}

.supplement-toolbar__title {
  font-weight: 800;
  color: #0f172a;
}

.supplement-toolbar__desc {
  margin-top: 4px;
  font-size: 13px;
  line-height: 1.7;
  color: #64748b;
}

.source-panel {
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  background: #fff;
  padding: 16px;
}

.section-block,
.detail-hero,
.workspace-panel,
.scene-editor-card,
.scene-stage-card,
.scene-stage-block,
.persona-stack-surface,
.file-hint,
.file-dropzone,
.supplement-toolbar,
.source-panel {
  position: relative;
  border-color: #d4dde8;
  background: linear-gradient(180deg, #ffffff 0%, #fcfdff 100%);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.96) inset, 0 0 0 1px rgba(212, 221, 232, 0.4), 0 14px 28px rgba(15, 23, 42, 0.035);
}

.section-block::before,
.detail-hero::before,
.workspace-panel::before,
.scene-editor-card::before,
.scene-stage-card::before,
.scene-stage-block::before,
.persona-stack-surface::before,
.file-hint::before,
.file-dropzone::before,
.supplement-toolbar::before,
.source-panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 16px;
  right: 16px;
  height: 1px;
  background: linear-gradient(90deg, rgba(29, 53, 87, 0.2), rgba(148, 163, 184, 0));
  pointer-events: none;
}

.section-block__hint,
.workspace-panel__badge,
.detail-hero__chip,
.scene-workbench__hint,
.scene-workbench__chip,
.scene-editor-card__index,
.scene-stage-toolbar,
.scene-stage-toolbar__badge,
.scene-stage-empty,
.scene-stage-item,
.persona-role-summary,
.persona-compact-panel,
.preview-card {
  border-color: #d8e0ea;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.92) inset, 0 0 0 1px rgba(216, 224, 234, 0.28);
}

.wp__header,
.section-block__header {
  padding-bottom: 16px;
  border-bottom: 1px solid #edf2f7;
}

.source-panel__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 12px;
}

.source-panel__meta {
  font-size: 12px;
  color: #94a3b8;
}

.source-panel__textarea {
  font-family: 'KaiTi', 'STKaiti', 'FangSong', serif;
}

/* 全局精简：隐藏说明性小字，保留核心输入信息 */
.cases-compact .section-block__hint,
.cases-compact .workspace-panel__desc,
.cases-compact .workspace-panel__badge,
.cases-compact .scene-editor-card__helper,
.cases-compact .supplement-toolbar__desc,
.cases-compact .source-panel__meta,
.cases-compact .preview-label,
.cases-compact .mode-card__desc,
.cases-compact .section-block__eyebrow,
.cases-compact .wp__eyebrow,
.cases-compact .review-module-nav__step,
.cases-compact .scene-editor-card__section-title,
.cases-compact p.mt-1.text-xs,
.cases-compact p.mt-2.text-xs,
.cases-compact p.text-xs,
.cases-compact .text-xs.text-slate-400 {
  display: none !important;
}

/* 视觉收敛：统一更简约的大卡片风格 */
.cases-compact .section-block,
.cases-compact .workspace-panel,
.cases-compact .scene-editor-card {
  border-color: #e2e8f0;
  border-radius: 18px;
  background: #ffffff;
  box-shadow: none;
}

@media (max-width: 960px) {
  .supplement-toolbar {
    flex-direction: column;
    align-items: stretch;
  }
}

/* ── 角色审核工作台 ─────────────────────────────────────── */
.role-audit-workspace {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 0;
  height: calc(92vh - 280px);
  min-height: 480px;
  max-height: 680px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  overflow: hidden;
  background: #fff;
}

/* ── 左侧角色列表 ─────────────────────────────────────── */
.role-audit-sidebar {
  display: flex;
  flex-direction: column;
  border-right: 1px solid #f1f5f9;
  background: #f8fafc;
  overflow: hidden;
  height: 100%;
}

.role-audit-sidebar__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 13px 14px 10px;
  border-bottom: 1px solid #f1f5f9;
}

.role-audit-sidebar__title {
  font-size: 12px;
  font-weight: 800;
  color: #475569;
  letter-spacing: 0.04em;
}

.role-audit-sidebar__count {
  font-size: 11px;
  color: #94a3b8;
  background: #e2e8f0;
  border-radius: 999px;
  padding: 2px 8px;
}

.role-audit-sidebar__list {
  flex: 1;
  overflow-y: auto;
  padding: 6px 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.role-audit-sidebar__footer {
  padding: 8px;
  border-top: 1px solid #f1f5f9;
}

.role-sidebar-add-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 7px 12px;
  border: 1.5px dashed #cbd5e1;
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s;
}

.role-sidebar-add-btn:hover {
  border-color: #1d3557;
  color: #1d3557;
  background: #eff6ff;
}

.role-audit-sidebar__note {
  padding: 10px 14px 12px;
  border-top: 1px solid #f1f5f9;
}

.role-audit-sidebar__note-title {
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  margin-bottom: 4px;
}

.role-audit-sidebar__note-text {
  font-size: 11px;
  line-height: 1.6;
  color: #b0bfd0;
}

/* ── 角色列表单项 ─────────────────────────────────────── */
.role-sidebar-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 10px;
  border-radius: 9px;
  border: 1.5px solid transparent;
  background: transparent;
  cursor: pointer;
  text-align: left;
  transition: all 0.14s;
  width: 100%;
}

.role-sidebar-item:hover:not(.is-active) {
  background: #f1f5f9;
  border-color: #e2e8f0;
}

.role-sidebar-item.is-active {
  background: #1d3557;
  border-color: #1d3557;
}

.role-sidebar-item__avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, #3b82f6, #6366f1);
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  letter-spacing: 0;
}

.role-sidebar-item.is-active .role-sidebar-item__avatar {
  background: rgba(255,255,255,0.18);
}

.role-sidebar-item__info {
  flex: 1;
  min-width: 0;
}

.role-sidebar-item__name {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.3;
}

.role-sidebar-item.is-active .role-sidebar-item__name {
  color: #fff;
}

.role-sidebar-item__meta {
  display: flex;
  align-items: center;
  gap: 3px;
  margin-top: 2px;
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.2;
}

.role-sidebar-item.is-active .role-sidebar-item__meta {
  color: rgba(255,255,255,0.6);
}

.role-sidebar-item__status {
  flex-shrink: 0;
}

/* ── 审核状态徽章 ──────────────────────────────────────── */
.role-review-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.role-review-badge--pending {
  background: #fef9c3;
  color: #a16207;
}

.role-review-badge--needs-update {
  background: #ffedd5;
  color: #c2410c;
}

.role-review-badge--approved {
  background: #dcfce7;
  color: #15803d;
}

.role-review-badge--lg {
  padding: 3px 10px;
  font-size: 12px;
}

/* ── 审核状态下拉 ──────────────────────────────────────── */
.role-review-status-select {
  padding: 4px 8px;
  border: 1.5px solid #e2e8f0;
  border-radius: 7px;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
  background: #fff;
  cursor: pointer;
  outline: none;
  transition: border-color 0.15s;
}

.role-review-status-select:focus {
  border-color: #1d3557;
}

/* ── 右侧工作区 ──────────────────────────────────────── */
.role-audit-main {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
  background: #fff;
}

/* 空状态 */
.role-audit-main__empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 60px 32px;
  color: #94a3b8;
}

.role-audit-main__empty-icon {
  font-size: 40px;
  opacity: 0.3;
}

.role-audit-main__empty-title {
  font-size: 15px;
  font-weight: 700;
  color: #64748b;
}

.role-audit-main__empty-desc {
  font-size: 13px;
  text-align: center;
  max-width: 300px;
  line-height: 1.7;
  color: #94a3b8;
}

/* ── 角色详情头部 ─────────────────────────────────────── */
.role-audit-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 18px 13px;
  border-bottom: 1px solid #f1f5f9;
  background: #fff;
  flex-shrink: 0;
}

.role-audit-header__avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1d3557 60%, #3b82f6);
  color: #fff;
  font-size: 18px;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.role-audit-header__info {
  flex: 1;
  min-width: 0;
}

.role-audit-header__name-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.role-audit-header__name {
  font-size: 18px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.2;
}

.role-audit-header__meta-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 4px;
  font-size: 11px;
  color: #94a3b8;
}

.role-audit-header__sep {
  color: #d1d5db;
}

.role-audit-header__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

/* ── 子标签页 ────────────────────────────────────────── */
.role-audit-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid #f1f5f9;
  padding: 0 18px;
  background: #fff;
  flex-shrink: 0;
}

.role-audit-tab {
  padding: 9px 14px;
  font-size: 12px;
  font-weight: 700;
  color: #94a3b8;
  background: transparent;
  border: none;
  border-bottom: 2.5px solid transparent;
  cursor: pointer;
  transition: all 0.14s;
  margin-bottom: -1px;
  letter-spacing: 0.01em;
}

.role-audit-tab:hover {
  color: #334155;
}

.role-audit-tab.is-active {
  color: #1d3557;
  border-bottom-color: #1d3557;
}

/* ── 标签页内容容器 ───────────────────────────────────── */
.role-audit-tab-content {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  background: #f8fafc;
}

.role-audit-tab-body {
  position: absolute;
  inset: 0;
  overflow-y: auto;
  padding: 14px 16px;
}

.role-audit-field-row {
  margin-bottom: 12px;
}

/* ── AI 审核建议卡片 ──────────────────────────────────── */
.role-ai-review-card {
  border: 1px solid #bfdbfe;
  border-radius: 12px;
  background: #eff6ff;
  overflow: hidden;
}

.role-ai-review-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 14px;
  border-bottom: 1px solid #bfdbfe;
  background: rgba(219, 234, 254, 0.5);
}

.role-ai-review-card__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 7px;
  background: #3b82f6;
  color: #fff;
  font-size: 11px;
  font-weight: 800;
}

.role-ai-review-card__title {
  font-size: 13px;
  font-weight: 700;
  color: #1e40af;
}

.role-ai-review-card__body {
  padding: 14px;
  font-size: 13px;
  line-height: 1.8;
  color: #1e293b;
  white-space: pre-line;
}

.role-ai-review-card__loading,
.role-ai-review-card__empty {
  padding: 28px 14px;
  font-size: 13px;
  color: #64748b;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}

/* ── 审核记录表格 ─────────────────────────────────────── */
.role-audit-log {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
}

.role-audit-log__header {
  padding: 11px 14px;
  font-size: 12px;
  font-weight: 700;
  color: #475569;
  background: #f8fafc;
  border-bottom: 1px solid #f1f5f9;
}

.role-audit-log__empty {
  padding: 36px 14px;
  text-align: center;
  font-size: 13px;
  color: #94a3b8;
}

.role-audit-log__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.role-audit-log__table th {
  padding: 9px 14px;
  text-align: left;
  font-size: 11px;
  font-weight: 700;
  color: #94a3b8;
  background: #f8fafc;
  border-bottom: 1px solid #f1f5f9;
}

.role-audit-log__table td {
  padding: 9px 14px;
  color: #334155;
  border-bottom: 1px solid #f8fafc;
  font-size: 12px;
}

.role-audit-log__table tr:last-child td {
  border-bottom: none;
}

/* ── 人物身份行（tab-body 顶部独立输入框） ───────────── */
.rcf-identity-row {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 12px;
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.rcf-identity-label {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  line-height: 1;
}

.rcf-identity-input {
  padding: 7px 10px;
  border: 1.5px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  font-size: 13px;
  font-weight: 500;
  color: #0f172a;
  outline: none;
  transition: border-color 0.15s;
  font-family: inherit;
  width: 100%;
  box-sizing: border-box;
}

.rcf-identity-input:focus {
  border-color: #1d3557;
  background: #fff;
}

/* ══════════════════════════════════════════════════════
   wp — 统一工作台面板系统
   三个 tab（基础信息 / 角色审核 / 场景编辑）共用
   ══════════════════════════════════════════════════════ */

/* 面板容器 */
.wp {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #fff;
  overflow: hidden;
}

/* 面板顶栏 */
.wp__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 13px 16px 12px;
  border-bottom: 1px solid #f1f5f9;
  background: #fff;
}

.wp__header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.wp__step {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: #1d3557;
  color: #fff;
  font-size: 11px;
  font-weight: 800;
  flex-shrink: 0;
}

.wp__title {
  font-size: 14px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.3;
}

.wp__sub {
  margin-top: 2px;
  font-size: 12px;
  color: #94a3b8;
}

.wp__badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  font-size: 11px;
  font-weight: 700;
  color: #475569;
  white-space: nowrap;
}

.wp__badge--count {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #1d4ed8;
}

/* 面板内容区 */
.wp__body {
  background: #f8fafc;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 内容卡片 */
.wp-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  overflow: hidden;
}

.wp-card__header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid #f1f5f9;
  background: #f8fafc;
}

.wp-card__title {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.wp-card__meta {
  font-size: 12px;
  color: #94a3b8;
  margin-left: auto;
}

.wp-card__body {
  padding: 14px;
}

/* 警告条 */
.wp-alert {
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 13px;
  line-height: 1.6;
}

.wp-alert--blue {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1e40af;
}

.wp-alert--amber {
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #92400e;
}

.wp-alert__title {
  font-weight: 700;
  margin-bottom: 4px;
}

.wp-alert__row {
  font-size: 12px;
  margin-top: 2px;
}

/* 表单 */
.wp-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: 1fr;
}

.wp-grid--3 {
  grid-template-columns: 1fr;
}

@media (min-width: 700px) {
  .wp-grid--3 {
    grid-template-columns: repeat(3, 1fr);
  }
}

.wp-mt {
  margin-top: 4px;
}

.wp-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.wp-label {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  line-height: 1;
}

.wp-required {
  color: #ef4444;
}

.wp-hint {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.6;
}

.wp-input,
.wp-textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 7px 10px;
  border: 1.5px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  font-size: 13px;
  font-weight: 500;
  color: #0f172a;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
  font-family: inherit;
}

.wp-input:focus,
.wp-textarea:focus {
  border-color: #1d3557;
  box-shadow: 0 0 0 3px rgba(29, 53, 87, 0.08);
}

.wp-input::placeholder,
.wp-textarea::placeholder {
  color: #cbd5e1;
  font-weight: 400;
}

.wp-textarea {
  resize: vertical;
  min-height: 80px;
  line-height: 1.6;
}

.wp-textarea--mono {
  font-family: 'KaiTi', 'STKaiti', 'FangSong', serif;
  font-size: 13px;
}

/* 场景导航 */
.scene-studio {
  display: block;
}

.scene-studio__layout {
  display: grid;
  grid-template-columns: 168px 1fr;
  gap: 16px;
  align-items: start;
}

.wp__nav-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 9px 12px;
  border-radius: 10px;
  border: 1.5px solid #e2e8f0;
  background: #fff;
  cursor: pointer;
  transition: all 0.14s;
}

.wp__nav-item:hover:not(.is-active) {
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.wp__nav-item.is-active {
  border-color: #1d3557;
  background: #1d3557;
}

.wp__nav-index {
  display: block;
  font-size: 10px;
  font-weight: 700;
  color: #94a3b8;
  letter-spacing: 0.06em;
}

.wp__nav-item.is-active .wp__nav-index {
  color: rgba(255,255,255,0.6);
}

.wp__nav-name {
  display: block;
  margin-top: 3px;
  font-size: 12px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.3;
}

.wp__nav-item.is-active .wp__nav-name {
  color: #fff;
}

.wp__nav-meta {
  display: block;
  margin-top: 4px;
  font-size: 10px;
  color: #64748b;
}

.wp__nav-item.is-active .wp__nav-meta {
  color: rgba(255,255,255,0.5);
}

/* 场景 tabs */
.wp__tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid #f1f5f9;
  margin-bottom: 14px;
}

.wp__tab {
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 700;
  color: #94a3b8;
  background: transparent;
  border: none;
  border-bottom: 2.5px solid transparent;
  cursor: pointer;
  transition: all 0.14s;
  margin-bottom: -1px;
}

.wp__tab:hover {
  color: #334155;
}

.wp__tab.is-active {
  color: #1d3557;
  border-bottom-color: #1d3557;
}

/* ── 响应式 ──────────────────────────────────────────── */
@media (max-width: 768px) {
  .role-audit-workspace {
    grid-template-columns: 1fr;
    height: auto;
    max-height: none;
  }
  .role-audit-sidebar {
    border-right: none;
    border-bottom: 1px solid #f1f5f9;
    max-height: 240px;
  }
  .role-audit-header {
    flex-wrap: wrap;
  }
  .role-audit-header__actions {
    width: 100%;
  }
}
/* ── 案件预览弹窗 cpv-* ──────────────────────────────── */
.cpv-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px 14px;
  border-bottom: 1px solid #f1f5f9;
  background: #fff;
}

.cpv-header__left {
  flex: 1;
  min-width: 0;
}

.cpv-title {
  font-size: 18px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.3;
  margin-bottom: 8px;
}

.cpv-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.cpv-meta-text {
  font-size: 12px;
  color: #94a3b8;
}

.cpv-meta-sep {
  color: #d1d5db;
  font-size: 11px;
}

.cpv-header__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.cpv-close {
  color: #94a3b8;
  cursor: pointer;
  padding: 4px;
  transition: color 0.14s;
}

.cpv-close:hover {
  color: #334155;
}

.cpv-body {
  overflow-y: auto;
  padding: 16px 20px 24px;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 卡片 */
.cpv-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 14px 16px;
}

.cpv-card__label {
  font-size: 11px;
  font-weight: 800;
  color: #94a3b8;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 10px;
}

.cpv-text {
  font-size: 13px;
  line-height: 1.8;
  color: #334155;
}

/* 统计行 */
.cpv-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.cpv-stat {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.cpv-stat__num {
  font-size: 22px;
  font-weight: 800;
  color: #1d3557;
  line-height: 1;
}

.cpv-stat__label {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 600;
}

/* 角色列表 */
.cpv-person-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cpv-person {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f8fafc;
}

.cpv-person__avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1d3557, #3b82f6);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.cpv-person__info {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.cpv-person__name {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.cpv-person__type {
  font-size: 11px;
  color: #64748b;
  background: #e2e8f0;
  border-radius: 4px;
  padding: 1px 6px;
}

.cpv-person__arch {
  font-size: 11px;
  color: #3b82f6;
  background: #eff6ff;
  border-radius: 4px;
  padding: 1px 6px;
  border: 1px solid #bfdbfe;
}

/* 场景列表 */
.cpv-scene-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cpv-scene {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f8fafc;
}

.cpv-scene__idx {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: #1d3557;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 1px;
}

.cpv-scene__info {
  flex: 1;
  min-width: 0;
}

.cpv-scene__name {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.cpv-scene__desc {
  margin-top: 3px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}


</style>
