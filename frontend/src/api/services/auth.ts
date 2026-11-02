import type { AuthService, AuthUser } from '../contracts'
import { request } from '../http'

export const authApi: AuthService = {
  login: (username, password) =>
    request<AuthUser>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
  me: () => request<AuthUser>('/auth/me'),
  changePassword: (oldPassword, newPassword) =>
    request<{ ok: boolean; reLogin: boolean }>('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ oldPassword, newPassword }),
    }),
}
