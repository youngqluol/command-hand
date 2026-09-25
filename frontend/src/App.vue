<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'

import { apiPrefix } from './api/client'
import AuthModal from './components/AuthModal.vue'
import TopBar from './components/TopBar.vue'
import { apiUnavailableState, dismissApiAlert, restoreSession } from './stores/session'

onMounted(restoreSession)
</script>

<template>
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

    <TopBar />

    <RouterView v-slot="{ Component }">
      <component :is="Component" />
    </RouterView>

    <AuthModal />
  </main>
</template>
