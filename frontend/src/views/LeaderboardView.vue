<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { isNetworkError, request } from '../api/client'
import { isLoggedIn } from '../stores/session'
import { openAuth } from '../stores/ui'
import type { Leaderboard } from '../types'

const LIMIT = 50

const board = ref<Leaderboard | null>(null)
const loading = ref(false)
const error = ref('')

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    board.value = await request<Leaderboard>('/api/v1/leaderboard', { query: { limit: LIMIT } })
  } catch (err) {
    error.value = isNetworkError(err) ? '无法连接到后端，排行榜加载失败。' : (err as Error).message
  } finally {
    loading.value = false
  }
}

onMounted(load)

/** 自己排在前 50 名之内时列表里已经有了一行，不必再单独置底重复展示。 */
const mePinned = computed(() => {
  const me = board.value?.me
  if (!me) return null
  return board.value?.entries.some((entry) => entry.is_me) ? null : me
})
</script>

<template>
  <section class="leaderboard-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">排行榜</p>
        <h1>公开榜</h1>
        <p class="muted">按经验值降序、连续打卡天数降序排列。只展示用户名、等级、经验与连续打卡。</p>
      </div>
      <p v-if="board" class="muted hint">共 {{ board.total_users }} 名用户</p>
    </header>

    <p v-if="loading && !board" class="muted">正在加载排行榜…</p>
    <p v-else-if="error" class="feedback error-feedback">{{ error }}</p>

    <template v-else-if="board">
      <p v-if="!board.entries.length" class="muted">还没有用户上榜。注册并完成一道题就会出现在这里。</p>

      <table v-else class="leaderboard panel">
        <thead>
          <tr>
            <th scope="col" class="col-rank">名次</th>
            <th scope="col">用户</th>
            <th scope="col" class="col-level">等级</th>
            <th scope="col" class="col-xp">经验</th>
            <th scope="col" class="col-streak">连续打卡</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="entry in board.entries" :key="entry.username" :class="{ me: entry.is_me }">
            <td class="col-rank">{{ entry.rank }}</td>
            <td>
              <span class="leader-name">{{ entry.username }}</span>
              <span v-if="entry.is_me" class="chip me-chip">你</span>
            </td>
            <td class="col-level">
              <span class="chip">LV.{{ String(entry.level).padStart(2, '0') }}</span>
              <small class="muted">{{ entry.level_title }}</small>
            </td>
            <td class="col-xp">{{ entry.xp }}</td>
            <td class="col-streak">{{ entry.streak_days }} 天</td>
          </tr>
          <tr v-if="mePinned" class="me pinned">
            <td class="col-rank">{{ mePinned.rank }}</td>
            <td>
              <span class="leader-name">{{ mePinned.username }}</span>
              <span class="chip me-chip">你</span>
            </td>
            <td class="col-level">
              <span class="chip">LV.{{ String(mePinned.level).padStart(2, '0') }}</span>
              <small class="muted">{{ mePinned.level_title }}</small>
            </td>
            <td class="col-xp">{{ mePinned.xp }}</td>
            <td class="col-streak">{{ mePinned.streak_days }} 天</td>
          </tr>
        </tbody>
      </table>

      <p v-if="!isLoggedIn" class="muted login-hint">
        登录后可看到自己的名次 ——
        <button class="text-button" @click="openAuth('login')">登录 / 注册</button>
      </p>
    </template>
  </section>
</template>
