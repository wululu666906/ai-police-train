export type NotificationRecord = {
  id: number | string
  title?: string
  content?: string
  created_at?: string
  source_label?: string
  source_name?: string
  source_type?: string
  category?: string
  notification_type?: string
  severity?: string
  session_id?: number
  video_id?: number
  class_id?: number
  failure_count?: number
}

export const formatNotificationDateTime = (value?: string) => {
  if (!value) return '未知时间'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = (num: number) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export const notificationTypeLabel = (item: NotificationRecord) => {
  if (item.notification_type === 'training_anomaly') return '训练异常'
  if (item.notification_type === 'announcement') return '班级通知'
  return '系统通知'
}

export const notificationSourceLabel = (item?: NotificationRecord | null) => {
  if (!item) return '系统'
  const sourceName = String(item.source_label || item.source_name || '').trim()
  if (sourceName) return sourceName
  if (item.source_type === 'system' || item.category === 'system') return '系统通知'
  return '班级通知'
}

export const firstNotificationLine = (content?: string) => {
  const lines = String(content || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
  return lines[0] || '暂无正文'
}
