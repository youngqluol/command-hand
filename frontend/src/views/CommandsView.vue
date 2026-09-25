<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import { isNetworkError, request } from '../api/client'
import type { CommandFacets } from '../types'

/**
 * 命令速查的前端页面尚未实现（REQUIREMENTS.md §4.4.12 最后两行）。
 * 后端接口已全部就绪，这里先展示数据规模，避免让导航项指向空白页。
 */
const facets = ref<CommandFacets | null>(null)
const error = ref('')

onMounted(async () => {
  try {
    facets.value = await request<CommandFacets>('/api/v1/commands/facets')
  } catch (err) {
    error.value = isNetworkError(err) ? '无法连接到后端。' : (err as Error).message
  }
})
</script>

<template>
  <section class="search-page panel">
    <p class="eyebrow">命令速查</p>
    <h1>描述问题，找到命令。</h1>
    <p>例如：查看 8080 端口被谁占用、统计日志中出现最多的 IP。</p>

    <div class="feedback coming-soon">
      <strong>界面正在开发中</strong>
      <span>
        后端检索接口（关键词 + 自然语言 + 兜底建议）已经就绪，前端页面是下一阶段的工作。 课程主流程已可正常使用。
      </span>
    </div>

    <div v-if="facets" class="facets-preview">
      <p class="muted">
        已收录 <strong>{{ facets.total }}</strong> 条命令 · {{ facets.categories.length }} 个分类 ·
        {{ facets.tags.length }} 个标签 · {{ facets.letters.length }} 个首字母
      </p>
      <div class="facets-row">
        <span v-for="item in facets.categories" :key="item.category" class="chip">
          {{ item.category }} {{ item.count }}
        </span>
      </div>
    </div>
    <p v-else-if="error" class="auth-error">{{ error }}</p>

    <RouterLink class="secondary compact" :to="{ name: 'units' }">先去课程地图 →</RouterLink>
  </section>
</template>
