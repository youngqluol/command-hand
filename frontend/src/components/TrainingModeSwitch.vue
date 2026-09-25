<script setup lang="ts">
/**
 * 训练路径切换器（REQUIREMENTS.md §3）。
 *
 * 两种路径共用同一份完成记录与经验值，切换只影响「未完成的单元是否上锁」，
 * 所以这里不做任何二次确认 —— 切回来进度分毫不差。
 */
import { ref } from 'vue'

import { isLoggedIn, setTrainingMode, trainingMode } from '../stores/session'
import { openAuth } from '../stores/ui'
import type { TrainingMode } from '../types'

const MODES: Array<{ value: TrainingMode; label: string; hint: string }> = [
  { value: 'camp', label: '21 天训练营', hint: '按顺序推进，完成一个单元解锁下一个' },
  { value: 'free', label: '自由闯关', hint: '不设关卡锁，任意单元随时可挑战' },
]

const pending = ref(false)
const error = ref('')

async function choose(mode: TrainingMode): Promise<void> {
  if (!isLoggedIn.value || pending.value || mode === trainingMode.value) return
  pending.value = true
  error.value = ''
  try {
    await setTrainingMode(mode)
  } catch (err) {
    error.value = (err as Error).message || '切换失败，请稍后重试'
  } finally {
    pending.value = false
  }
}
</script>

<template>
  <div class="training-switch panel">
    <div class="training-switch-head">
      <p class="eyebrow">训练路径</p>
      <span v-if="!isLoggedIn" class="muted">登录后可切换</span>
      <span v-else-if="pending" class="muted">正在切换…</span>
      <span v-else class="muted">{{ MODES.find((item) => item.value === trainingMode)?.hint }}</span>
    </div>

    <div class="training-switch-options" role="group" aria-label="训练路径">
      <button
        v-for="item in MODES"
        :key="item.value"
        type="button"
        class="training-switch-option"
        :class="{ active: item.value === trainingMode }"
        :aria-pressed="item.value === trainingMode"
        :disabled="!isLoggedIn || pending"
        @click="choose(item.value)"
      >
        {{ item.label }}
      </button>
    </div>

    <p v-if="error" class="feedback error-feedback training-switch-error">{{ error }}</p>
    <button v-else-if="!isLoggedIn" class="text-button" type="button" @click="openAuth('login')">
      登录 / 注册 以解锁切换 →
    </button>
  </div>
</template>
