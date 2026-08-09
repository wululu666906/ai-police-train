import { onUnmounted, ref, type Ref } from 'vue'
import Hls, { ErrorTypes, Events } from 'hls.js'
import { waitForPlaybackManifest } from '../services/videoPlayback'
import { resolveMediaUrl } from '../utils/media'

export type PlaybackState = 'idle' | 'preparing' | 'ready' | 'playing' | 'buffering' | 'fallback' | 'error'

export function useSegmentedVideoPlayback(videoRef: Ref<HTMLVideoElement | null>) {
  const state = ref<PlaybackState>('idle')
  const usingHls = ref(false)
  let hls: Hls | null = null
  let manifestBlobUrl = ''
  let generation = 0

  function revokeManifestUrl() {
    if (!manifestBlobUrl) return
    URL.revokeObjectURL(manifestBlobUrl)
    manifestBlobUrl = ''
  }

  function release(clearSource = false) {
    generation += 1
    hls?.destroy()
    hls = null
    revokeManifestUrl()
    usingHls.value = false
    const element = videoRef.value
    if (clearSource && element) {
      element.pause()
      element.removeAttribute('src')
      element.load()
    }
    state.value = 'idle'
  }

  function useFallback(fallbackUrl: string) {
    hls?.destroy()
    hls = null
    revokeManifestUrl()
    usingHls.value = false
    const element = videoRef.value
    if (!element || !fallbackUrl) {
      state.value = 'error'
      return
    }
    element.src = resolveMediaUrl(fallbackUrl)
    element.load()
    state.value = 'fallback'
  }

  function resolveManifestUrls(manifest: string): string {
    return manifest
      .split(/\r?\n/)
      .map((line) => {
        const stripped = line.trim()
        if (!stripped) return line
        if (stripped.startsWith('#EXT-X-MAP')) {
          return line.replace(/URI="([^"]+)"/, (_match, url) => `URI="${resolveMediaUrl(url)}"`)
        }
        if (stripped.startsWith('#')) return line
        return resolveMediaUrl(stripped)
      })
      .join('\n')
  }

  async function attach(videoId: number, fallbackUrl: string): Promise<void> {
    release()
    const currentGeneration = generation
    state.value = 'preparing'
    try {
      const playback = await waitForPlaybackManifest(videoId)
      if (currentGeneration !== generation) return
      const element = videoRef.value
      if (!element || playback.status !== 'ready' || !playback.manifest) {
        useFallback(playback.fallback_url || fallbackUrl)
        return
      }

      manifestBlobUrl = URL.createObjectURL(new Blob([resolveManifestUrls(playback.manifest)], {
        type: 'application/vnd.apple.mpegurl',
      }))
      if (Hls.isSupported()) {
        hls = new Hls({
          startFragPrefetch: true,
          maxBufferLength: 60,
          maxMaxBufferLength: 120,
          maxBufferSize: 120 * 1024 * 1024,
          backBufferLength: 30,
          manifestLoadingMaxRetry: 2,
          fragLoadingMaxRetry: 4,
        })
        hls.on(Events.MEDIA_ATTACHED, () => hls?.loadSource(manifestBlobUrl))
        hls.on(Events.MANIFEST_PARSED, () => {
          state.value = 'ready'
          usingHls.value = true
        })
        hls.on(Events.ERROR, (_event, data) => {
          if (!data.fatal) return
          if (data.type === ErrorTypes.MEDIA_ERROR) {
            hls?.recoverMediaError()
            return
          }
          useFallback(playback.fallback_url || fallbackUrl)
        })
        hls.attachMedia(element)
      } else if (element.canPlayType('application/vnd.apple.mpegurl')) {
        element.src = manifestBlobUrl
        element.load()
        usingHls.value = true
        state.value = 'ready'
      } else {
        useFallback(playback.fallback_url || fallbackUrl)
      }
    } catch {
      if (currentGeneration === generation) useFallback(fallbackUrl)
    }
  }

  function markPlaying() {
    state.value = 'playing'
  }

  function markWaiting() {
    if (state.value !== 'preparing') state.value = 'buffering'
  }

  onUnmounted(() => release(true))

  return { state, usingHls, attach, release, markPlaying, markWaiting }
}
