const BASE = (import.meta.env.VITE_API_URL || 'http://localhost:5000').replace(/\/$/, '')
const TOKEN_KEY = 'grievdesk_token'

export class ApiError extends Error {
  constructor(status, code, message, data) {
    super(message)
    this.status = status
    this.code = code
    this.data = data
  }
}

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

let onUnauthorized = null
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

/**
 * One place for every backend call.
 * - Sends the JWT as "Authorization: Bearer ...".
 * - Your routes fail with { error, message }; flask-jwt-extended fails with { msg } (401/422).
 *   Both become an ApiError with a `code` the UI can translate.
 * - A dead, expired or deactivated session triggers the unauthorized handler (log out).
 */
export async function api(path, { method = 'GET', body, form, auth = true, signal } = {}) {
  const headers = {}
  const token = tokenStore.get()
  if (auth && token) headers.Authorization = `Bearer ${token}`

  let payload
  if (form) {
    payload = form // multipart: the browser sets the boundary header itself
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  let res
  try {
    res = await fetch(BASE + path, { method, headers, body: payload, signal })
  } catch (e) {
    if (e.name === 'AbortError') throw e
    throw new ApiError(0, 'network', 'Cannot reach the server.', null)
  }

  let data = null
  const text = await res.text()
  if (text) {
    try { data = JSON.parse(text) } catch { data = { raw: text } }
  }

  if (!res.ok) {
    const jwtProblem = auth && data?.msg && !data?.error && (res.status === 401 || res.status === 422)
    const inactive = auth && res.status === 401 && data?.error === 'unauthorized'
    if ((jwtProblem || inactive) && onUnauthorized) onUnauthorized()
    throw new ApiError(
      res.status,
      data?.error || (data?.msg ? 'token_error' : 'http_error'),
      data?.message || data?.msg || `Request failed (${res.status})`,
      data,
    )
  }
  return data
}

export const get = (path, opts) => api(path, { ...opts, method: 'GET' })
export const post = (path, body, opts) => api(path, { ...opts, method: 'POST', body })
export const put = (path, body, opts) => api(path, { ...opts, method: 'PUT', body })
export const patch = (path, body, opts) => api(path, { ...opts, method: 'PATCH', body })
export const del = (path, opts) => api(path, { ...opts, method: 'DELETE' })
