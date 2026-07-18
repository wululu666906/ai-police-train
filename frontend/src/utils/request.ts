import axios from 'axios'
import { showToast } from 'vant'
import { redirectToLogin } from './auth'

const getDevApiBaseUrl = () => {
  return 'http://127.0.0.1:8000'
}

const service = axios.create({
  baseURL: import.meta.env.VITE_API_URL || (import.meta.env.DEV ? getDevApiBaseUrl() : '/api'),
  timeout: 120000,
})

export const toChineseErrorMessage = (value: unknown, fallback = '服务暂时不可用，请稍后重试') => {
  const text = String(value || '').trim()
  const lowered = text.toLowerCase()
  if (!text) return fallback
  if (lowered.includes('request failed with status code') || lowered.includes('internal server error')) {
    return '服务器处理请求失败，请稍后重试'
  }
  if (lowered.includes('network error') || lowered.includes('failed to fetch')) return '网络连接异常，请检查网络后重试'
  if (lowered.includes('timeout')) return '请求超时，请稍后重试'
  if (lowered.includes('not found')) return '请求的服务不存在或暂不可用'
  // Do not surface untranslated framework, dependency, or proxy messages.
  if (/[a-z]/i.test(text) && !/[\u4e00-\u9fff]/.test(text)) return fallback
  return text
}

service.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

service.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const requestUrl = String(error.config?.url || '')
    const isLoginRequest = requestUrl.includes('/auth/token')

    if (error.response?.status === 401 && !isLoginRequest) {
      showToast({ type: 'fail', message: '登录状态已失效，请重新登录' })
      redirectToLogin()
      return Promise.reject(error)
    }

    if (!error.config?._skipErrorToast) {
      const detail = error.response?.data?.detail
      let msg: string
      if (Array.isArray(detail)) {
        // FastAPI 422 validation error：detail 是 [{loc, msg, type}] 数组
        msg = detail.map((d: any) => toChineseErrorMessage(d.msg || String(d), '请求参数有误')).join('；') || '请求参数有误'
      } else {
        msg = toChineseErrorMessage(
          detail,
          error.response?.status >= 500 ? '服务器处理请求失败，请稍后重试' : '网络异常，请稍后重试',
        )
      }
      showToast({ type: 'fail', message: msg })
    }

    return Promise.reject(error)
  }
)

export default service
