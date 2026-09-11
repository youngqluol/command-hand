<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

type Quest = {
  id: number
  zone: string
  title: string
  command: string
  description: string
  status: 'done' | 'current' | 'locked'
}

type UserSummary = {
  id: number
  username: string
  xp: number
  streak_days: number
}

const activeTab = ref<'home' | 'quests' | 'search'>('home')
const query = ref('')
const authUser = ref<UserSummary | null>(null)
const sessionToken = ref(localStorage.getItem('shellquest-session') ?? '')
const showAuth = ref(false)
const authMode = ref<'login' | 'register'>('login')
const credentials = ref({ username: '', password: '' })
const authError = ref('')
const completionMessage = ref('')

const fallbackQuests: Quest[] = [
  { id: 1, zone: '文件工坊', title: '初入服务器', command: 'whoami · pwd', description: '确认当前身份、目录和系统环境。', status: 'done' },
  { id: 2, zone: '文件工坊', title: '项目文件定位', command: 'find · ls', description: '在发布目录中找到缺失的配置文件。', status: 'current' },
  { id: 3, zone: '文件工坊', title: '文件整理与备份', command: 'cp · mv', description: '安全归档日志，避免覆盖已有备份。', status: 'locked' },
]

const quests = ref<Quest[]>(fallbackQuests)

const activeQuest = computed(() => quests.value.find((quest) => quest.status === 'current') ?? quests.value[0])
const result = ref<'idle' | 'success' | 'error'>('idle')
const terminalInput = ref('find /srv/app -name "*.env"')

async function runCommand() {
  result.value = terminalInput.value.trim().includes('find') && terminalInput.value.includes('.env') ? 'success' : 'error'
  completionMessage.value = ''
  if (result.value !== 'success' || !authUser.value || !activeQuest.value) return
  try {
    const response = await fetch(`/api/v1/quests/${activeQuest.value.id}/complete`, {
      method: 'POST',
      headers: { 'X-Session-Token': sessionToken.value },
    })
    if (!response.ok) return
    const payload: { already_completed: boolean; xp_awarded: number; user: UserSummary } = await response.json()
    authUser.value = payload.user
    completionMessage.value = payload.already_completed ? '该任务已完成，进度已保留。' : `任务完成 · +${payload.xp_awarded} XP`
  } catch {
    completionMessage.value = '已在本地完成演练；暂时无法保存进度。'
  }
}

function selectTab(tab: 'home' | 'quests' | 'search') {
  activeTab.value = tab
  result.value = 'idle'
}

async function submitAuth() {
  authError.value = ''
  try {
    const response = await fetch(`/api/v1/auth/${authMode.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials.value),
    })
    const payload = await response.json()
    if (!response.ok) {
      authError.value = payload.detail ?? '请求失败，请稍后再试。'
      return
    }
    sessionToken.value = payload.token
    localStorage.setItem('shellquest-session', payload.token)
    authUser.value = payload.user
    showAuth.value = false
    credentials.value = { username: '', password: '' }
  } catch {
    authError.value = '无法连接到本地 API。'
  }
}

onMounted(async () => {
  try {
    const response = await fetch('/api/v1/quests')
    if (!response.ok) return
    const apiQuests: Array<Omit<Quest, 'command' | 'status'> & { command_hint: string }> = await response.json()
    quests.value = apiQuests.map((quest) => ({
      ...quest,
      command: quest.command_hint,
      status: quest.id === 1 ? 'done' : quest.id === 2 ? 'current' : 'locked',
    }))
  } catch {
    // 本地 API 未启动时保留原型数据，方便单独开发前端。
  }
  if (sessionToken.value) {
    try {
      const response = await fetch('/api/v1/auth/me', { headers: { 'X-Session-Token': sessionToken.value } })
      if (response.ok) authUser.value = await response.json()
      else localStorage.removeItem('shellquest-session')
    } catch {
      // 保留匿名预览状态。
    }
  }
})
</script>

<template>
  <main class="app-shell">
    <header class="topbar">
      <button class="brand" aria-label="ShellQuest 首页" @click="selectTab('home')">
        <span class="brand-mark">$_</span>
        <span>ShellQuest</span>
      </button>
      <nav aria-label="主导航">
        <button :class="{ active: activeTab === 'home' }" @click="selectTab('home')">训练营</button>
        <button :class="{ active: activeTab === 'quests' }" @click="selectTab('quests')">自由闯关</button>
        <button :class="{ active: activeTab === 'search' }" @click="selectTab('search')">命令速查</button>
      </nav>
      <button class="profile" @click="showAuth = true"><span class="online-dot"></span>{{ authUser ? `${authUser.username}@quest` : '登录 / 注册' }}</button>
    </header>

    <section v-if="activeTab === 'home'" class="dashboard">
      <div class="hero-card grid-lines">
        <p class="eyebrow">21 个课程单元 · 自由加速完成</p>
        <h1>把 Linux 命令，<br /><em>练成实战直觉。</em></h1>
        <p class="hero-copy">不是背命令。你会在发布、故障与运维现场中，找到解决问题的正确组合。</p>
        <div class="hero-actions">
          <button class="primary" @click="selectTab('quests')">继续当前任务 <span>→</span></button>
          <button class="secondary" @click="selectTab('search')">查询命令</button>
        </div>
      </div>

      <aside class="progress-card">
        <p class="eyebrow">你的进度</p>
        <div class="level-row"><span class="level-badge">LV.01</span><strong>初级探索者</strong></div>
        <div class="meter"><span style="width: 18%"></span></div>
        <p class="muted">{{ authUser?.xp ?? 0 }} / 1,000 XP · 下一级还需 {{ 1000 - (authUser?.xp ?? 0) }} XP</p>
        <div class="streak"><span>⚡</span><div><strong>{{ authUser?.streak_days ?? 0 }} 天</strong><small>连续学习</small></div><button>打卡</button></div>
      </aside>

      <section class="skill-card panel">
        <div class="section-heading"><div><p class="eyebrow">技能树</p><h2>文件工坊 <span>01 / 04</span></h2></div><button class="text-button">查看全部 →</button></div>
        <div class="skill-path">
          <div class="skill done"><i>✓</i><span>初入服务器</span></div>
          <div class="link active-link"></div>
          <div class="skill current"><i>02</i><span>文件定位</span></div>
          <div class="link"></div>
          <div class="skill"><i>03</i><span>安全备份</span></div>
          <div class="link"></div>
          <div class="skill"><i>04</i><span>文本追踪</span></div>
        </div>
      </section>

      <section class="mission-card panel">
        <div class="mission-meta"><span class="chip">当前任务</span><span>文件工坊 / 02</span><span class="xp">+120 XP</span></div>
        <h2>{{ activeQuest.title }}</h2>
        <p>{{ activeQuest.description }}</p>
        <button class="primary compact" @click="selectTab('quests')">进入任务 →</button>
      </section>
    </section>

    <section v-else-if="activeTab === 'quests'" class="quest-layout">
      <aside class="quest-list panel">
        <p class="eyebrow">文件工坊 · 01 / 04</p>
        <button v-for="quest in quests" :key="quest.id" class="quest-item" :class="quest.status">
          <span>{{ quest.status === 'done' ? '✓' : String(quest.id).padStart(2, '0') }}</span>
          <div><strong>{{ quest.title }}</strong><small>{{ quest.command }}</small></div>
          <b v-if="quest.status === 'locked'">⌁</b>
        </button>
      </aside>
      <article class="task-panel panel">
        <div class="mission-meta"><span class="chip">场景任务</span><span>预计 5 分钟</span><span class="xp">+120 XP</span></div>
        <h1>配置文件失踪</h1>
        <p>新版本已解压到 <code>/srv/app/releases/2026-09-10</code>，但服务启动时提示找不到环境配置。请在不修改任何文件的前提下，定位该目录及其子目录中的 <code>.env</code> 文件。</p>
        <div class="context-box"><span>已知目录</span><pre>/srv/app/
├── releases/2026-09-10/
│   ├── api/
│   └── config/.env
└── shared/</pre></div>
        <p class="terminal-label">在模拟终端中输入命令</p>
        <div class="terminal">
          <div class="terminal-bar"><span></span><span></span><span></span><b>shellquest — simulated terminal</b></div>
          <div class="terminal-body"><p><i>quest@server</i>:<b>~</b>$ {{ terminalInput }}</p><p v-if="result === 'success'" class="success-text">/srv/app/releases/2026-09-10/config/.env</p><p v-if="result === 'error'" class="error-text">未找到目标。提示：需要递归查找文件名。</p></div>
          <form class="terminal-form" @submit.prevent="runCommand"><span>❯</span><input v-model="terminalInput" aria-label="输入 Linux 命令" autocomplete="off" /><button>运行</button></form>
        </div>
        <div v-if="result === 'success'" class="feedback success-feedback"><strong>{{ completionMessage || (authUser ? '正在保存进度…' : '演练完成 · 登录后可保存 XP') }}</strong><span><code>find /srv/app/releases/2026-09-10 -name ".env"</code> 会递归定位目标文件。</span></div>
        <div v-else-if="result === 'error'" class="feedback error-feedback"><strong>再试一次</strong><span>从给定发布目录开始搜索，并使用文件名条件。</span></div>
      </article>
    </section>

    <section v-else class="search-page panel">
      <p class="eyebrow">命令速查</p>
      <h1>描述问题，找到命令。</h1>
      <p>例如：查看 8080 端口被谁占用、统计日志中出现最多的 IP。</p>
      <label class="search-input"><span>⌕</span><input v-model="query" placeholder="输入命令或自然语言描述" /><kbd>Enter</kbd></label>
      <div class="command-result" v-if="query"><div><span class="chip">网络 / 端口</span><h2><code>ss -ltnp</code></h2><p>查看正在监听的 TCP 端口及其关联进程。</p></div><button class="secondary">查看详情 →</button></div>
      <div v-else class="search-suggestions"><span>推荐尝试</span><button>查看端口占用</button><button>实时查看日志</button><button>磁盘空间不足</button></div>
    </section>

    <div v-if="showAuth" class="modal-backdrop" @click.self="showAuth = false">
      <form class="auth-modal panel" @submit.prevent="submitAuth">
        <button type="button" class="close" aria-label="关闭" @click="showAuth = false">×</button>
        <p class="eyebrow">账户</p>
        <h2>{{ authMode === 'login' ? '回到训练场' : '创建你的档案' }}</h2>
        <p>{{ authMode === 'login' ? '登录以同步你的进度与经验。' : '用户名仅包含字母、数字、下划线或连字符。' }}</p>
        <label>用户名<input v-model="credentials.username" required minlength="3" maxlength="32" /></label>
        <label>密码<input v-model="credentials.password" required type="password" minlength="8" /></label>
        <p v-if="authError" class="auth-error">{{ authError }}</p>
        <button class="primary" type="submit">{{ authMode === 'login' ? '登录' : '注册并开始' }} →</button>
        <button type="button" class="text-button auth-switch" @click="authMode = authMode === 'login' ? 'register' : 'login'; authError = ''">{{ authMode === 'login' ? '还没有账户？注册' : '已有账户？登录' }}</button>
      </form>
    </div>
  </main>
</template>
