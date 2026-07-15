export interface SelfieCaptureOptions {
  size?: number
  jpegQuality?: number
  mirror?: boolean
  zoom?: number
  focusY?: number
  /** preview = match circular UI crop; full = entire frame (better for backend matching) */
  mode?: 'preview' | 'full'
}

/** Capture a selfie frame aligned with mirrored/zoomed circular camera previews. */
export function captureSelfieFrame(
  video: HTMLVideoElement,
  canvas: HTMLCanvasElement,
  options: SelfieCaptureOptions = {},
) {
  const {
    size = 640,
    jpegQuality = 0.9,
    mirror = true,
    zoom = 1.45,
    focusY = 0.28,
    mode = 'preview',
  } = options

  if (!video.videoWidth || !video.videoHeight) return null

  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  if (!ctx) return null

  const videoWidth = video.videoWidth
  const videoHeight = video.videoHeight

  let drawWidth: number
  let drawHeight: number
  let offsetX: number
  let offsetY: number

  if (mode === 'full') {
    const fitScale = Math.min(size / videoWidth, size / videoHeight)
    drawWidth = videoWidth * fitScale
    drawHeight = videoHeight * fitScale
    offsetX = (size - drawWidth) / 2
    offsetY = (size - drawHeight) / 2
  } else {
    const coverScale = Math.max(size / videoWidth, size / videoHeight) * zoom
    drawWidth = videoWidth * coverScale
    drawHeight = videoHeight * coverScale
    offsetX = (size - drawWidth) / 2
    offsetY = (size - drawHeight) * focusY
  }

  ctx.save()
  if (mirror) {
    ctx.translate(size, 0)
    ctx.scale(-1, 1)
  }
  ctx.drawImage(video, offsetX, offsetY, drawWidth, drawHeight)
  ctx.restore()

  return canvas.toDataURL('image/jpeg', jpegQuality)
}
