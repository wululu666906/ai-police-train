const MIC_CONSTRAINTS: MediaStreamConstraints = {
  audio: {
    channelCount: 1,
    echoCancellation: true,
    noiseSuppression: true,
  },
}

let activeStream: MediaStream | null = null
let activeLeases = 0

export type MicrophoneLease = {
  stream: MediaStream
  release: () => void
}

const doRelease = () => {
  if (!activeStream) {
    activeLeases = 0
    return
  }
  activeLeases = Math.max(0, activeLeases - 1)
  if (activeLeases === 0) {
    activeStream.getTracks().forEach((track) => track.stop())
    activeStream = null
  }
}

export const acquireSharedMicrophone = async (): Promise<MediaStream> => {
  if (activeStream?.active) {
    activeLeases += 1
    return activeStream
  }

  activeStream = await navigator.mediaDevices.getUserMedia(MIC_CONSTRAINTS)
  activeLeases = 1
  return activeStream
}

export const acquireSharedMicrophoneLease = async (): Promise<MicrophoneLease> => {
  const stream = await acquireSharedMicrophone()
  let released = false
  return {
    stream,
    release: () => {
      if (released) return
      released = true
      doRelease()
    },
  }
}

export const releaseSharedMicrophone = () => {
  doRelease()
}

export const getSharedMicrophoneStream = () => activeStream
