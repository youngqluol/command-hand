<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'

import { apiPrefix } from './api/client'
import AchievementToast from './components/AchievementToast.vue'
import AuthModal from './components/AuthModal.vue'
import TopBar from './components/TopBar.vue'
import { apiUnavailableState, dismissApiAlert, restoreSession } from './stores/session'

onMounted(restoreSession)

/**
 * 新页面进场前把滚动位置归零。
 *
 * 不能交给 router 的 `scrollBehavior`：它在导航确认时就重置滚动，而此刻旧页面还在退场
 * （`mode="out-in"` 要 130ms），用户会看到旧页面「先跳到顶部再淡出」。放在进场前，
 * 屏幕上正好没有内容，跳转不可见。详见 router/index.ts 的 scrollBehavior 注释。
 */
function resetScroll(): void {
  window.scrollTo(0, 0)
}
</script>

<template>
  <!-- 顶栏在 app-shell 之外：吸顶时要通栏铺背景，正文才限宽居中（styles.css `.topbar`）。 -->
  <TopBar />

  <main class="app-shell">
    <div v-if="apiUnavailableState" class="api-alert">
      <span class="alert-mark">⚠</span>
      <div>
        <strong>无法连接到后端 API</strong>
        <small>
          请检查：① backend 容器是否正常启动 ② nginx 是否可反代到 <code>backend:8000</code> ③
          服务器防火墙是否放行端口。当前 API 前缀：<code>{{ apiPrefix }}</code>
        </small>
      </div>
      <button class="alert-close" aria-label="关闭提示" @click="dismissApiAlert">×</button>
    </div>

    <!--
      页面切换动效：`mode="out-in"` 让旧页面先退场，避免两个页面在文档流里叠一帧导致跳动。
      `:key` 用完整路径而不是组件 —— 否则 `/commands/ls` → `/commands/grep` 复用同一个组件，
      不会有任何过渡（命令详情页只靠 props 变化刷新）。
    -->
    <RouterView v-slot="{ Component, route: current }">
      <Transition name="page" mode="out-in" @before-enter="resetScroll">
        <component :is="Component" :key="current.path" />
      </Transition>
    </RouterView>
  </main>

  <AuthModal />
  <AchievementToast />
</template>
