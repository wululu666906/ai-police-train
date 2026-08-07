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

const STORAGE_KEY = 'case_pipeline_job_id'

const delay = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

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
