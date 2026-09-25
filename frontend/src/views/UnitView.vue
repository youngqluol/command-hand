<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import QuestionPane from '../components/QuestionPane.vue'
import InlineText from '../components/InlineText.vue'
import MarkdownBlock from '../components/MarkdownBlock.vue'
import { curriculum, curriculumError, curriculumLoading, loadUnits, unitById } from '../stores/curriculum'
import { isLoggedIn } from '../stores/session'
import type { QuestKind } from '../types'

const props = defineProps<{ id: string }>()

const KIND_LABEL: Record<QuestKind, string> = {
  terminal: '终端',
  fill: '填空',
  choice: '选择',
  judge: '判断',
}

const unitId = computed(() => Number(props.id))
const unit = computed(() => unitById(unitId.value))
const activeQuestId = ref<number | null>(null)

const activeQuest = computed(() => {
  const target = unit.value
  if (!target) return null
  return target.quests.find((quest) => quest.id === activeQuestId.value) ?? target.quests[0] ?? null
})

const activeIndex = computed(() => {
  const target = unit.value
  if (!target || !activeQuest.value) return -1
  return target.quests.findIndex((quest) => quest.id === activeQuest.value?.id)
})

const nextUnit = computed(() => {
  const list = curriculum.value
  const idx = list.findIndex((item) => item.id === unitId.value)
  return idx >= 0 ? (list[idx + 1] ?? null) : null
})

const isLocked = computed(() => isLoggedIn.value && unit.value?.status === 'locked')

async function ensureLoaded(): Promise<void> {
  await loadUnits()
  if (!unit.value || activeQuestId.value !== null) return
  const first = unit.value.quests.find((quest) => quest.status !== 'done') ?? unit.value.quests[0]
  activeQuestId.value = first?.id ?? null
}

onMounted(ensureLoaded)

// 在同一路由下切换单元时组件会被复用，必须重置选中题目并重新定位。
watch(unitId, () => {
  activeQuestId.value = null
  void ensureLoaded()
})

function questStatusIcon(status: string | null): string {
  if (status === 'done') return '✓'
  if (status === 'current') return '▶'
  return '·'
}
</script>

<template>
  <section v-if="unit" class="quest-layout">
    <aside class="quest-list panel">
      <p class="eyebrow">
        {{ unit.zone }} · {{ String(unit.order).padStart(2, '0') }} /
        {{ String(curriculum.length).padStart(2, '0') }}
      </p>
      <h3 class="unit-title">{{ unit.title }}</h3>
      <p class="unit-goal"><InlineText :text="unit.goal" /></p>

      <button
        v-for="quest in unit.quests"
        :key="quest.id"
        class="quest-item"
        :class="[quest.status ?? 'unknown', { selected: quest.id === activeQuest?.id }]"
        @click="activeQuestId = quest.id"
      >
        <span>{{ questStatusIcon(quest.status) }}</span>
        <div>
          <strong>{{ quest.title }}</strong>
          <small>{{ KIND_LABEL[quest.kind] }} · +{{ quest.xp_reward }} XP</small>
        </div>
      </button>

      <div class="unit-foot">
        <p class="muted">{{ unit.completed_quests }} / {{ unit.quest_count }} 题已完成</p>
        <RouterLink v-if="nextUnit" class="text-button" :to="{ name: 'unit', params: { id: nextUnit.id } }">
          下一个单元：{{ nextUnit.title }} →
        </RouterLink>
      </div>
    </aside>

    <div class="quest-main">
      <div v-if="isLocked" class="feedback error-feedback locked-notice">
        <strong>该单元尚未解锁</strong>
        <span>请先完成上一个单元的全部题目。</span>
      </div>
      <QuestionPane v-if="activeQuest" :key="activeQuest.id" :quest="activeQuest" />
      <p v-else class="muted">这个单元还没有配置题目。</p>
      <p class="muted quest-progress-hint">
        第 {{ activeIndex + 1 }} / {{ unit.quests.length }} 题 · 完成本单元全部题目可获得额外 60 XP
      </p>
    </div>

    <section v-if="unit.knowledge" class="knowledge-card panel">
      <p class="eyebrow">本单元知识卡片</p>
      <MarkdownBlock :source="unit.knowledge" />
    </section>
  </section>

  <section v-else class="units-page">
    <p v-if="curriculumLoading" class="muted">正在加载课程…</p>
    <div v-else class="feedback error-feedback">
      <strong>{{ curriculumError || '找不到这个单元' }}</strong>
      <span>单元编号 {{ props.id }} 不存在，或课程数据尚未加载。</span>
      <RouterLink class="secondary compact" :to="{ name: 'units' }">返回课程地图</RouterLink>
    </div>
  </section>
</template>
