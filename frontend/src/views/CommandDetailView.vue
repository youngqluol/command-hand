<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { ApiError, isNetworkError, request } from '../api/client'
import InlineText from '../components/InlineText.vue'
import MarkdownBlock from '../components/MarkdownBlock.vue'
import type { CommandDetail } from '../types'

/**
 * 命令详情页。排版顺序遵循 REQUIREMENTS.md §4.4.5：
 * 命令名 → 一句话简介 → 补充说明 → 语法 → 选项 → 参数 → 实例 → 扩展知识。
 *
 * 上游 Markdown 的结构并不统一（`ls.md` 用 `### 实例`，`find.md` 用 `## 例子`），
 * 所以章节按后端解析出的 `sections` 顺序渲染、用**原文标题**做小标题；
 * 只有选项与实例在解析成功时才用结构化数据替代原文（`curl` 这类就没解析出来，回落原文）。
 */

const props = defineProps<{ name: string }>()

const detail = ref<CommandDetail | null>(null)
const loading = ref(true)
const error = ref('')
const showRaw = ref(false)

const isMissing = computed(() => error.value.includes('不存在'))

async function load(name: string): Promise<void> {
  loading.value = true
  error.value = ''
  showRaw.value = false
  detail.value = null
  try {
    detail.value = await request<CommandDetail>(`/api/v1/commands/${encodeURIComponent(name)}`)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) error.value = '命令不存在'
    else error.value = isNetworkError(err) ? '无法连接到后端，命令详情加载失败。' : (err as Error).message
  } finally {
    loading.value = false
  }
}

watch(() => props.name, load, { immediate: true })

/** 结构化数据已经覆盖的章节不再重复渲染原文。 */
const sections = computed(() => {
  const data = detail.value
  if (!data) return []
  return data.sections.filter((section) => {
    if (section.role === 'syntax' && data.syntax) return false
    if (section.role === 'options' && data.options?.length) return false
    if (section.role === 'examples' && data.examples?.length) return false
    return true
  })
})

const hasStructuredOptions = computed(() => Boolean(detail.value?.options?.length))
const hasStructuredExamples = computed(() => Boolean(detail.value?.examples?.length))
/** 既没有结构化选项也没有原文选项章节时，不要显示一个空标题。 */
const showOptionsSection = computed(
  () => hasStructuredOptions.value || sections.value.some((section) => section.role === 'options'),
)
const showExamplesSection = computed(
  () => hasStructuredExamples.value || sections.value.some((section) => section.role === 'examples'),
)

/**
 * 上游个别文档的 Markdown 围栏不成对（如 `curl.md`），章节切分整体失败、`sections` 为空。
 * 这种情况必须直接回落原文，否则详情页除标题外一片空白。
 */
const needsRawFallback = computed(
  () =>
    Boolean(detail.value) &&
    sections.value.length === 0 &&
    !hasStructuredOptions.value &&
    !hasStructuredExamples.value &&
    !detail.value?.syntax,
)

function headingTag(level: number): string {
  return `h${Math.min(Math.max(level, 2), 4)}`
}
</script>

<template>
  <section class="command-detail-page">
    <nav class="breadcrumb" aria-label="面包屑">
      <RouterLink :to="{ name: 'commands' }">命令速查</RouterLink>
      <span>/</span>
      <span>{{ name }}</span>
    </nav>

    <p v-if="loading" class="muted">正在加载…</p>

    <div v-else-if="error" class="feedback error-feedback">
      <strong>{{ error }}</strong>
      <span v-if="isMissing"
        >没有名为 <code>{{ name }}</code> 的命令。</span
      >
      <span v-else>请确认后端服务已启动。</span>
      <RouterLink class="secondary compact" :to="{ name: 'commands' }">返回命令速查</RouterLink>
    </div>

    <template v-else-if="detail">
      <header class="command-header panel">
        <div class="command-header-main">
          <h1>
            <code>{{ detail.name }}</code>
          </h1>
          <div class="command-header-meta">
            <span class="chip">{{ detail.category }}</span>
            <span v-for="item in detail.tags" :key="item" class="tag">#{{ item }}</span>
          </div>
          <p class="command-header-summary"><InlineText :text="detail.summary" /></p>
        </div>
      </header>

      <div class="command-detail-layout">
        <article class="command-body panel">
          <section v-if="detail.syntax" class="command-section">
            <h2>语法</h2>
            <pre class="syntax-block"><code>{{ detail.syntax }}</code></pre>
          </section>

          <!-- 选项：结构化优先，否则回落原文章节 -->
          <section v-if="showOptionsSection" class="command-section">
            <h2>选项</h2>
            <table v-if="hasStructuredOptions" class="option-table">
              <tbody>
                <tr v-for="(option, index) in detail.options" :key="index">
                  <td class="option-flag"><InlineText :text="option.flag" /></td>
                  <td><InlineText :text="option.desc" /></td>
                </tr>
              </tbody>
            </table>
            <template v-else>
              <MarkdownBlock
                v-for="section in sections.filter((item) => item.role === 'options')"
                :key="section.title"
                :source="section.content"
              />
            </template>
          </section>

          <!-- 实例：结构化优先，否则回落原文章节 -->
          <section v-if="showExamplesSection" class="command-section">
            <h2>实例</h2>
            <template v-if="hasStructuredExamples">
              <div v-for="(example, index) in detail.examples" :key="index" class="example">
                <p v-if="example.description" class="example-desc">
                  <InlineText :text="example.description" />
                </p>
                <pre class="example-code"><code>{{ example.code }}</code></pre>
              </div>
            </template>
            <template v-else>
              <MarkdownBlock
                v-for="section in sections.filter((item) => item.role === 'examples')"
                :key="section.title"
                :source="section.content"
              />
            </template>
          </section>

          <!-- 其余章节按原文顺序渲染，用原文标题做小标题 -->
          <section
            v-for="section in sections.filter((item) => item.role !== 'options' && item.role !== 'examples')"
            :key="`${section.role}-${section.title}`"
            class="command-section"
          >
            <component :is="headingTag(section.level)">{{ section.title }}</component>
            <MarkdownBlock v-if="section.content" :source="section.content" />
          </section>

          <template v-if="needsRawFallback">
            <p class="muted raw-fallback-hint">
              这篇上游文档的章节结构无法解析（Markdown 代码围栏不成对），下面直接展示原文。
            </p>
            <MarkdownBlock :source="detail.body_markdown" />
          </template>
          <template v-else>
            <div class="raw-toggle">
              <button class="text-button" @click="showRaw = !showRaw">
                {{ showRaw ? '收起上游原文' : '查看上游原文（Markdown 渲染）' }}
              </button>
            </div>
            <MarkdownBlock v-if="showRaw" :source="detail.body_markdown" />
          </template>
        </article>

        <aside class="command-aside">
          <section class="panel aside-card">
            <p class="eyebrow">课程关联</p>
            <template v-if="detail.related_quests.length">
              <p class="muted aside-hint">
                这些关卡会用到 <code>{{ detail.name }}</code
                >：
              </p>
              <RouterLink
                v-for="quest in detail.related_quests"
                :key="quest.quest_id"
                class="aside-link"
                :to="{ name: 'unit', params: { id: quest.unit_id } }"
              >
                <span class="aside-order">U{{ String(quest.unit_order).padStart(2, '0') }}</span>
                <span>
                  <strong>{{ quest.quest_title }}</strong>
                  <small>{{ quest.zone }} · {{ quest.unit_title }}</small>
                </span>
              </RouterLink>
            </template>
            <p v-else class="muted aside-hint">课程里暂时没有用到这个命令的关卡。</p>
          </section>

          <section v-if="detail.related_commands.length" class="panel aside-card">
            <p class="eyebrow">相关命令</p>
            <div class="filter-chips">
              <RouterLink
                v-for="item in detail.related_commands"
                :key="item.name"
                class="filter-chip"
                :to="{ name: 'command-detail', params: { name: item.name } }"
              >
                {{ item.name }}
              </RouterLink>
            </div>
          </section>

          <section class="panel aside-card">
            <p class="eyebrow">来源与许可</p>
            <p class="muted aside-hint">
              内容来自
              <a :href="detail.source_url" target="_blank" rel="noopener noreferrer">jaywcjlove/linux-command</a> ，许可
              <strong>{{ detail.license }}</strong
              >，上游版本 {{ detail.source_version || '未知' }}。
            </p>
          </section>
        </aside>
      </div>
    </template>
  </section>
</template>
