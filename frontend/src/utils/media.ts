import request from './request'

export const resolveMediaUrl = (value: unknown): string => {
  const url = String(value || '').trim()
  if (!url) return ''
  if (/^(https?:)?\/\//i.test(url) || url.startsWith('data:') || url.startsWith('blob:')) {
    return url
  }

  if (url.startsWith('/')) {
    const apiBase = String((request as any).defaults?.baseURL || '').replace(/\/$/, '')
    if (/^https?:\/\//i.test(apiBase)) {
      return `${apiBase}${url}`
    }
    return url
  }

  return url
}

