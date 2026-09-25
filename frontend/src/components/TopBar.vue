<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { currentUser, signOut } from '../stores/session'
import { openAuth } from '../stores/ui'

const route = useRoute()

const NAV = [
  { name: 'home', label: '训练营', to: { name: 'home' } },
  { name: 'units', label: '课程地图', to: { name: 'units' } },
  { name: 'commands', label: '命令速查', to: { name: 'commands' } },
]

// 「单元」属于课程地图这一支，导航上要高亮父级。
const activeNav = computed(() => (route.name === 'unit' ? 'units' : String(route.name ?? '')))

const accountLabel = computed(() => (currentUser.value ? `${currentUser.value.username}@quest` : '登录 / 注册'))
</script>

<template>
  <header class="topbar">
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
  </header>
</template>
