import type { HandwritingRecognizePayload, HandwritingRecognizeResult } from './types'

export type { HandwritingRecognizePayload, HandwritingRecognizeResult, HandwritingStroke, HandwritingStrokePoint } from './types'

/**
 * 手写识别占位：当前保留人工确认流程，后续可接入新的 OCR 服务。
 */
export const recognizeHandwriting = async (
  _payload: HandwritingRecognizePayload
): Promise<HandwritingRecognizeResult> => {
  return {
    text: '',
    provider: 'manual',
    requiresManualConfirm: true,
  }
}
