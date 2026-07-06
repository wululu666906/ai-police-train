export interface HandwritingStrokePoint {
  x: number
  y: number
}

export interface HandwritingStroke {
  points: HandwritingStrokePoint[]
}

export interface HandwritingRecognizePayload {
  imageDataUrl: string
  strokes: HandwritingStroke[]
  width: number
  height: number
}

export interface HandwritingRecognizeResult {
  text: string
  provider: 'manual'
  /** 为 true 时表示尚未接入 OCR，需用户确认/编辑 */
  requiresManualConfirm?: boolean
}
