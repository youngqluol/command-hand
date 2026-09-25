/**
 * 纯界面状态：登录弹窗的开合与模式。
 *
 * 单独放一个文件是因为任何视图都可能需要唤起登录（例如未登录时点「进入单元」），
 * 用 props 逐层透传会很啰嗦。
 */

import { ref } from 'vue'

export type AuthMode = 'login' | 'register'

export const authModalOpen = ref(false)
export const authMode = ref<AuthMode>('login')

export function openAuth(mode: AuthMode = 'login'): void {
  authMode.value = mode
  authModalOpen.value = true
}

export function closeAuth(): void {
  authModalOpen.value = false
}
