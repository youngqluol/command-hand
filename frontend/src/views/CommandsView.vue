<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { isNetworkError, request } from '../api/client'
import CommandCard from '../components/CommandCard.vue'
import type { CommandFacets, CommandPage, CommandSearchResult, RelatedQuest } from '../types'

/**
 * 命令速查：浏览（分类 / 首字母 / 标签）+ 关键词搜索 + 自然语言搜索。
 *
 * **URL 是筛选状态的唯一事实来源**（`?q=&mode=&category=&tag=&letter=&page=`），
 * 所以结果页可分享、可刷新、可前进后退（REQUIREMENTS.md §4.4）。
 * 搜索框文字先落在本地 `input`，防抖后再写回 URL —— 否则每敲一个字符都会推一条历史。
 */

const PAGE_SIZE = 40
const NATURAL_LIMIT = 12
const TAG_PREVIEW = 20

const route = useRoute()
const router = useRouter()

const q = computed(() => String(route.query.q ?? ''))
const mode = computed<'keyword' | 'natural'>(() => (route.query.mode === 'natural' ? 'natural' : 'keyword'))
const category = computed(() => String(route.query.category ?? ''))
const tag = computed(() => String(route.query.tag ?? ''))
const letter = computed(() => String(route.query.letter ?? ''))
const page = computed(() => Math.max(1, Number(route.query.page) || 1))

/** 自然语言模式只在真的有输入时才生效，否则退回浏览列表。 */
const isNatural = computed(() => mode.value === 'natural' && q.value.trim().length > 0)
const hasFilter = computed(() => Boolean(q.value || category.value || tag.value || letter.value))

const input = ref(q.value)
const searchInput = ref<HTMLInputElement | null>(null)
const facets = ref<CommandFacets | null>(null)
const pageData = ref<CommandPage | null>(null)
const naturalData = ref<CommandSearchResult | null>(null)
const loading = ref(false)
const error = ref('')
const highlight = ref(0)
/** 只有用过 ↑↓ 之后才画高亮框，否则首屏第一项会看起来像「已选中」。 */
const keyboardNav = ref(false)
const tagsExpanded = ref(false)

type DisplayHit = {
  name: string
  summary: string
  category: string
  tags: string[]
  snippet?: string
  relatedQuests?: RelatedQuest[]
}

const hits = computed<DisplayHit[]>(() => {
  if (isNatural.value) {
    return (naturalData.value?.hits ?? []).map((hit) => ({
      ...hit.command,
      snippet: hit.snippet,
      relatedQuests: hit.related_quests,
    }))
  }
  return pageData.value?.items ?? []
})

const total = computed(() => (isNatural.value ? hits.value.length : (pageData.value?.total ?? 0)))
const pageCount = computed(() => (isNatural.value ? 1 : Math.ceil(total.value / PAGE_SIZE)))
const suggestions = computed(() => (isNatural.value ? (naturalData.value?.suggestions ?? []) : []))
const visibleTags = computed(() => {
  const all = facets.value?.tags ?? []
  return tagsExpanded.value ? all : all.slice(0, TAG_PREVIEW)
})

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    if (isNatural.value) {
      naturalData.value = await request<CommandSearchResult>('/api/v1/commands/natural', {
        query: { q: q.value, limit: NATURAL_LIMIT },
      })
      pageData.value = null
    } else {
      pageData.value = await request<CommandPage>('/api/v1/commands', {
        query: {
          q: q.value,
          category: category.value,
          tag: tag.value,
          letter: letter.value,
          page: page.value,
          page_size: PAGE_SIZE,
        },
      })
      naturalData.value = null
    }
  } catch (err) {
    error.value = isNetworkError(err) ? '无法连接到后端，命令数据加载失败。' : (err as Error).message
  } finally {
    loading.value = false
  }
}

/** 把补丁合并进 query。`undefined` 表示删掉该参数。 */
function updateQuery(patch: Record<string, string | number | undefined>, replace = false): void {
  const merged: Record<string, string> = {}
  for (const [key, value] of Object.entries({ ...route.query, ...patch })) {
    if (value === undefined || value === null || value === '') continue
    merged[key] = String(value)
  }
  const target = { name: 'commands', query: merged }
  if (replace) void router.replace(target)
  else void router.push(target)
}

function toggleFilter(key: 'category' | 'tag' | 'letter', value: string): void {
  const current = key === 'category' ? category.value : key === 'tag' ? tag.value : letter.value
  updateQuery({ [key]: current === value ? undefined : value, page: undefined })
}

function setMode(next: 'keyword' | 'natural'): void {
  updateQuery({ mode: next === 'natural' ? 'natural' : undefined, page: undefined }, true)
}

function submitSearch(): void {
  updateQuery({ q: input.value.trim() || undefined, page: undefined })
}

function goToPage(next: number): void {
  updateQuery({ page: next <= 1 ? undefined : next })
}

function clearAll(): void {
  input.value = ''
  void router.push({ name: 'commands' })
}

function searchAsKeyword(name: string): void {
  input.value = name
  updateQuery({ q: name, mode: undefined, page: undefined })
}

// 输入防抖：300ms 内不再输入才写回 URL，避免每敲一个字符推一条历史。
let debounce: number | undefined
watch(input, (value) => {
  window.clearTimeout(debounce)
  debounce = window.setTimeout(() => {
    const next = value.trim()
    if (next === q.value) return
    updateQuery({ q: next || undefined, page: undefined }, true)
  }, 300)
})
onBeforeUnmount(() => window.clearTimeout(debounce))

// URL 变化（含前进后退）时把输入框同步回来。
watch(q, (value) => {
  if (value !== input.value.trim()) input.value = value
})

// `immediate` 是必需的：带 query 直接进入（分享链接 / 刷新）时组件挂载后 watch 不会自己触发。
watch(
  [q, mode, category, tag, letter, page],
  () => {
    highlight.value = 0
    void load()
  },
  { immediate: true },
)

watch(hits, () => {
  highlight.value = 0
  keyboardNav.value = false
})

function moveHighlight(delta: number): void {
  if (!hits.value.length) return
  keyboardNav.value = true
  highlight.value = Math.max(0, Math.min(highlight.value + delta, hits.value.length - 1))
  document.querySelector('.command-card.active')?.scrollIntoView({ block: 'nearest' })
}

function openHighlighted(): void {
  const target = hits.value[highlight.value]
  if (target) void router.push({ name: 'command-detail', params: { name: target.name } })
}

/** `/` 聚焦、`Esc` 清空、`↑↓` 切换、`Enter` 打开（REQUIREMENTS.md §4.4.7 交互）。 */
function onKeydown(event: KeyboardEvent): void {
  const target = event.target as HTMLElement | null
  const typing =
    target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || Boolean(target?.isContentEditable)

  if (event.key === '/' && !typing) {
    event.preventDefault()
    searchInput.value?.focus()
    return
  }
  if (!typing) return

  if (event.key === 'Escape') {
    input.value = ''
    searchInput.value?.blur()
  } else if (event.key === 'ArrowDown') {
    event.preventDefault()
    moveHighlight(1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    moveHighlight(-1)
  } else if (event.key === 'Enter') {
    event.preventDefault()
    // 输入框里还有没提交的内容时先提交搜索，否则打开高亮项。
    if (input.value.trim() !== q.value) submitSearch()
    else openHighlighted()
  }
}

onMounted(async () => {
  window.addEventListener('keydown', onKeydown)
  try {
    facets.value = await request<CommandFacets>('/api/v1/commands/facets')
  } catch (err) {
    console.warn('[ShellQuest] 加载命令分面失败:', err)
  }
})

onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <section class="commands-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">命令速查</p>
        <h1>描述问题，找到命令。</h1>
        <p class="muted">
          例如「查看某个端口被谁占用」「磁盘满了怎么查」。已收录
          <strong>{{ facets?.total ?? '—' }}</strong> 条命令，按 <kbd>/</kbd> 快速聚焦搜索框。
        </p>
      </div>
    </header>

    <div class="search-bar panel">
      <form class="search-input" @submit.prevent="submitSearch">
        <span>⌕</span>
        <input
          ref="searchInput"
          v-model="input"
          aria-label="搜索命令"
          autocomplete="off"
          spellcheck="false"
          :placeholder="mode === 'natural' ? '用一句话描述你想做什么' : '输入命令名或关键词，如 ls、端口、磁盘'"
        />
        <kbd>/</kbd>
      </form>
      <div class="mode-switch">
        <button :class="['zone-chip', { active: mode === 'keyword' }]" @click="setMode('keyword')">关键词</button>
        <button :class="['zone-chip', { active: mode === 'natural' }]" @click="setMode('natural')">自然语言</button>
      </div>
    </div>

    <div class="commands-layout">
      <aside class="filters panel">
        <div class="filter-group">
          <p class="eyebrow">分类</p>
          <div class="filter-chips">
            <button
              v-for="item in facets?.categories ?? []"
              :key="item.category"
              :class="['filter-chip', { active: category === item.category }]"
              @click="toggleFilter('category', item.category)"
            >
              {{ item.category }} <b>{{ item.count }}</b>
            </button>
          </div>
        </div>

        <div class="filter-group">
          <p class="eyebrow">首字母</p>
          <div class="letter-grid">
            <button
              v-for="item in facets?.letters ?? []"
              :key="item.letter"
              :class="['letter-chip', { active: letter === item.letter }]"
              :title="`${item.count} 条`"
              @click="toggleFilter('letter', item.letter)"
            >
              {{ item.letter }}
            </button>
          </div>
        </div>

        <div class="filter-group">
          <p class="eyebrow">标签</p>
          <div class="filter-chips">
            <button
              v-for="item in visibleTags"
              :key="item.tag"
              :class="['filter-chip', { active: tag === item.tag }]"
              @click="toggleFilter('tag', item.tag)"
            >
              {{ item.tag }} <b>{{ item.count }}</b>
            </button>
          </div>
          <button
            v-if="(facets?.tags.length ?? 0) > TAG_PREVIEW"
            class="text-button more-tags"
            @click="tagsExpanded = !tagsExpanded"
          >
            {{ tagsExpanded ? '收起' : `展开全部 ${facets?.tags.length} 个标签` }}
          </button>
        </div>

        <button v-if="hasFilter" class="secondary clear-filters" @click="clearAll">清除全部筛选</button>
      </aside>

      <div class="results">
        <div class="results-head">
          <p class="muted">
            <template v-if="loading">加载中…</template>
            <template v-else-if="isNatural">自然语言匹配到 {{ total }} 条命令</template>
            <template v-else-if="total">
              {{ total }} 条结果<template v-if="pageCount > 1"> · 第 {{ page }} / {{ pageCount }} 页</template>
            </template>
            <template v-else>没有匹配的命令</template>
          </p>
          <p v-if="isNatural" class="muted">按课程主题匹配，命中的命令都出现在对应关卡里。</p>
        </div>

        <p v-if="error" class="feedback error-feedback">{{ error }}</p>

        <div v-if="hits.length" class="command-list">
          <CommandCard
            v-for="(item, index) in hits"
            :key="item.name"
            :name="item.name"
            :summary="item.summary"
            :category="item.category"
            :tags="item.tags"
            :snippet="item.snippet"
            :related-quests="item.relatedQuests"
            :active="keyboardNav && index === highlight"
          />
        </div>

        <div v-else-if="!loading && !error" class="feedback coming-soon">
          <strong>没有找到匹配的命令</strong>
          <span v-if="isNatural">
            课程只覆盖 21 个主题，这句话可能没落在任何一个关卡上。试试下面的关键词兜底建议，或切到「关键词」模式。
          </span>
          <span v-else>换个关键词，或者点左侧的分类 / 首字母浏览全部命令。</span>
        </div>

        <div v-if="suggestions.length" class="suggestions">
          <p class="eyebrow">关键词兜底建议</p>
          <div class="filter-chips">
            <button v-for="name in suggestions" :key="name" class="filter-chip" @click="searchAsKeyword(name)">
              {{ name }}
            </button>
          </div>
        </div>

        <nav v-if="pageCount > 1" class="pagination" aria-label="分页">
          <button class="secondary" :disabled="page <= 1" @click="goToPage(page - 1)">← 上一页</button>
          <span class="muted">{{ page }} / {{ pageCount }}</span>
          <button class="secondary" :disabled="page >= pageCount" @click="goToPage(page + 1)">下一页 →</button>
        </nav>
      </div>
    </div>
  </section>
</template>
