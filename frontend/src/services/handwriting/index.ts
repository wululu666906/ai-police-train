import type { HandwritingRecognizePayload, HandwritingRecognizeResult } from './types'

export type { HandwritingRecognizePayload, HandwritingRecognizeResult, HandwritingStroke, HandwritingStrokePoint } from './types'

/**
 * 手写识别占位：接入科大讯飞手写 OCR 后在此调用其 API。
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
