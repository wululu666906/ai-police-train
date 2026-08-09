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
      if (/^\/(static|object-storage|avatars)\//.test(url)) {
        try {
          const parsed = new URL(apiBase)
          return `${parsed.origin}${url}`
        } catch {
          return url
        }
      }
      return `${apiBase}${url}`
    }
    return url
  }

  return url
}

