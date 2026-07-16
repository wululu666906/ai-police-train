const AUTH_KEYS = ['token', 'role', 'username', 'user_id'] as const

let redirectingToLogin = false

export const getStoredRole = () => localStorage.getItem('role')

export const isLoggedIn = () => Boolean(localStorage.getItem('token'))

export const persistAuth = (payload: { access_token: string; username: string; role: string; user_id: number | string }) => {
  localStorage.setItem('token', payload.access_token)
  localStorage.setItem('username', payload.username)
  localStorage.setItem('role', payload.role)
  localStorage.setItem('user_id', String(payload.user_id))
}

export const clearAuth = () => {
  AUTH_KEYS.forEach((key) => localStorage.removeItem(key))
}

export const redirectToLogin = () => {
  if (redirectingToLogin) return
  redirectingToLogin = true
  clearAuth()
  window.location.href = '/login'
}

export const resetLoginRedirectState = () => {
  redirectingToLogin = false
}
