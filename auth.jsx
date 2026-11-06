import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, tokenStore, setUnauthorizedHandler } from '@/lib/api'
import i18n from '@/lib/i18n'
import { ROLES } from '@/lib/constants'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(!!tokenStore.get())
  const [notice, setNotice] = useState(null) // e.g. 'sessionExpired', shown on the login page

  const logout = useCallback((reason = null) => {
    tokenStore.clear()
    setUser(null)
    setNotice(reason)
  }, [])

  // Any 401 from the API means the session is over.
  useEffect(() => {
    setUnauthorizedHandler(() => logout('sessionExpired'))
    return () => setUnauthorizedHandler(null)
  }, [logout])

  // On first load, trust the server for who the user is and what role they have now.
  useEffect(() => {
    if (!tokenStore.get()) return
    api('/api/users/me')
      .then((res) => setUser(res.user))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  // The UI language follows the user's saved preference.
  useEffect(() => {
    if (user?.preferred_language) i18n.changeLanguage(user.preferred_language)
  }, [user?.preferred_language])

  const login = useCallback(async (gmail, password) => {
    const data = await api('/api/auth/login', { method: 'POST', body: { gmail, password }, auth: false })
    tokenStore.set(data.access_token)
    setNotice(null)
    setUser(data.user)
    return data.user
  }, [])

  const register = useCallback(
    (fields) => api('/api/auth/register', { method: 'POST', body: fields, auth: false }),
    [],
  )

  const refreshUser = useCallback(async () => {
    const res = await api('/api/users/me')
    setUser(res.user)
    return res.user
  }, [])

  const value = useMemo(
    () => ({
      user,
      loading,
      notice,
      login,
      register,
      logout,
      refreshUser,
      isStaff: user?.role === ROLES.COMMITTEE || user?.role === ROLES.SECRETARY,
      isSecretary: user?.role === ROLES.SECRETARY,
    }),
    [user, loading, notice, login, register, logout, refreshUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
