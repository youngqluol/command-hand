/**
 * 路由表。nginx 与 Vite 都配了 history 回退（`try_files ... /index.html`），
 * 所以用 `createWebHistory`，URL 可分享、可刷新（REQUIREMENTS.md §4.4 要求命令↔任务双向跳转）。
 *
 * 视图一律懒加载：命令速查与课程作答互不依赖，没必要一起进首屏包。
 */

import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/HomeView.vue'),
      meta: { title: '训练营' },
    },
    {
      path: '/units',
      name: 'units',
      component: () => import('../views/UnitsView.vue'),
      meta: { title: '课程地图' },
    },
    {
      path: '/units/:id(\\d+)',
      name: 'unit',
      component: () => import('../views/UnitView.vue'),
      props: true,
      meta: { title: '单元' },
    },
    {
      path: '/commands',
      name: 'commands',
      component: () => import('../views/CommandsView.vue'),
      meta: { title: '命令速查' },
    },
    {
      path: '/commands/:name',
      name: 'command-detail',
      component: () => import('../views/CommandDetailView.vue'),
      props: true,
      meta: { title: '命令详情' },
    },
    {
      path: '/achievements',
      name: 'achievements',
      component: () => import('../views/AchievementsView.vue'),
      meta: { title: '成就' },
    },
    {
      path: '/leaderboard',
      name: 'leaderboard',
      component: () => import('../views/LeaderboardView.vue'),
      meta: { title: '排行榜' },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('../views/NotFoundView.vue'),
      meta: { title: '页面不存在' },
    },
  ],
  /*
   * 滚动归零**不在这里**做。导航确认的那一刻旧页面还在退场（App.vue 的页面过渡是
   * `out-in`，要 130ms），此时跳顶会让用户看到「旧页面先跳到顶部再淡出」的闪烁。
   * 改由 App.vue 的过渡钩子在「新页面进场前」归零 —— 那一刻屏幕上没有内容，跳转不可见。
   * 返回 false 即「不自动滚动」。
   */
  scrollBehavior: () => false,
})

router.afterEach((to) => {
  const title = to.meta.title
  document.title = typeof title === 'string' ? `${title} · ShellQuest` : 'ShellQuest · Linux 实战训练'
})

export default router
