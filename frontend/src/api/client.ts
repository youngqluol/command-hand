/**
 * 统一的 fetch 封装。全局只有这一处拼 URL、带 token、解析错误（AGENTS.md §5.1）。
 *
 * token 由本模块自己持有，避免「store 依赖 client、client 依赖 store」的循环引用。
 */

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '') || ''
const TOKEN_KEY = 'shellquest-session'

let token = localStorage.getItem(TOKEN_KEY) ?? ''

export function getToken(): string {
  return token
}

export function setToken(next: string): void {
  token = next
  if (next) localStorage.setItem(TOKEN_KEY, next)
  else localStorage.removeItem(TOKEN_KEY)
}

/** HTTP 层的业务错误（后端返回了 4xx/5xx）。网络不可达时抛出的是原始 TypeError。 */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** 只有网络层失败才算「后端不可达」；4xx/5xx 是业务错误，界面照常渲染。 */
export function isNetworkError(error: unknown): boolean {
  return !(error instanceof ApiError)
}

export function apiUrl(path: string): string {
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
}

export const apiPrefix = API_BASE || '/api'

type RequestOptions = {
  method?: string
  body?: unknown
  query?: Record<string, string | number | undefined | null>
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query } = options

  let url = apiUrl(path)
  if (query) {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === '') continue
      params.set(key, String(value))
    }
    const qs = params.toString()
    if (qs) url += `?${qs}`
  }

  const headers: Record<string, string> = {}
  if (token) headers['X-Session-Token'] = token
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const response = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (!response.ok) {
    let detail = `请求失败（HTTP ${response.status}）`
    try {
      const payload: unknown = await response.json()
      const raw = (payload as { detail?: unknown })?.detail
      if (typeof raw === 'string') detail = raw
    } catch {
      // 响应不是 JSON，保留状态码文案
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
