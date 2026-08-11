import { computed, ref } from 'vue'
import request from '../utils/request'

export type CasePipelineJob = {
  id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  stage: string
  progress: number
  message: string
  result?: any
  error?: string
  cache_hit?: boolean
}

export type NormalizedCasePipelineResult = {
  caseInfo: Record<string, any>
  scenes: any[]
  parseAiWorkflow: Record<string, any> | null
  sceneAiWorkflow: Record<string, any> | null
  aiWorkflows: Record<string, any>[]
}

const STORAGE_KEY = 'case_pipeline_job_id'

const delay = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

const compactWorkflowList = (...items: any[]) => {
  const result: Record<string, any>[] = []
  for (const item of items.flat()) {
    if (item && typeof item === 'object' && Object.keys(item).length) result.push(item)
  }
  return result
}

export const normalizeCasePipelineResult = (raw: any): NormalizedCasePipelineResult => {
  const payload = raw && typeof raw === 'object' ? raw : {}
  const caseInfo = payload.case_info && typeof payload.case_info === 'object'
    ? { ...payload.case_info }
    : { ...payload }
  const scenes = Array.isArray(payload.scenes)
    ? payload.scenes
    : Array.isArray(caseInfo.scenes)
      ? caseInfo.scenes
      : []
  const parseAiWorkflow = caseInfo.parse_ai_workflow || payload.parse_ai_workflow || caseInfo.ai_workflow || null
  const sceneAiWorkflow = caseInfo.scene_ai_workflow || payload.scene_ai_workflow || payload.ai_workflow || null
  const aiWorkflows = compactWorkflowList(
    caseInfo.ai_workflows,
    payload.ai_workflows,
    parseAiWorkflow,
    sceneAiWorkflow,
  )
  Object.assign(caseInfo, {
    scene_generation_mode: payload.scene_generation_mode || caseInfo.scene_generation_mode || '',
    scene_generation_warning: payload.scene_generation_warning || caseInfo.scene_generation_warning || '',
    scene_blueprints: payload.scene_blueprints || caseInfo.scene_blueprints || [],
    scene_scripts: payload.scene_scripts || caseInfo.scene_scripts || [],
    scene_role_map: payload.scene_role_map || caseInfo.scene_role_map || {},
    training_tasks: payload.training_tasks || caseInfo.training_tasks || [],
    state_machine: payload.state_machine || caseInfo.state_machine || null,
    observable_scoring_rules: payload.observable_scoring_rules || caseInfo.observable_scoring_rules || [],
    derived_artifact_version: payload.derived_artifact_version || caseInfo.derived_artifact_version || '',
    derived_revision: payload.derived_revision || caseInfo.derived_revision || '',
    scene_contract_schema_version: payload.scene_contract_schema_version || caseInfo.scene_contract_schema_version || '',
    quality_report: payload.quality_report || caseInfo.quality_report || null,
    parse_ai_workflow: parseAiWorkflow,
    scene_ai_workflow: sceneAiWorkflow,
    ai_workflows: aiWorkflows,
  })
  return { caseInfo, scenes, parseAiWorkflow, sceneAiWorkflow, aiWorkflows }
}

export const useCasePipeline = () => {
  const job = ref<CasePipelineJob | null>(null)
  const polling = ref(false)
  const isRunning = computed(() => ['queued', 'running'].includes(job.value?.status || ''))

  const poll = async (jobId: string): Promise<CasePipelineJob> => {
    polling.value = true
    try {
      while (true) {
        const current = await request.get(`/cases/pipeline/${jobId}`, { _skipErrorToast: true } as any) as CasePipelineJob
        job.value = current
        if (current.status === 'completed') {
          localStorage.removeItem(STORAGE_KEY)
          return current
        }
        if (current.status === 'failed') {
          localStorage.removeItem(STORAGE_KEY)
          throw new Error(current.error || '案件整理失败')
        }
        await delay(1200)
      }
    } finally {
      polling.value = false
    }
  }

  const startText = async (sourceText: string) => {
    const created = await request.post('/cases/pipeline/text', {
      source_text: sourceText,
      source_mode: 'plain_case',
      force_rebuild: true,
    }, { _skipErrorToast: true } as any) as CasePipelineJob
    job.value = created
    if (created.status === 'completed') return created
    localStorage.setItem(STORAGE_KEY, created.id)
    return poll(created.id)
  }

  const startFile = async (file: File) => {
    const payload = new FormData()
    payload.append('file', file)
    payload.append('source_mode', 'transcript_file')
    payload.append('force_rebuild', 'true')
    const created = await request.post('/cases/pipeline/file', payload, {
      timeout: 120000,
      _skipErrorToast: true,
    } as any) as CasePipelineJob
    job.value = created
    if (created.status === 'completed') return created
    localStorage.setItem(STORAGE_KEY, created.id)
    return poll(created.id)
  }

  const resume = async () => {
    const jobId = localStorage.getItem(STORAGE_KEY)
    if (!jobId) return null
    return poll(jobId)
  }

  const clear = () => {
    job.value = null
    localStorage.removeItem(STORAGE_KEY)
  }

  return { job, polling, isRunning, startText, startFile, resume, clear }
}
