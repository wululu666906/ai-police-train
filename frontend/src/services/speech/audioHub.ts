type AudioHubOptions = {
  targetSampleRate?: number
  processorBufferSize?: number
  analyserFftSize?: number
  analyserSmoothing?: number
}

type AudioHubCallbacks = {
  onPcmChunk?: (chunk: Uint8Array) => void
  onLevel?: (level: number) => void
}

const DEFAULT_TARGET_SAMPLE_RATE = 16000
const DEFAULT_PROCESSOR_BUFFER_SIZE = 4096
const DEFAULT_ANALYSER_FFT_SIZE = 2048
const DEFAULT_ANALYSER_SMOOTHING = 0.8

const floatTo16BitPCM = (input: Float32Array) => {
  const buffer = new ArrayBuffer(input.length * 2)
  const view = new DataView(buffer)
  for (let i = 0; i < input.length; i += 1) {
    const sample = Math.max(-1, Math.min(1, input[i]))
    view.setInt16(i * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true)
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

const rmsFromTimeDomain = (samples: ArrayLike<number>, isByteDomain = false) => {
  let sumSquares = 0
  for (let i = 0; i < samples.length; i += 1) {
    const raw = samples[i] ?? 0
    const v = isByteDomain ? (raw - 128) / 128 : raw
    sumSquares += v * v
  }
  const rms = Math.sqrt(sumSquares / Math.max(1, samples.length))
  return Math.min(1, Math.pow(rms * 8, 0.75))
}

export class AudioHub {
  private mediaStream: MediaStream | null = null
  private ownsMediaStream = true
  private audioContext: AudioContext | null = null
  private sourceNode: MediaStreamAudioSourceNode | null = null
  private processorNode: ScriptProcessorNode | null = null
  private analyserNode: AnalyserNode | null = null
  private silentGain: GainNode | null = null
  private onPcmChunk: ((chunk: Uint8Array) => void) | null = null
  private onLevel: ((level: number) => void) | null = null
  private levelRafId = 0
  private targetSampleRate = DEFAULT_TARGET_SAMPLE_RATE

  async start(stream: MediaStream | undefined, callbacks: AudioHubCallbacks, options: AudioHubOptions = {}) {
    this.onPcmChunk = callbacks.onPcmChunk ?? null
    this.onLevel = callbacks.onLevel ?? null
    this.targetSampleRate = options.targetSampleRate ?? DEFAULT_TARGET_SAMPLE_RATE

    if (stream) {
      this.mediaStream = stream
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

    this.audioContext = new AudioContext()
    await this.audioContext.resume()

    this.sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream)

    this.processorNode = this.audioContext.createScriptProcessor(
      options.processorBufferSize ?? DEFAULT_PROCESSOR_BUFFER_SIZE,
      1,
      1
    )
    this.processorNode.onaudioprocess = (event) => {
      const channel = event.inputBuffer.getChannelData(0)
      const downsampled = downsampleBuffer(channel, this.audioContext?.sampleRate || 48000, this.targetSampleRate)
      const pcmChunk = floatTo16BitPCM(downsampled)
      this.onPcmChunk?.(pcmChunk)
    }

    this.analyserNode = this.audioContext.createAnalyser()
    this.analyserNode.fftSize = options.analyserFftSize ?? DEFAULT_ANALYSER_FFT_SIZE
    this.analyserNode.smoothingTimeConstant = options.analyserSmoothing ?? DEFAULT_ANALYSER_SMOOTHING

    this.silentGain = this.audioContext.createGain()
    this.silentGain.gain.value = 0

    this.sourceNode.connect(this.processorNode)
    this.sourceNode.connect(this.analyserNode)
    this.processorNode.connect(this.silentGain)
    this.silentGain.connect(this.audioContext.destination)

    this.startLevelLoop()
  }

  private startLevelLoop() {
    if (!this.analyserNode) return
    const tick = () => {
      if (!this.analyserNode) return
      const analyserBuffer = new Uint8Array(this.analyserNode.fftSize)
      this.analyserNode.getByteTimeDomainData(analyserBuffer)
      this.onLevel?.(rmsFromTimeDomain(analyserBuffer, true))
      this.levelRafId = window.requestAnimationFrame(tick)
    }
    this.levelRafId = window.requestAnimationFrame(tick)
  }

  stop() {
    if (this.levelRafId) {
      window.cancelAnimationFrame(this.levelRafId)
      this.levelRafId = 0
    }

    if (this.processorNode) {
      this.processorNode.onaudioprocess = null
      this.processorNode.disconnect()
      this.processorNode = null
    }
    this.sourceNode?.disconnect()
    this.sourceNode = null
    this.analyserNode?.disconnect()
    this.analyserNode = null
    this.silentGain?.disconnect()
    this.silentGain = null

    if (this.ownsMediaStream) {
      this.mediaStream?.getTracks().forEach((track) => track.stop())
    }
    this.mediaStream = null
    this.ownsMediaStream = true

    if (this.audioContext) {
      void this.audioContext.close()
      this.audioContext = null
    }

    this.onPcmChunk = null
    this.onLevel = null
  }
}
