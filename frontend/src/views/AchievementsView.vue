<script setup lang="ts">
import { computed, watch } from 'vue'

import { achievements, achievementsError, achievementsLoading, loadAchievements } from '../stores/achievements'
import { isLoggedIn, isRestoring } from '../stores/session'
import { openAuth } from '../stores/ui'
import type { AchievementItem } from '../types'

/**
 * 会话恢复是异步的：本视图挂载时 `currentUser` 往往还是 null（子组件的 onMounted 先于 App 执行），
 * 此时直接拉 `/achievements` 没带 token，拿不到数据。等恢复结束再拉。
 */
watch(
  [isRestoring, isLoggedIn],
  () => {
    if (!isRestoring.value) void loadAchievements()
  },
  { immediate: true },
)

const overall = computed(() => {
  const data = achievements.value
  return { total: data?.total ?? 0, unlocked: data?.unlocked ?? 0, percent: data?.unlocked_percent ?? 0 }
})

function percentOf(item: AchievementItem): number {
  if (!item.progress || !item.progress.target) return 0
  return Math.min(100, Math.round((item.progress.current / item.progress.target) * 100))
}
</script>

<template>
  <section class="achievements-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">成就</p>
        <h1>徽章墙</h1>
        <p class="muted">连续打卡、通关主题区域、首次作答即正确 —— 都会在这里留下记录。</p>
      </div>
      <div v-if="isLoggedIn" class="achievement-score">
        <strong
          >{{ overall.unlocked }}<span>/{{ overall.total }}</span></strong
        >
        <small>已解锁 · {{ overall.percent }}%</small>
        <div class="score-bar" role="presentation">
          <span :style="{ width: `${overall.percent}%` }"></span>
        </div>
      </div>
    </header>

    <div v-if="!isLoggedIn" class="panel login-prompt">
      <p class="muted">登录后才能记录成就。现在登录，此前的进度也会一并计入。</p>
      <button class="primary" @click="openAuth('login')">登录 / 注册</button>
    </div>

    <template v-else>
      <p v-if="achievementsLoading && !achievements" class="muted">正在加载成就…</p>
      <p v-else-if="achievementsError" class="feedback error-feedback">{{ achievementsError }}</p>

      <section v-for="group in achievements?.groups ?? []" :key="group.group" class="panel badge-group">
        <div class="section-heading">
          <div>
            <p class="eyebrow">成就分组</p>
            <h2>
              {{ group.group }}
              <span>{{ String(group.unlocked).padStart(2, '0') }} / {{ String(group.total).padStart(2, '0') }}</span>
            </h2>
          </div>
        </div>

        <ul class="badge-grid">
          <li v-for="item in group.items" :key="item.code" class="badge" :class="{ unlocked: item.unlocked }">
            <span class="badge-icon" aria-hidden="true">{{ item.icon }}</span>
            <div class="badge-body">
              <strong>{{ item.title }}</strong>
              <small>{{ item.description }}</small>
              <template v-if="item.unlocked">
                <span class="badge-state">已解锁</span>
              </template>
              <template v-else-if="item.progress">
                <div class="badge-progress" role="presentation">
                  <span :style="{ width: `${percentOf(item)}%` }"></span>
                </div>
                <span class="badge-state muted"> {{ item.progress.current }} / {{ item.progress.target }} </span>
              </template>
              <template v-else>
                <span class="badge-state muted">未解锁</span>
              </template>
            </div>
          </li>
        </ul>
      </section>
    </template>
  </section>
</template>
