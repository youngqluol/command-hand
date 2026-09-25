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

/**
 * 会话失效（401）的全局回调，由 `stores/session.ts` 在模块加载时注册。
 *
 * 放在这里是因为只有 `request()` 能看到响应状态；而 client 不能反过来 import store
 * （见文件顶部：会造成循环引用）。没有注册回调时静默跳过。
 */
let onSessionExpired: (() => void) | null = null

export function setSessionExpiredHandler(handler: (() => void) | null): void {
  onSessionExpired = handler
}

/**
 * 登录 / 注册接口自己用 401 表示「用户名或密码错误」，那是**业务错误**而不是会话失效，
 * 必须排除，否则用户在登录页输错密码会被当成「登录已过期」。
 */
function isAuthCredentialEndpoint(path: string): boolean {
  return path.startsWith('/api/v1/auth/login') || path.startsWith('/api/v1/auth/register')
}

/**
 * FastAPI / Pydantic 校验失败时 `detail` 是数组，形如
 * `[{ loc: ['body', 'username'], msg: 'String should have at least 3 characters', type: 'string_too_short' }]`。
 * 原样抛出去，界面只会显示「请求失败（HTTP 422）」，用户完全不知道是哪个字段错了。
 *
 * 这里**不翻译 `msg`**：后端自己写的中文 `detail` 走字符串分支，能走到这里的都是
 * Pydantic 兜底拦下的（说明前端漏了一条约束），保留英文原文更利于定位问题。
 * 最多列 3 项，其余只报数量，避免刷屏。
 */
function describeValidationError(entries: unknown[]): string {
  const parts = entries.slice(0, 3).map((entry) => {
    const item = entry as { loc?: unknown; msg?: unknown }
    const message = typeof item.msg === 'string' ? item.msg : '取值不合法'
    // loc 的首段是来源（body / query / path），对使用者没有意义，去掉。
    const field = Array.isArray(item.loc)
      ? item.loc.filter((part) => part !== 'body' && part !== 'query').join('.')
      : ''
    return field ? `${field}：${message}` : message
  })
  const rest = entries.length > 3 ? `（另有 ${entries.length - 3} 项）` : ''
  return `请求参数不合法 —— ${parts.join('；')}${rest}`
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
      else if (Array.isArray(raw)) detail = describeValidationError(raw)
    } catch {
      // 响应不是 JSON，保留状态码文案
    }
    // 带着 token 发请求却拿到 401 → 会话在服务端已失效（被清库、用户被删、token 被回收）。
    // 必须确认「确实发过 token」才判定，否则游客的 401 会误报成登录过期。
    if (response.status === 401 && token && !isAuthCredentialEndpoint(path)) onSessionExpired?.()
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}
