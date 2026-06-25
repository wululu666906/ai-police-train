import axios from 'axios'
import { showToast } from 'vant'
import { redirectToLogin } from './auth'

const getDevApiBaseUrl = () => {
  return 'http://127.0.0.1:8000'
}

const service = axios.create({
  baseURL: import.meta.env.VITE_API_URL || (import.meta.env.DEV ? getDevApiBaseUrl() : ''),
  timeout: 120000,
})

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
        msg = detail.map((d: any) => d.msg || String(d)).join('；') || '请求参数有误'
      } else {
        msg = String(detail || '网络异常，请稍后重试')
      }
      showToast({ type: 'fail', message: msg })
    }

    return Promise.reject(error)
  }
)

export default service
