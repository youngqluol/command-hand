<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { isNetworkError } from '../api/client'
import { authenticate } from '../stores/session'
import { authModalOpen, authMode, closeAuth } from '../stores/ui'

const credentials = ref({ username: '', password: '' })
const error = ref('')
const pending = ref(false)

const title = computed(() => (authMode.value === 'login' ? '回到训练场' : '创建你的档案'))
const hint = computed(() =>
  authMode.value === 'login' ? '登录以同步你的进度与经验。' : '用户名仅包含字母、数字、下划线或连字符。',
)

// 关掉弹窗就清掉残留的错误与输入，避免下次打开还显示上一次的报错。
watch(authModalOpen, (open) => {
  if (open) return
  error.value = ''
  credentials.value = { username: '', password: '' }
})

function switchMode(): void {
  authMode.value = authMode.value === 'login' ? 'register' : 'login'
  error.value = ''
}

async function submit(): Promise<void> {
  error.value = ''
  pending.value = true
  try {
    await authenticate(authMode.value, credentials.value)
    closeAuth()
  } catch (err) {
    error.value = isNetworkError(err) ? '无法连接到 API 服务，请确认后端已启动。' : (err as Error).message
  } finally {
    pending.value = false
  }
}
</script>

<template>
  <div v-if="authModalOpen" class="modal-backdrop" @click.self="closeAuth">
    <form class="auth-modal panel" @submit.prevent="submit">
      <button type="button" class="close" aria-label="关闭" @click="closeAuth">×</button>
      <p class="eyebrow">账户</p>
      <h2>{{ title }}</h2>
      <p>{{ hint }}</p>
      <label>用户名<input v-model="credentials.username" required minlength="3" maxlength="32" /></label>
      <label>密码<input v-model="credentials.password" required type="password" minlength="8" /></label>
      <p v-if="error" class="auth-error">{{ error }}</p>
      <button class="primary" type="submit" :disabled="pending">
        {{ pending ? '处理中…' : authMode === 'login' ? '登录' : '注册并开始' }} →
      </button>
      <button type="button" class="text-button auth-switch" @click="switchMode">
        {{ authMode === 'login' ? '还没有账户？注册' : '已有账户？登录' }}
      </button>
    </form>
  </div>
</template>
