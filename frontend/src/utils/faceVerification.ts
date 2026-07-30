export const FACE_VERIFY_RETRY_MS = 350
export const FACE_HEARTBEAT_RETRY_MS = 1500

export function localizeFaceMessage(
  value: unknown,
  fallback = '人脸验证失败，请调整后继续',
) {
  const text = String(value || '').trim()
  const lowered = text.toLowerCase()
  if (!text || /^\?+$/.test(text)) return fallback
  if (lowered.includes('request failed with status code') || lowered.includes('internal server error')) return '人脸识别服务处理失败，请稍后重试'
  if (lowered.includes('network error') || lowered.includes('failed to fetch')) return '人脸识别服务连接异常，请检查网络后重试'
  if (lowered.includes('no registered face profile')) return '当前账号尚未注册人脸档案'
  if (lowered.includes('no face detected') || lowered.includes('no face')) return '未检测到人脸，请正对摄像头'
  if (lowered.includes('multiple faces') || lowered.includes('multiple')) return '已选取画面中的主脸进行验证'
  if (lowered.includes('face mismatch') || lowered.includes('mismatch')) return '当前人脸与注册学员不一致'
  if (lowered.includes('invalid camera frame')) return '摄像头画面无效，请继续调整'
  if (lowered.includes('invalid image')) return '画面格式无效，请继续调整'
  if (lowered.includes('embedding extraction')) return '人脸特征提取失败，请调整光线后继续'
  if (lowered.includes('blur')) return '画面略有模糊，请调整摄像头或保持稳定'
  if (lowered.includes('insightface') || lowered.includes('model init') || lowered.includes('face engine unavailable')) {
    return '人脸识别模型暂不可用，请检查后端模型服务'
  }
  if (lowered === 'passed' || lowered.includes('人脸验证通过')) return '人脸验证通过'
  return /[a-z]/i.test(text) && !/[\u4e00-\u9fff]/.test(text) ? fallback : text
}
