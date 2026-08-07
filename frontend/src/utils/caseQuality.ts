import { showConfirmDialog } from 'vant'

type QualityIssue = {
  id: string
  code?: string
  message?: string
}

const qualityDetail = (error: any) => {
  const detail = error?.response?.data?.detail
  return detail && typeof detail === 'object' ? detail : null
}

const issueMessage = (issues: QualityIssue[]) =>
  issues.map((item, index) => `${index + 1}. ${item.message || item.code || item.id}`).join('\n')

export const saveWithCaseQualityGate = async <T>(
  submit: (acknowledgements: string[]) => Promise<T>,
): Promise<T> => {
  try {
    return await submit([])
  } catch (error: any) {
    const detail = qualityDetail(error)
    const issues = Array.isArray(detail?.issues) ? detail.issues as QualityIssue[] : []
    if (detail?.code === 'CASE_QUALITY_BLOCKED') {
      await showConfirmDialog({
        title: '案件质量检查未通过',
        message: issueMessage(issues) || '存在阻断发布的问题，请修复后重试。',
        showCancelButton: false,
        confirmButtonText: '返回修改',
      })
      throw error
    }
    if (detail?.code !== 'CASE_QUALITY_ACK_REQUIRED' || !issues.length) throw error

    await showConfirmDialog({
      title: '确认发布风险',
      message: issueMessage(issues),
      confirmButtonText: '确认并继续',
      cancelButtonText: '返回修改',
    })
    return submit(issues.map(item => item.id).filter(Boolean))
  }
}
