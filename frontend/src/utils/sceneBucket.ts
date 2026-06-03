/** Client-side scene bucket rules (mirror backend scene_bucket_service). */

export type SceneBucket = 'intake' | 'onsite' | 'investigation'

const BUCKET_LABELS: Record<SceneBucket, string> = {
  intake: '接警',
  onsite: '现场',
  investigation: '询问',
}

const KEYWORDS: Record<SceneBucket, RegExp> = {
  intake: /接警|报警|接处警|信息初核|110/,
  onsite: /现场|初查|勘查|处置|出警|到场/,
  investigation: /询问|讯问|审讯|核实|笔录|问询|压实/,
}

export function inferSceneBucket(sceneName: string, sceneIndex = 0, sceneCount = 1): SceneBucket {
  const text = String(sceneName || '').trim()
  if (text) {
    for (const bucket of ['intake', 'onsite', 'investigation'] as SceneBucket[]) {
      if (KEYWORDS[bucket].test(text)) return bucket
    }
  }
  if (sceneCount === 3 && sceneIndex >= 0 && sceneIndex < 3) {
    return (['intake', 'onsite', 'investigation'] as SceneBucket[])[sceneIndex]
  }
  if (sceneCount === 2) {
    return sceneIndex === 0 ? 'intake' : 'onsite'
  }
  return 'onsite'
}

export function sceneBucketLabel(sceneName: string, sceneIndex = 0, sceneCount = 1): string {
  const bucket = inferSceneBucket(sceneName, sceneIndex, sceneCount)
  return BUCKET_LABELS[bucket]
}

export const SCENE_NAME_PLACEHOLDERS = ['接警研判', '现场处置', '重点询问']
