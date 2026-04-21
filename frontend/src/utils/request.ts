import axios from 'axios'
import { showToast } from 'vant'

const service = axios.create({
  baseURL: 'http://127.0.0.1:8000',
  timeout: 120000 // 统一将超时时间增加到 120 秒，以防大型模型分析耗时较长
})

// 请求拦截器：注入 Token
service.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器：统一错误处理
service.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    const msg = error.response?.data?.detail || '网络异常'
    showToast({ type: 'fail', message: msg })
    
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    
    return Promise.reject(error)
  }
)

export default service
