/**
 * 课程结构缓存。`/api/v1/units` 的响应比较大（21 个单元 × 每单元 3 道题的完整题干），
 * 首页、课程地图、单元页都要用，所以集中缓存一份，避免来回切换时重复拉取。
 *
 * 带 token 请求时后端会附上 `status` 字段；未登录时全部为 `null`，界面按「未登录」渲染。
 */

import { computed, ref, watch } from 'vue'

import { isNetworkError, request } from '../api/client'
import type { Unit } from '../types'
import { currentUser } from './session'

const units = ref<Unit[]>([])
const loading = ref(false)
const error = ref('')
/** 已加载数据所属的账号；换账号（含登录 / 退出）必须重拉，否则会看到上一个人的进度。 */
const loadedFor = ref<string | null>(null)

export const curriculum = computed(() => units.value)
export const curriculumLoading = computed(() => loading.value)
export const curriculumError = computed(() => error.value)

function scopeKey(): string {
  return currentUser.value ? `user:${currentUser.value.id}` : 'guest'
}

export async function loadUnits(force = false): Promise<void> {
  const key = scopeKey()
  if (!force && loadedFor.value === key && units.value.length) return

  loading.value = true
  error.value = ''
  try {
    units.value = await request<Unit[]>('/api/v1/units')
    loadedFor.value = key
  } catch (err) {
    error.value = isNetworkError(err) ? '无法连接到后端，课程数据加载失败。' : (err as Error).message
  } finally {
    loading.value = false
  }
}

/** 登录 / 退出后自动重拉，但只在已经有人加载过的情况下（避免启动时多打一次请求）。 */
watch(currentUser, () => {
  if (units.value.length) void loadUnits(true)
})

export function unitById(id: number): Unit | undefined {
  return units.value.find((unit) => unit.id === id)
}
