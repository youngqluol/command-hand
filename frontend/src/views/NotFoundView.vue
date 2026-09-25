<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <section class="search-page panel">
    <p class="eyebrow">404</p>
    <h1>这个页面不存在。</h1>
    <p>链接可能已经失效，或者地址输错了。</p>
    <div class="hero-actions">
      <RouterLink class="primary" :to="{ name: 'home' }">回到训练营</RouterLink>
      <RouterLink class="secondary" :to="{ name: 'units' }">课程地图</RouterLink>
    </div>
  </section>
</template>
