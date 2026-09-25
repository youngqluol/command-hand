/**
 * 会话与用户数据。模块级 `ref` 单例，不引 Pinia（AGENTS.md §5.3）。
 *
 * 所有写操作都吞掉异常并降级，界面永远不白屏（AGENTS.md §5.4）：
 * - 网络不可达 → `apiUnavailable = true`，顶部显示告警条
 * - 业务错误（如 401）→ 清掉本地 token，回到未登录态
 * - 会话在服务端失效（401）→ 额外置 `sessionExpired`，顶部提示「登录已过期 + 重新登录」
 *   （此前是静默清掉，用户只会莫名其妙发现自己变游客了，见 §5.4）
 */

import { computed, ref } from 'vue'

import { ApiError, getToken, isNetworkError, request, setSessionExpiredHandler, setToken } from '../api/client'
import type {
  AuthResponse,
  CheckInResponse,
  CheckInStatus,
  SkillTree,
  TrainingMode,
  UserProgress,
  UserSummary,
} from '../types'

/** 未登录 / 后端不可用时的占位用户。等级常量与后端 `schemas.py` 保持一致。 */
export const DEFAULT_USER: UserSummary = {
  id: 0,
  username: 'guest',
  xp: 0,
  streak_days: 0,
  created_at: '',
  level: 1,
  level_title: '初级探索者',
  level_xp_earned: 0,
  level_xp_total: 1000,
  training_mode: 'camp',
}

const user = ref<UserSummary | null>(null)
const checkin = ref<CheckInStatus | null>(null)
const skills = ref<SkillTree | null>(null)
const progress = ref<UserProgress | null>(null)
const apiUnavailable = ref(false)
const restoring = ref(true)
/** 会话在服务端失效（带着 token 却拿到 401）时置位，用于提示用户重新登录。 */
const sessionExpired = ref(false)

export const currentUser = computed(() => user.value)
export const displayUser = computed(() => user.value ?? DEFAULT_USER)
export const checkinStatus = computed(() => checkin.value)
export const skillTree = computed(() => skills.value)
export const userProgress = computed(() => progress.value)
export const apiUnavailableState = computed(() => apiUnavailable.value)
export const sessionExpiredState = computed(() => sessionExpired.value)
export const isRestoring = computed(() => restoring.value)
export const isLoggedIn = computed(() => user.value !== null)
/** 当前训练路径。未登录时恒为 `camp`，与后端默认值一致。 */
export const trainingMode = computed<TrainingMode>(() => user.value?.training_mode ?? 'camp')

export function setUser(next: UserSummary | null): void {
  user.value = next
  if (next) {
    apiUnavailable.value = false
    // 拿到有效用户即视为会话正常，「登录已过期」提示该收了。
    sessionExpired.value = false
  }
}

/** 清空所有用户态数据。登出与会话失效共用，避免两处漏清某个字段。 */
function clearUserState(): void {
  setToken('')
  user.value = null
  checkin.value = null
  skills.value = null
  progress.value = null
}

/**
 * 服务端判定会话失效时的统一处理。
 *
 * 由 `client.ts` 的 401 回调触发（登录/注册接口的 401 已排除，那是「密码错误」）。
 * 除了清凭据，还要把 `sessionExpired` 置位 —— 否则用户正在答题、突然所有写操作都失败，
 * 界面却还显示着已登录，完全不知道发生了什么。
 */
function handleSessionExpired(): void {
  // 已经是游客态就不要再提示了（例如未登录用户访问需要登录的接口）。
  if (!user.value && !getToken()) return
  console.warn('[ShellQuest] 会话已在服务端失效，退回未登录态')
  clearUserState()
  sessionExpired.value = true
}

// client 不认识 store，由 store 反向注册回调（见 client.ts 的 setSessionExpiredHandler）。
setSessionExpiredHandler(handleSessionExpired)

export function dismissSessionAlert(): void {
  sessionExpired.value = false
}

function reportError(scope: string, error: unknown): void {
  console.warn(`[ShellQuest] ${scope}失败:`, error)
  if (isNetworkError(error)) apiUnavailable.value = true
}

/** 登录后（或恢复会话后）一次性拉齐打卡状态、技能树与进度。 */
async function loadUserData(): Promise<void> {
  await Promise.all([refreshCheckin(), refreshSkills(), refreshProgress()])
}

export async function refreshProgress(): Promise<void> {
  if (!user.value) return
  try {
    progress.value = await request<UserProgress>('/api/v1/user/progress')
  } catch (error) {
    reportError('加载进度', error)
  }
}

export async function refreshCheckin(): Promise<void> {
  if (!user.value) return
  try {
    checkin.value = await request<CheckInStatus>('/api/v1/checkin/status')
  } catch (error) {
    reportError('加载打卡状态', error)
  }
}

export async function refreshSkills(): Promise<void> {
  if (!user.value) return
  try {
    skills.value = await request<SkillTree>('/api/v1/user/skills')
  } catch (error) {
    reportError('加载技能树', error)
  }
}

/**
 * 应用启动时恢复登录态。
 *
 * token 存在但已失效（401）时清掉本地凭据并**提示重新登录** —— 早期版本是静默清掉，
 * 结果是用户重开页面发现自己莫名其妙变成游客，只能自己猜原因。
 */
export async function restoreSession(): Promise<void> {
  // 没有 token 就别去问 /auth/me —— 那必然是一个 401，会在控制台留下无意义的报错。
  if (!getToken()) {
    restoring.value = false
    return
  }

  restoring.value = true
  try {
    const me = await request<UserSummary>('/api/v1/auth/me')
    setUser(me)
    await loadUserData()
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      // 正常情况下 client.ts 的全局回调已经处理过了；这里再调一次是为了不依赖回调的
      // 注册顺序（两次调用是幂等的）。
      handleSessionExpired()
    } else {
      reportError('恢复登录状态', error)
    }
  } finally {
    restoring.value = false
  }
}

/**
 * 登录 / 注册。失败时**向上抛出**，由弹窗展示具体原因（用户名占用、密码错误等）。
 */
export async function authenticate(
  mode: 'login' | 'register',
  credentials: { username: string; password: string },
): Promise<void> {
  const payload = await request<AuthResponse>(`/api/v1/auth/${mode}`, {
    method: 'POST',
    body: credentials,
  })
  setToken(payload.token)
  setUser(payload.user)
  await loadUserData()
}

export function signOut(): void {
  clearUserState()
  // 主动登出不是「过期」，别弹那条提示。
  sessionExpired.value = false
}

export async function checkIn(): Promise<CheckInResponse | null> {
  if (!user.value) return null
  try {
    const payload = await request<CheckInResponse>('/api/v1/checkin', { method: 'POST' })
    checkin.value = payload.status
    setUser(payload.user)
    return payload
  } catch (error) {
    reportError('打卡', error)
    return null
  }
}

export function dismissApiAlert(): void {
  apiUnavailable.value = false
}

/**
 * 作答成功后同步本地用户与进度。作答接口已经返回了最新的 `user`，
 * 这里只补一次进度（单元状态、完成数会变）。
 */
export async function applySubmitResult(nextUser: UserSummary): Promise<void> {
  setUser(nextUser)
  await refreshProgress()
}

/**
 * 切换训练路径（REQUIREMENTS.md §3）。
 *
 * 后端只改 `training_mode` 一个字段，两种模式共用同一份完成记录与经验值，所以
 * **切换不丢进度**。但单元状态会整体重算（`locked` ⇄ `available`），因此这里在
 * 写回用户后必须让课程缓存失效 —— `curriculum` store 监听 `currentUser`，
 * `setUser` 换新对象即自动触发重拉，界面无需手动刷新。
 *
 * 未登录（无用户）直接返回 `false` 不发请求；请求失败则**向上抛出**，由调用方
 * 展示原因（401 未登录 / 422 取值非法）。
 */
export async function setTrainingMode(mode: TrainingMode): Promise<boolean> {
  if (!user.value) return false
  if (user.value.training_mode === mode) return true

  const payload = await request<UserSummary>('/api/v1/user/mode', {
    method: 'POST',
    body: { mode },
  })
  setUser(payload)
  await refreshProgress()
  return true
}
