const KNOWN_DEV_NOISE = [
  /OpenGL error checking is disabled/,
  /Feedback manager requires a model with a single signature inference/,
  /Graph successfully started running/,
  /Graph finished closing successfully/,
  /TensorFlow Lite XNNPACK delegate for CPU/,
  /\bGL version:/,
  /Successfully destroyed WebGL context/,
  /inference_feedback_manager/,
  /\[ECharts\] The ticks may be not readable/,
]

function isKnownDevNoise(args: unknown[]): boolean {
  const text = args.map((item) => {
    if (typeof item === 'string') return item
    try {
      return String(item)
    } catch {
      return ''
    }
  }).join(' ')
  return KNOWN_DEV_NOISE.some((pattern) => pattern.test(text))
}

export function suppressKnownDevConsoleNoise() {
  ;(['log', 'info', 'warn', 'debug'] as const).forEach((method) => {
    const original = console[method].bind(console)
    console[method] = (...args: unknown[]) => {
      if (isKnownDevNoise(args)) return
      original(...args)
    }
  })
}
