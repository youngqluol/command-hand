<script setup lang="ts">
import { computed } from 'vue'

import { renderMarkdown } from '../utils/markdown'

/**
 * 渲染一段 Markdown（课程 `knowledge`、命令手册正文等）。
 *
 * `v-html` 在这里是必要的：内容已经是 HTML。安全性由 `renderMarkdown()` 里的
 * DOMPurify 保证，且上游原文本身就是 Markdown 而非可信 HTML。
 */
const props = defineProps<{ source: string }>()

const html = computed(() => renderMarkdown(props.source))
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -- 内容已在 renderMarkdown() 中经 DOMPurify 净化 -->
  <div class="markdown-body" v-html="html"></div>
</template>
