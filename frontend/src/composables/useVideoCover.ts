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
  const failedThumbnailUrls = ref<Record<number, string>>({})
  const loadingIds = new Set<number>()
  const objectUrls = new Set<string>()

  async function ensureVideoCover(video?: CoverableVideo | null, options: { force?: boolean } = {}) {
    const videoUrl = resolveMediaUrl(video?.video_url)
    const thumbnailUrl = resolveMediaUrl(video?.thumbnail_url)
    const thumbnailFailed = Boolean(video?.id && failedThumbnailUrls.value[video.id] === thumbnailUrl)

    if (!video?.id || !videoUrl) return
    if (thumbnailUrl && !thumbnailFailed && !options.force) return
    if (generatedCovers.value[video.id] || loadingIds.has(video.id)) return

    loadingIds.add(video.id)

    try {
      const coverUrl = await captureVideoFrame(videoUrl)
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
    const thumbnailUrl = resolveMediaUrl(video.thumbnail_url)
    const thumbnailFailed = Boolean(thumbnailUrl && failedThumbnailUrls.value[video.id] === thumbnailUrl)
    return generatedCovers.value[video.id] || (thumbnailFailed ? '' : thumbnailUrl) || ''
  }

  function markVideoCoverFailed(video?: CoverableVideo | null) {
    if (!video?.id) return
    const thumbnailUrl = resolveMediaUrl(video.thumbnail_url)
    if (thumbnailUrl) {
      failedThumbnailUrls.value = {
        ...failedThumbnailUrls.value,
        [video.id]: thumbnailUrl,
      }
    }
    void ensureVideoCover(video, { force: true })
  }

  function clearGeneratedCovers() {
    objectUrls.forEach((url) => URL.revokeObjectURL(url))
    objectUrls.clear()
    generatedCovers.value = {}
    failedThumbnailUrls.value = {}
    loadingIds.clear()
  }

  onUnmounted(() => {
    clearGeneratedCovers()
  })

  return {
    ensureVideoCover,
    ensureVideoCovers,
    getVideoCover,
    markVideoCoverFailed,
    clearGeneratedCovers,
  }
}

async function captureVideoFrame(videoUrl: string): Promise<string> {
  const frame = await captureBestVideoFrame(videoUrl, { revokeSourceUrl: false })
  return frame?.objectUrl || ''
}
