import { onUnmounted, ref } from 'vue'
import { resolveMediaUrl } from '../utils/media'
import { captureBestVideoFrame } from '../utils/videoFrame'

interface CoverableVideo {
  id: number
  video_url?: string
  thumbnail_url?: string
}

export function useVideoCover() {
  const generatedCovers = ref<Record<number, string>>({})
  const loadingIds = new Set<number>()
  const objectUrls = new Set<string>()

  async function ensureVideoCover(video?: CoverableVideo | null) {
    if (!video?.id || !video.video_url || video.thumbnail_url) return
    if (generatedCovers.value[video.id] || loadingIds.has(video.id)) return

    loadingIds.add(video.id)

    try {
      const coverUrl = await captureVideoFrame(resolveMediaUrl(video.video_url))
      if (coverUrl) {
        generatedCovers.value = {
          ...generatedCovers.value,
          [video.id]: coverUrl,
        }
        objectUrls.add(coverUrl)
      }
    } finally {
      loadingIds.delete(video.id)
    }
  }

  function ensureVideoCovers(videos: CoverableVideo[] = []) {
    videos.forEach((video) => {
      void ensureVideoCover(video)
    })
  }

  function getVideoCover(video?: CoverableVideo | null) {
    if (!video) return ''
    return resolveMediaUrl(video.thumbnail_url) || generatedCovers.value[video.id] || ''
  }

  function clearGeneratedCovers() {
    objectUrls.forEach((url) => URL.revokeObjectURL(url))
    objectUrls.clear()
    generatedCovers.value = {}
    loadingIds.clear()
  }

  onUnmounted(() => {
    clearGeneratedCovers()
  })

  return {
    ensureVideoCover,
    ensureVideoCovers,
    getVideoCover,
    clearGeneratedCovers,
  }
}

async function captureVideoFrame(videoUrl: string): Promise<string> {
  const frame = await captureBestVideoFrame(videoUrl, { revokeSourceUrl: false })
  return frame?.objectUrl || ''
}
