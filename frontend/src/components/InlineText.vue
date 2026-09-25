<script setup lang="ts">
import { computed } from 'vue'

import { parseInline } from '../utils/text'

/** 渲染含行内 `` `code` `` 与 `**粗体**` 的课程文案，不经过 `v-html`。 */
const props = defineProps<{ text: string }>()

const segments = computed(() => parseInline(props.text))
</script>

<template>
  <template v-for="(segment, index) in segments" :key="index">
    <code v-if="segment.code">{{ segment.text }}</code>
    <strong v-else-if="segment.bold">{{ segment.text }}</strong>
    <template v-else>{{ segment.text }}</template>
  </template>
</template>
