import request from '../utils/request'

export interface PlaybackManifest {
  video_id: number
  status: 'missing' | 'processing' | 'ready' | 'failed'
  version?: string | null
  segment_count?: number
  segment_seconds?: number
  manifest?: string
  fallback_url?: string
  error?: string | null
}

interface CachedManifest {
  value: PlaybackManifest
  expiresAt: number
}

const manifestCache = new Map<number, CachedManifest>()
const queuedPriorities = new Map<number, number>()
let queueRunning = false

function resolveManifestMediaUrl(value: string): string {
  const url = String(value || '').trim()
  if (!url) return url
  if (/^(https?:)?\/\//i.test(url) || url.startsWith('data:') || url.startsWith('blob:')) return url
  if (url.startsWith('/')) return `${window.location.origin}${url}`
  return new URL(url, window.location.href).href
}

function absolutizeManifestUrls(manifest: string): string {
  return manifest
    .replace(/URI="([^"]+)"/g, (_match, url) => `URI="${resolveManifestMediaUrl(url)}"`)
    .split(/\r?\n/)
    .map((line) => {
      const stripped = line.trim()
      if (!stripped || stripped.startsWith('#')) return line
      return resolveManifestMediaUrl(stripped)
    })
    .join('\n')
}

export async function getPlaybackManifest(videoId: number, force = false): Promise<PlaybackManifest> {
  const cached = manifestCache.get(videoId)
  if (!force && cached && cached.expiresAt > Date.now() && cached.value.status === 'ready') {
    return cached.value
  }
  const value = await request.get<any, PlaybackManifest>(`/videos/${videoId}/playback-manifest`, {
    _skipErrorToast: true,
  } as any)
  if (value.status === 'ready' && value.manifest) {
    value.manifest = absolutizeManifestUrls(value.manifest)
    manifestCache.set(videoId, { value, expiresAt: Date.now() + 90 * 60 * 1000 })
  }
  return value
}

export async function waitForPlaybackManifest(videoId: number, timeoutMs = 20_000): Promise<PlaybackManifest> {
  const startedAt = Date.now()
  let manifest = await getPlaybackManifest(videoId)
  if (manifest.status === 'ready') return manifest
  await request.post(`/videos/${videoId}/prepare-playback`, null, { _skipErrorToast: true } as any)
  while (Date.now() - startedAt < timeoutMs) {
    await new Promise(resolve => window.setTimeout(resolve, 1500))
    manifest = await getPlaybackManifest(videoId, true)
    if (manifest.status === 'ready') return manifest
  }
  return manifest
}

function firstMediaUrls(manifest: string): string[] {
  const urls: string[] = []
  const init = manifest.match(/#EXT-X-MAP:URI="([^"]+)"/)?.[1]
  if (init) urls.push(init)
  const firstSegment = manifest
    .split(/\r?\n/)
    .map(line => line.trim())
    .find(line => line && !line.startsWith('#'))
  if (firstSegment) urls.push(firstSegment)
  return urls
}

async function warmVideo(videoId: number): Promise<void> {
  const connection = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection
  if (connection?.saveData) return
  const manifest = await getPlaybackManifest(videoId)
  if (manifest.status !== 'ready' || !manifest.manifest) {
    await request.post(`/videos/${videoId}/prepare-playback`, null, { _skipErrorToast: true } as any)
    return
  }
  for (const url of firstMediaUrls(absolutizeManifestUrls(manifest.manifest))) {
    const response = await fetch(url, { cache: 'force-cache' })
    if (!response.ok) break
    await response.arrayBuffer()
  }
}

async function runQueue(): Promise<void> {
  if (queueRunning) return
  queueRunning = true
  try {
    while (queuedPriorities.size) {
      const next = [...queuedPriorities.entries()].sort((a, b) => b[1] - a[1])[0]
      queuedPriorities.delete(next[0])
      try {
        await warmVideo(next[0])
      } catch {
        // Prefetch is opportunistic and must never block navigation or playback.
      }
    }
  } finally {
    queueRunning = false
  }
}

export function prefetchPlayback(videoId: number, priority = 0): void {
  const current = queuedPriorities.get(videoId)
  if (current === undefined || priority > current) queuedPriorities.set(videoId, priority)
  void runQueue()
}

export function clearPlaybackPrefetchQueue(): void {
  queuedPriorities.clear()
}
