/**
 * 成就目录缓存 + 「刚刚解锁」提示队列。
 *
 * 成就目录只有登录用户能拿到（`/api/v1/achievements` 需要 token），所以退出登录时一并清空。
 * 作答与打卡的响应里会带回新解锁的成就，这里把它们排进队列，由 `AchievementToast` 依次弹出，
 * 并让已缓存的目录失效 —— 否则用户切到成就页会看到「刚解锁的徽章还没亮」。
 */

import { computed, ref, watch } from 'vue'

import { isNetworkError, request } from '../api/client'
import type { AchievementList, AchievementUnlock } from '../types'
import { currentUser } from './session'

const catalog = ref<AchievementList | null>(null)
const loading = ref(false)
const error = ref('')
const pending = ref<AchievementUnlock[]>([])

export const achievements = computed(() => catalog.value)
export const achievementsLoading = computed(() => loading.value)
export const achievementsError = computed(() => error.value)
export const pendingUnlocks = computed(() => pending.value)

export async function loadAchievements(force = false): Promise<void> {
  if (!currentUser.value) {
    catalog.value = null
    return
  }
  if (!force && catalog.value) return

  loading.value = true
  error.value = ''
  try {
    catalog.value = await request<AchievementList>('/api/v1/achievements')
  } catch (err) {
    error.value = isNetworkError(err) ? '无法连接到后端，成就数据加载失败。' : (err as Error).message
  } finally {
    loading.value = false
  }
}

/** 作答 / 打卡返回新成就时调用：入队提示，并让缓存失效以便下次进入成就页重拉。 */
export function pushUnlocks(items: AchievementUnlock[]): void {
  if (!items.length) return
  pending.value = [...pending.value, ...items]
  catalog.value = null
}

/** 关掉当前这条提示，后面的依次顶上。 */
export function dismissUnlock(): void {
  pending.value = pending.value.slice(1)
}

export function clearUnlocks(): void {
  pending.value = []
}

// 退出登录后成就不再可见，缓存与队列都要清掉。
watch(currentUser, (user) => {
  if (!user) {
    catalog.value = null
    pending.value = []
    error.value = ''
  }
})
