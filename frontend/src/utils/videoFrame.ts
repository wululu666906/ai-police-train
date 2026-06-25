export interface CapturedVideoFrame {
  blob: Blob
  objectUrl: string
  capturedAt: number
  width: number
  height: number
}

export async function captureBestVideoFrame(
  source: File | string,
  options: {
    durationHint?: number | null
    revokeSourceUrl?: boolean
  } = {},
): Promise<CapturedVideoFrame | null> {
  const sourceUrl = typeof source === 'string' ? source : URL.createObjectURL(source)
  const shouldRevokeSourceUrl = typeof source !== 'string' || options.revokeSourceUrl
  const video = document.createElement('video')
  video.preload = 'auto'
  video.muted = true
  video.playsInline = true
  video.crossOrigin = 'anonymous'
  video.src = sourceUrl

  try {
    await waitForFirstReady(video)

    const duration = normalizeDuration(options.durationHint ?? video.duration)
    const captureCandidates = buildCandidateTimes(duration)

    for (const candidate of captureCandidates) {
      const frame = await tryCaptureAt(video, candidate)
      if (frame) return frame
    }

    const fallbackFrame = await captureCurrentFrame(video)
    return fallbackFrame
  } catch {
    return null
  } finally {
    video.pause()
    video.removeAttribute('src')
    video.load()
    video.remove()
    if (shouldRevokeSourceUrl) {
      URL.revokeObjectURL(sourceUrl)
    }
  }
}

async function waitForFirstReady(video: HTMLVideoElement) {
  if (video.readyState >= 1) return
  await waitForVideoEvent(video, ['loadeddata', 'loadedmetadata', 'canplay'], 10000)
}

async function tryCaptureAt(video: HTMLVideoElement, seconds: number) {
  if (Number.isFinite(seconds) && seconds >= 0) {
    try {
      video.currentTime = seconds
      await waitForVideoEvent(video, ['seeked', 'canplay', 'timeupdate'], 5000)
    } catch {
      return null
    }
  }
  return captureCurrentFrame(video)
}

async function captureCurrentFrame(video: HTMLVideoElement): Promise<CapturedVideoFrame | null> {
  const width = video.videoWidth || 0
  const height = video.videoHeight || 0
  if (!width || !height) return null

  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) return null
  ctx.drawImage(video, 0, 0, width, height)

  if (isLikelyBlackFrame(ctx, width, height)) {
    return null
  }

  const blob = await new Promise<Blob | null>((resolve) => {
    canvas.toBlob((result) => resolve(result), 'image/jpeg', 0.86)
  })
  if (!blob) return null

  return {
    blob,
    objectUrl: URL.createObjectURL(blob),
    capturedAt: Number.isFinite(video.currentTime) ? video.currentTime : 0,
    width,
    height,
  }
}

function isLikelyBlackFrame(ctx: CanvasRenderingContext2D, width: number, height: number) {
  const sampleWidth = Math.max(12, Math.min(64, Math.floor(width / 10)))
  const sampleHeight = Math.max(12, Math.min(64, Math.floor(height / 10)))
  const offsetX = Math.max(0, Math.floor((width - sampleWidth) / 2))
  const offsetY = Math.max(0, Math.floor((height - sampleHeight) / 2))
  const image = ctx.getImageData(offsetX, offsetY, sampleWidth, sampleHeight).data

  let totalLuma = 0
  let brightPixels = 0
  const pixelCount = Math.max(image.length / 4, 1)
  for (let i = 0; i < image.length; i += 4) {
    const r = image[i]
    const g = image[i + 1]
    const b = image[i + 2]
    const luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    totalLuma += luma
    if (luma > 24) brightPixels += 1
  }

  const avgLuma = totalLuma / pixelCount
  const brightRatio = brightPixels / pixelCount
  return avgLuma < 18 && brightRatio < 0.08
}

function buildCandidateTimes(duration: number) {
  if (!duration || duration <= 0) {
    return [0, 0.2, 0.4, 0.8, 1.2]
  }

  const rawCandidates = [
    duration * 0.08,
    duration * 0.14,
    duration * 0.22,
    duration * 0.33,
    duration * 0.5,
  ]
  const maxTime = Math.max(duration - 0.25, 0)
  return Array.from(
    new Set(
      rawCandidates
        .map((item) => Math.max(0, Math.min(maxTime, Number(item.toFixed(2)))))
        .filter((item) => Number.isFinite(item)),
    ),
  )
}

function normalizeDuration(duration?: number | null) {
  const value = Number(duration || 0)
  return Number.isFinite(value) && value > 0 ? value : 0
}

function waitForVideoEvent(
  video: HTMLVideoElement,
  eventNames: Array<'loadedmetadata' | 'loadeddata' | 'canplay' | 'seeked' | 'timeupdate'>,
  timeoutMs: number,
) {
  return new Promise<void>((resolve, reject) => {
    let settled = false
    let timer = 0

    const cleanup = () => {
      eventNames.forEach((name) => video.removeEventListener(name, onSuccess))
      video.removeEventListener('error', onError)
      window.clearTimeout(timer)
    }

    const finish = (handler: () => void) => {
      if (settled) return
      settled = true
      cleanup()
      handler()
    }

    const onSuccess = () => finish(resolve)
    const onError = () => finish(() => reject(new Error('video event failed')))

    timer = window.setTimeout(() => finish(() => reject(new Error('video event timeout'))), timeoutMs)
    eventNames.forEach((name) => video.addEventListener(name, onSuccess, { once: true }))
    video.addEventListener('error', onError, { once: true })
  })
}
