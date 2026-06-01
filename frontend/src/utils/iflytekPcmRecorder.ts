import { AudioHub } from '../services/speech/audioHub'

const FRAME_BYTES = 1280
const FRAME_INTERVAL_MS = 40

const bytesToBase64 = (bytes: Uint8Array) => {
  let binary = ''
  const chunkSize = 0x8000
  for (let index = 0; index < bytes.length; index += chunkSize) {
    const chunk = bytes.subarray(index, index + chunkSize)
    binary += String.fromCharCode(...chunk)
  }
  return btoa(binary)
}

export type PcmFrameHandler = (base64Audio: string, status: 0 | 1 | 2) => void
export type AudioLevelHandler = (level: number) => void
export type RecorderDebugHandler = (snapshot: { queueBytes: number; droppedFrames: number; sentFrames: number }) => void

export class IFlytekPcmRecorder {
  private mediaStream: MediaStream | null = null
  private readonly audioHub = new AudioHub()
  private pendingPcm = new Uint8Array(0)
  private sendTimer: ReturnType<typeof setInterval> | null = null
  private hasSentFirstFrame = false
  private onFrame: PcmFrameHandler | null = null
  private onLevel: AudioLevelHandler | null = null
  private onDebug: RecorderDebugHandler | null = null
  private ownsMediaStream = true
  private sentFrames = 0
  private droppedFrames = 0

  async start(
    onFrame: PcmFrameHandler,
    externalStream?: MediaStream,
    onLevel?: AudioLevelHandler,
    onDebug?: RecorderDebugHandler
  ) {
    this.onFrame = onFrame
    this.onLevel = onLevel ?? null
    this.onDebug = onDebug ?? null

    if (externalStream) {
      this.mediaStream = externalStream
      this.ownsMediaStream = false
    } else {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      })
      this.ownsMediaStream = true
    }

    const audioTrack = this.mediaStream.getAudioTracks()[0]
    if (!audioTrack || audioTrack.readyState !== 'live') {
      throw new Error('麦克风流不可用')
    }

    await this.audioHub.start(
      this.mediaStream,
      {
        onPcmChunk: (chunk) => this.enqueuePcm(chunk),
        onLevel: (level) => this.onLevel?.(level),
      },
      {
        targetSampleRate: 16000,
      }
    )

    this.sendTimer = setInterval(() => this.flushFrame(1), FRAME_INTERVAL_MS)
    this.sentFrames = 0
    this.droppedFrames = 0
  }

  private enqueuePcm(chunk: Uint8Array) {
    if (this.pendingPcm.length > FRAME_BYTES * 40) {
      this.pendingPcm = this.pendingPcm.slice(Math.max(0, this.pendingPcm.length - FRAME_BYTES * 20))
      this.droppedFrames += 1
    }
    const merged = new Uint8Array(this.pendingPcm.length + chunk.length)
    merged.set(this.pendingPcm, 0)
    merged.set(chunk, this.pendingPcm.length)
    this.pendingPcm = merged
    this.emitDebug()
  }

  private flushFrame(status: 0 | 1 | 2) {
    if (!this.onFrame) return

    if (status === 2) {
      if (this.pendingPcm.length) {
        this.onFrame(bytesToBase64(this.pendingPcm), 2)
        this.pendingPcm = new Uint8Array(0)
      } else {
        this.onFrame('', 2)
      }
      return
    }

    if (!this.pendingPcm.length) return

    const frameStatus: 0 | 1 = this.hasSentFirstFrame ? 1 : 0
    const bytes = this.pendingPcm.slice(0, FRAME_BYTES)
    this.pendingPcm = this.pendingPcm.slice(bytes.length)
    this.onFrame(bytesToBase64(bytes), frameStatus)
    this.hasSentFirstFrame = true
    this.sentFrames += 1
    this.emitDebug()
  }

  private emitDebug() {
    this.onDebug?.({
      queueBytes: this.pendingPcm.length,
      droppedFrames: this.droppedFrames,
      sentFrames: this.sentFrames,
    })
  }

  stop() {
    if (this.sendTimer) {
      clearInterval(this.sendTimer)
      this.sendTimer = null
    }
    this.flushFrame(2)

    this.audioHub.stop()

    if (this.ownsMediaStream) {
      this.mediaStream?.getTracks().forEach((track) => track.stop())
    }
    this.mediaStream = null
    this.ownsMediaStream = true

    this.pendingPcm = new Uint8Array(0)
    this.hasSentFirstFrame = false
    this.sentFrames = 0
    this.droppedFrames = 0
    this.onFrame = null
    this.onLevel = null
    this.onDebug = null
  }
}
