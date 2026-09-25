<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import type { RelatedQuest } from '../types'
import InlineText from './InlineText.vue'

/** 命令列表项。搜索结果与浏览列表共用（REQUIREMENTS.md §4.4.7「两种入口共用结果展示」）。 */
const props = defineProps<{
  name: string
  summary: string
  category: string
  tags: string[]
  /** 关键词 / 自然语言命中时的上下文片段 */
  snippet?: string
  relatedQuests?: RelatedQuest[]
  /** 键盘上下键选中的那一项 */
  active?: boolean
}>()

/** 同一个单元可能有多道题用到这条命令，列表里只保留单元级别的去重结果。 */
const questUnits = computed(() => {
  const seen = new Set<number>()
  const picked: RelatedQuest[] = []
  for (const quest of props.relatedQuests ?? []) {
    if (seen.has(quest.unit_id)) continue
    seen.add(quest.unit_id)
    picked.push(quest)
  }
  return picked.slice(0, 3)
})
</script>

<template>
  <RouterLink
    class="command-card"
    :class="{ active }"
    :to="{ name: 'command-detail', params: { name } }"
    :data-command="name"
  >
    <div class="command-card-head">
      <code class="command-name">{{ name }}</code>
      <span class="chip">{{ category }}</span>
      <span v-if="tags.length" class="command-tags">
        <span v-for="item in tags.slice(0, 4)" :key="item" class="tag">#{{ item }}</span>
      </span>
    </div>
    <p class="command-summary"><InlineText :text="summary" /></p>
    <p v-if="snippet" class="command-snippet"><InlineText :text="snippet" /></p>
    <p v-if="questUnits.length" class="command-related">
      <span>课程关联：</span>
      <span v-for="quest in questUnits" :key="quest.unit_id" class="related-chip">
        U{{ String(quest.unit_order).padStart(2, '0') }} {{ quest.unit_title }}
      </span>
    </p>
  </RouterLink>
</template>
