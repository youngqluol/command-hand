<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'

import ProgressCard from '../components/ProgressCard.vue'
import SkillTreePanel from '../components/SkillTreePanel.vue'
import InlineText from '../components/InlineText.vue'
import { curriculum, curriculumError, loadUnits } from '../stores/curriculum'
import { displayUser, isLoggedIn } from '../stores/session'
import { openAuth } from '../stores/ui'

onMounted(() => loadUnits())

/** 当前该做的单元：优先后端标出的 current，其次第一个未完成的，最后退回第一个。 */
const currentUnit = computed(() => {
  const list = curriculum.value
  if (!list.length) return null
  return list.find((unit) => unit.status === 'current') ?? list.find((unit) => unit.status !== 'done') ?? list[0]
})

/** 当前单元里第一道没做对的题；全做完了就退回第一题。 */
const nextQuest = computed(() => {
  const unit = currentUnit.value
  if (!unit) return null
  return unit.quests.find((quest) => quest.status !== 'done') ?? unit.quests[0] ?? null
})

const totalUnits = computed(() => curriculum.value.length)
const doneUnits = computed(() => curriculum.value.filter((unit) => unit.status === 'done').length)
const totalQuests = computed(() => curriculum.value.reduce((sum, unit) => sum + unit.quest_count, 0))
const doneQuests = computed(() => curriculum.value.reduce((sum, unit) => sum + unit.completed_quests, 0))
</script>

<template>
  <section class="dashboard">
    <div class="hero-card grid-lines">
      <p class="eyebrow">{{ totalUnits || 21 }} 个课程单元 · 自由加速完成</p>
      <h1>把 Linux 命令，<br /><em>练成实战直觉。</em></h1>
      <p class="hero-copy">不是背命令。你会在发布、故障与运维现场中，找到解决问题的正确组合。</p>
      <div class="hero-actions">
        <RouterLink v-if="currentUnit" class="primary" :to="{ name: 'unit', params: { id: currentUnit.id } }">
          继续当前任务 <span>→</span>
        </RouterLink>
        <button v-else class="primary" disabled>加载课程中…</button>
        <RouterLink class="secondary" :to="{ name: 'commands' }">查询命令</RouterLink>
      </div>
      <p v-if="curriculumError" class="hero-warning">{{ curriculumError }}</p>
    </div>

    <ProgressCard />

    <SkillTreePanel />

    <section class="mission-card panel">
      <template v-if="currentUnit && nextQuest">
        <div class="mission-meta">
          <span class="chip">当前任务</span>
          <span>{{ currentUnit.zone }} / {{ String(currentUnit.order).padStart(2, '0') }}</span>
          <span class="xp">+{{ nextQuest.xp_reward }} XP</span>
        </div>
        <h2>{{ nextQuest.title }}</h2>
        <p><InlineText :text="nextQuest.scenario" /></p>
        <RouterLink class="primary compact" :to="{ name: 'unit', params: { id: currentUnit.id } }">
          进入任务 →
        </RouterLink>
      </template>
      <template v-else-if="!curriculumError">
        <div class="mission-meta"><span class="chip">当前任务</span></div>
        <h2>正在加载课程…</h2>
        <p>稍候片刻，正在从后端获取 21 个单元的课程结构。</p>
      </template>
      <template v-else>
        <div class="mission-meta"><span class="chip">当前任务</span></div>
        <h2>课程数据不可用</h2>
        <p>无法从后端获取课程结构，请确认服务已启动后刷新页面。</p>
      </template>
    </section>

    <section v-if="isLoggedIn" class="mission-card panel compact-panel">
      <div class="mission-meta">
        <span class="chip">总进度</span>
        <span>{{ doneUnits }} / {{ totalUnits }} 个单元</span>
        <span class="xp">{{ doneQuests }} / {{ totalQuests }} 道题</span>
      </div>
      <h2>{{ displayUser.level_title }} · {{ displayUser.xp.toLocaleString() }} XP</h2>
      <p>已完成 {{ doneQuests }} 道题，继续推进即可解锁后续区域。</p>
    </section>

    <section v-else class="mission-card panel compact-panel">
      <div class="mission-meta"><span class="chip">进度同步</span></div>
      <h2>登录后保存你的进度</h2>
      <p>当前是游客模式，作答结果不会保存。登录即可记录经验值、连续打卡与技能树。</p>
      <button class="primary compact" @click="openAuth('login')">登录 / 注册 →</button>
    </section>
  </section>
</template>
