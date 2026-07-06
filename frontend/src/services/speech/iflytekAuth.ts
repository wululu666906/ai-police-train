import request from '../../utils/request'

export type IFlytekStatusResponse = {
  configured: boolean
  app_id: string
  host: string
  path: string
  has_api_key: boolean
  has_api_secret: boolean
}

export const fetchIFlytekStatus = () =>
  request.get('/speech/iflytek/status', { _skipErrorToast: true } as any) as Promise<IFlytekStatusResponse>

export const fetchIFlytekWsUrl = () =>
  request.get('/speech/iflytek/ws-url', { _skipErrorToast: true } as any) as Promise<{ url: string }>
