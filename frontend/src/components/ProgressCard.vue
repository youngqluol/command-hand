<script setup lang="ts">
import { computed, ref } from 'vue'

import { pushUnlocks } from '../stores/achievements'
import { checkinStatus, checkIn, displayUser } from '../stores/session'
import { openAuth } from '../stores/ui'

const message = ref('')
const pending = ref(false)

const streakDays = computed(() => checkinStatus.value?.streak_days ?? displayUser.value.streak_days)
const checkedIn = computed(() => checkinStatus.value?.today_checked_in ?? false)

const meterWidth = computed(() => {
  const user = displayUser.value
  if (!user.level_xp_total) return '0%'
  return `${Math.min(100, (user.level_xp_earned / user.level_xp_total) * 100)}%`
})

const xpToNextLevel = computed(() => Math.max(0, displayUser.value.level_xp_total - displayUser.value.level_xp_earned))

async function perform(): Promise<void> {
  if (!checkinStatus.value) {
    openAuth('login')
    return
  }
  pending.value = true
  message.value = ''
  const payload = await checkIn()
  pending.value = false
  if (!payload) {
    message.value = '打卡失败，请稍后再试。'
    return
  }
  pushUnlocks(payload.achievements)
  message.value = payload.already_checked_in
    ? '今天已经打过卡啦，明天再来～'
    : `打卡成功 · +${payload.xp_awarded} XP · 连续 ${payload.status.streak_days} 天`
}
</script>

<template>
  <aside class="progress-card">
    <p class="eyebrow">你的进度</p>
    <div class="level-row">
      <span class="level-badge">LV.{{ String(displayUser.level).padStart(2, '0') }}</span>
      <strong>{{ displayUser.level_title }}</strong>
    </div>
    <div class="meter"><span :style="{ width: meterWidth }"></span></div>
    <p class="muted">
      {{ displayUser.xp.toLocaleString() }} 总 XP · 本级 {{ displayUser.level_xp_earned.toLocaleString() }} /
      {{ displayUser.level_xp_total.toLocaleString() }} · 下一级还需 {{ xpToNextLevel.toLocaleString() }} XP
    </p>
    <div class="streak">
      <span>⚡</span>
      <div>
        <strong>{{ streakDays }} 天</strong>
        <small>{{ checkedIn ? '今日已打卡' : '连续学习' }}</small>
      </div>
      <button :disabled="checkedIn || pending" @click="perform">
        {{ checkedIn ? '✓ 已打卡' : pending ? '打卡中…' : '打卡' }}
      </button>
    </div>
    <p v-if="message" class="checkin-msg">{{ message }}</p>
  </aside>
</template>
