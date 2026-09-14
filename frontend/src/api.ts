import type { AuthStatus, Comic, ComicUpdate, FailedComic, ImportResult, Me, PublicComic } from './types'

class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') detail = body.detail
    } catch {
      // ignore non-JSON error bodies
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

async function upload<T>(path: string, formData: FormData): Promise<T> {
  // No Content-Type header here: the browser must set its own multipart boundary.
  const res = await fetch(path, { method: 'POST', body: formData, credentials: 'include' })
  const data = await res.json()
  if (!res.ok) {
    const detail = typeof data?.detail === 'string' ? data.detail : JSON.stringify(data)
    throw new ApiError(res.status, detail)
  }
  return data as T
}

export { ApiError }

export interface ListParams {
  q?: string
  sort?: string
  order?: 'asc' | 'desc'
  confidence?: string
}

export function listComics(params: ListParams = {}): Promise<Comic[]> {
  const qs = new URLSearchParams()
  if (params.q) qs.set('q', params.q)
  if (params.sort) qs.set('sort', params.sort)
  if (params.order) qs.set('order', params.order)
  if (params.confidence) qs.set('confidence', params.confidence)
  const suffix = qs.toString() ? `?${qs.toString()}` : ''
  return request<Comic[]>(`/api/comics${suffix}`)
}

export function listFailed(): Promise<FailedComic[]> {
  return request<FailedComic[]>('/api/failed')
}

export function retryFailed(id: number): Promise<ImportResult> {
  return request<ImportResult>(`/api/failed/${id}/retry`, { method: 'POST' })
}

export function getComic(id: number): Promise<Comic> {
  return request<Comic>(`/api/comics/${id}`)
}

export function updateComic(id: number, patch: ComicUpdate): Promise<Comic> {
  return request<Comic>(`/api/comics/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export function deleteComic(id: number): Promise<void> {
  return request<void>(`/api/comics/${id}`, { method: 'DELETE' })
}

export function uploadComicImage(id: number, blob: Blob): Promise<Comic> {
  const formData = new FormData()
  formData.append('file', blob, 'cropped.jpg')
  return upload<Comic>(`/api/comics/${id}/image`, formData)
}

export function reclassifyComic(id: number): Promise<Comic> {
  return request<Comic>(`/api/comics/${id}/reclassify`, { method: 'POST' })
}

export function importComic(file: File): Promise<ImportResult> {
  const formData = new FormData()
  formData.append('file', file)
  return upload<ImportResult>('/api/import', formData)
}

export function listForSale(): Promise<PublicComic[]> {
  return request<PublicComic[]>('/api/public/for-sale')
}

export function getAuthStatus(): Promise<AuthStatus> {
  return request<AuthStatus>('/api/auth/status')
}

export function getMe(): Promise<Me> {
  return request<Me>('/api/auth/me')
}

export function setupAdmin(username: string, password: string): Promise<Me> {
  return request<Me>('/api/auth/setup', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function login(username: string, password: string): Promise<Me> {
  return request<Me>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function logout(): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>('/api/auth/logout', { method: 'POST' })
}
