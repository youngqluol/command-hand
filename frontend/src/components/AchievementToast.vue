<script setup lang="ts">
/**
 * 成就解锁提示。固定在右下角，自动消失，不遮挡作答区
 * （REQUIREMENTS.md §6：排行榜与成就作为辅助入口，不干扰主学习流程）。
 */
import { computed, onUnmounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { dismissUnlock, pendingUnlocks } from '../stores/achievements'

const DISMISS_AFTER = 6000

const current = computed(() => pendingUnlocks.value[0] ?? null)
const timer = ref<number | null>(null)

function clearTimer(): void {
  if (timer.value !== null) {
    window.clearTimeout(timer.value)
    timer.value = null
  }
}

// 每换一条就重置倒计时，否则连着解锁两个成就时第二条会一闪而过。
watch(
  current,
  (item) => {
    clearTimer()
    if (item) timer.value = window.setTimeout(dismissUnlock, DISMISS_AFTER)
  },
  { immediate: true },
)

onUnmounted(clearTimer)
</script>

<template>
  <Transition name="unlock">
    <aside v-if="current" class="unlock-toast" role="status" aria-live="polite">
      <span class="unlock-icon" aria-hidden="true">{{ current.icon }}</span>
      <div class="unlock-body">
        <p class="unlock-eyebrow">成就解锁 · {{ current.group }}</p>
        <p class="unlock-title">{{ current.title }}</p>
        <p class="unlock-desc">{{ current.description }}</p>
        <RouterLink class="unlock-link" :to="{ name: 'achievements' }" @click="dismissUnlock">
          查看全部成就 →
        </RouterLink>
      </div>
      <button type="button" class="unlock-close" aria-label="关闭提示" @click="dismissUnlock">×</button>
    </aside>
  </Transition>
</template>
