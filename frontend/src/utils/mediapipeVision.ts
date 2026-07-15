const REMOTE_TASKS_VISION_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14'
const REMOTE_TASKS_VISION_WASM_URL = `${REMOTE_TASKS_VISION_URL}/wasm`

const LOCAL_TASKS_VISION_URL = import.meta.env.VITE_MEDIAPIPE_TASKS_VISION_URL || '/mediapipe/tasks-vision/index.js'
const LOCAL_TASKS_VISION_WASM_URL =
  import.meta.env.VITE_MEDIAPIPE_TASKS_VISION_WASM_URL || '/mediapipe/models/wasm'

const loadRemoteModule = async (url: string) => {
  const dynamicImporter = new Function('u', 'return import(/* @vite-ignore */ u)') as (u: string) => Promise<any>
  return dynamicImporter(url)
}

export interface VisionModuleCandidate {
  moduleUrl: string
  wasmUrl: string
  sourceLabel: string
  visionModule: any
}

async function loadBundledVisionModule(): Promise<VisionModuleCandidate | null> {
  try {
    const visionModule = await import('@mediapipe/tasks-vision')
    if (!visionModule?.FilesetResolver) return null
    return {
      moduleUrl: '@mediapipe/tasks-vision',
      wasmUrl: LOCAL_TASKS_VISION_WASM_URL,
      sourceLabel: 'npm',
      visionModule,
    }
  } catch (error) {
    console.warn('MediaPipe npm bundle load failed', error)
    return null
  }
}

export async function loadVisionTasksModule(): Promise<VisionModuleCandidate> {
  const bundled = await loadBundledVisionModule()
  if (bundled) return bundled

  const candidates = [
    {
      moduleUrl: LOCAL_TASKS_VISION_URL,
      wasmUrl: LOCAL_TASKS_VISION_WASM_URL,
      sourceLabel: 'local',
    },
    {
      moduleUrl: REMOTE_TASKS_VISION_URL,
      wasmUrl: REMOTE_TASKS_VISION_WASM_URL,
      sourceLabel: 'remote',
    },
    {
      moduleUrl: 'https://unpkg.com/@mediapipe/tasks-vision@0.10.14',
      wasmUrl: 'https://unpkg.com/@mediapipe/tasks-vision@0.10.14/wasm',
      sourceLabel: 'unpkg',
    },
  ] as const

  const errors: unknown[] = []
  for (const candidate of candidates) {
    try {
      const visionModule = await loadRemoteModule(candidate.moduleUrl)
      if (!visionModule?.FilesetResolver) continue
      return { ...candidate, visionModule }
    } catch (error) {
      errors.push(error)
      console.warn('MediaPipe vision load failed:', candidate.moduleUrl, error)
    }
  }
  throw errors[errors.length - 1] || new Error('Unable to load mediapipe vision module')
}
