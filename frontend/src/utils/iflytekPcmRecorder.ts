const TARGET_SAMPLE_RATE = 16000
const FRAME_BYTES = 1280
const FRAME_INTERVAL_MS = 40

const floatTo16BitPCM = (input: Float32Array) => {
  const buffer = new ArrayBuffer(input.length * 2)
  const view = new DataView(buffer)
  for (let index = 0; index < input.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, input[index]))
    view.setInt16(index * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true)
  }
  return new Uint8Array(buffer)
}

const downsampleBuffer = (buffer: Float32Array, inputRate: number, outputRate: number) => {
  if (outputRate === inputRate) return buffer
  const ratio = inputRate / outputRate
  const newLength = Math.round(buffer.length / ratio)
  const result = new Float32Array(newLength)
  let offsetResult = 0
  let offsetBuffer = 0
  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio)
    let accum = 0
    let count = 0
    for (let index = offsetBuffer; index < nextOffsetBuffer && index < buffer.length; index += 1) {
      accum += buffer[index]
      count += 1
    }
    result[offsetResult] = count ? accum / count : 0
    offsetResult += 1
    offsetBuffer = nextOffsetBuffer
  }
  return result
}

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

export class IFlytekPcmRecorder {
  private mediaStream: MediaStream | null = null
  private audioContext: AudioContext | null = null
  private sourceNode: MediaStreamAudioSourceNode | null = null
  private processorNode: ScriptProcessorNode | null = null
  private pendingPcm = new Uint8Array(0)
  private sendTimer: ReturnType<typeof setInterval> | null = null
  private hasSentFirstFrame = false
  private onFrame: PcmFrameHandler | null = null

  async start(onFrame: PcmFrameHandler) {
    this.onFrame = onFrame
    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    })

    this.audioContext = new AudioContext()
    const inputRate = this.audioContext.sampleRate
    this.sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream)
    this.processorNode = this.audioContext.createScriptProcessor(4096, 1, 1)

    this.processorNode.onaudioprocess = (event) => {
      const channelData = event.inputBuffer.getChannelData(0)
      const downsampled = downsampleBuffer(channelData, inputRate, TARGET_SAMPLE_RATE)
      const pcmChunk = floatTo16BitPCM(downsampled)
      this.enqueuePcm(pcmChunk)
    }

    this.sourceNode.connect(this.processorNode)
    this.processorNode.connect(this.audioContext.destination)

    this.sendTimer = setInterval(() => this.flushFrame(1), FRAME_INTERVAL_MS)
  }

  private enqueuePcm(chunk: Uint8Array) {
    const merged = new Uint8Array(this.pendingPcm.length + chunk.length)
    merged.set(this.pendingPcm, 0)
    merged.set(chunk, this.pendingPcm.length)
    this.pendingPcm = merged
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
  }

  stop() {
    if (this.sendTimer) {
      clearInterval(this.sendTimer)
      this.sendTimer = null
    }
    this.flushFrame(2)

    this.processorNode?.disconnect()
    this.sourceNode?.disconnect()
    this.processorNode = null
    this.sourceNode = null

    this.mediaStream?.getTracks().forEach((track) => track.stop())
    this.mediaStream = null

    if (this.audioContext) {
      void this.audioContext.close()
      this.audioContext = null
    }

    this.pendingPcm = new Uint8Array(0)
    this.hasSentFirstFrame = false
    this.onFrame = null
  }
}
