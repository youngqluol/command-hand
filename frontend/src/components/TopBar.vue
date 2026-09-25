<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { currentUser, signOut } from '../stores/session'
import { openAuth } from '../stores/ui'

const route = useRoute()

const NAV = [
  { name: 'home', label: '训练营', to: { name: 'home' } },
  { name: 'units', label: '课程地图', to: { name: 'units' } },
  { name: 'commands', label: '命令速查', to: { name: 'commands' } },
  { name: 'achievements', label: '成就', to: { name: 'achievements' } },
  { name: 'leaderboard', label: '排行榜', to: { name: 'leaderboard' } },
]

// 子路由在导航上要高亮父级：单元属于课程地图，命令详情属于命令速查。
const PARENT_NAV: Record<string, string> = {
  unit: 'units',
  'command-detail': 'commands',
}

const activeNav = computed(() => {
  const name = String(route.name ?? '')
  return PARENT_NAV[name] ?? name
})

const accountLabel = computed(() => (currentUser.value ? `${currentUser.value.username}@quest` : '登录 / 注册'))

/**
 * 吸顶状态。顶栏本身是 `position: sticky`，但未滚动时不该有底色 ——
 * 否则首屏顶部会出现一条与背景割裂的横带。滚动超过 4px 才挂 `.is-stuck`，
 * 由 CSS 补上毛玻璃底与分隔线（见 styles.css 的 `.topbar` 注释）。
 *
 * 用 `window.scrollY` 而不是 IntersectionObserver：这里只有一个哨兵元素，
 * 监听滚动更直接，`passive: true` 也不会阻塞滚动。
 */
const stuck = ref(false)

function syncStuck(): void {
  stuck.value = window.scrollY > 4
}

onMounted(() => {
  syncStuck()
  window.addEventListener('scroll', syncStuck, { passive: true })
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', syncStuck)
})
</script>

<template>
  <header class="topbar" :class="{ 'is-stuck': stuck }">
    <!-- 内层负责与正文同宽居中；外层负责全宽吸顶背景（见 styles.css）。 -->
    <div class="topbar-inner">
      <RouterLink class="brand" :to="{ name: 'home' }" aria-label="ShellQuest 首页">
        <span class="brand-mark">$_</span>
        <span>ShellQuest</span>
      </RouterLink>

      <nav aria-label="主导航">
        <RouterLink
          v-for="item in NAV"
          :key="item.name"
          :to="item.to"
          :class="{ active: activeNav === item.name }"
          :aria-current="activeNav === item.name ? 'page' : undefined"
        >
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="account">
        <template v-if="currentUser">
          <span class="profile"><span class="online-dot"></span>{{ accountLabel }}</span>
          <button class="text-button sign-out" @click="signOut">退出</button>
        </template>
        <button v-else class="profile" @click="openAuth('login')">
          <span class="online-dot offline"></span>{{ accountLabel }}
        </button>
      </div>
    </div>
  </header>
</template>
