<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { isNetworkError, request } from '../api/client'
import { applySubmitResult, isLoggedIn } from '../stores/session'
import { openAuth } from '../stores/ui'
import type { Quest, QuestKind, SubmitResponse } from '../types'
import { unfence } from '../utils/text'
import InlineText from './InlineText.vue'

const props = defineProps<{ quest: Quest }>()
const emit = defineEmits<{ (e: 'solved', payload: SubmitResponse): void }>()

const KIND_LABEL: Record<QuestKind, string> = {
  terminal: '模拟终端',
  fill: '补全命令',
  choice: '单选题',
  judge: '判断题',
}

const textAnswer = ref('')
const pickedKeys = ref<string[]>([])
const result = ref<SubmitResponse | null>(null)
const error = ref('')
const pending = ref(false)

/** terminal / fill 用文本作答，choice / judge 用选项作答（后端约定，见 schemas.SubmitRequest）。 */
const isTextKind = computed(() => props.quest.kind === 'terminal' || props.quest.kind === 'fill')
const canSubmit = computed(() => (isTextKind.value ? textAnswer.value.trim().length > 0 : pickedKeys.value.length > 0))
const contextText = computed(() => unfence(props.quest.context ?? ''))
const alreadyDone = computed(() => props.quest.status === 'done')

/** 参考答案与用户输入相同时不必再回显一遍（terminal 题常见），否则终端里会出现两行一样的内容。 */
const showsExpected = computed(() => {
  const expected = result.value?.expected_display?.trim()
  return Boolean(expected) && expected !== textAnswer.value.trim()
})

// 切到另一道题时必须清空作答与上一次的判题结果，否则会把上一题的答案带过去。
watch(
  () => props.quest.id,
  () => {
    textAnswer.value = ''
    pickedKeys.value = []
    result.value = null
    error.value = ''
  },
)

// 因未登录被拦下后，登录成功即清掉那条提示，用户可以直接重试。
watch(isLoggedIn, (loggedIn) => {
  if (loggedIn) error.value = ''
})

function pick(key: string): void {
  // choice / judge 目前全部为单选（14 + 13 题的 correct_keys 长度均为 1），故用单选交互。
  pickedKeys.value = [key]
  result.value = null
}

function optionClass(key: string): Record<string, boolean> {
  const judged = result.value
  return {
    picked: pickedKeys.value.includes(key),
    correct: Boolean(judged?.correct_keys?.includes(key)),
    wrong: Boolean(judged && pickedKeys.value.includes(key) && !judged.correct_keys?.includes(key)),
  }
}

async function submit(): Promise<void> {
  if (!canSubmit.value || pending.value) return

  // 判题在服务端（答案不下发），未登录无法提交。与其抛一个「请先登录」的报错，不如直接引导登录。
  if (!isLoggedIn.value) {
    error.value = '登录后即可提交作答并记录经验值。'
    openAuth('login')
    return
  }

  pending.value = true
  error.value = ''
  try {
    const payload = await request<SubmitResponse>(`/api/v1/quests/${props.quest.id}/submit`, {
      method: 'POST',
      body: isTextKind.value ? { answer: textAnswer.value } : { option_keys: pickedKeys.value },
    })
    result.value = payload
    if (payload.correct) {
      emit('solved', payload)
      await applySubmitResult(payload.user)
    }
  } catch (err) {
    error.value = isNetworkError(err) ? '无法连接到后端，作答未提交。' : (err as Error).message
  } finally {
    pending.value = false
  }
}

function retry(): void {
  result.value = null
  error.value = ''
}
</script>

<template>
  <article class="task-panel panel">
    <div class="mission-meta">
      <span class="chip">{{ KIND_LABEL[quest.kind] }}</span>
      <span>难度 {{ quest.difficulty }}</span>
      <span class="xp">+{{ quest.xp_reward }} XP</span>
      <span v-if="alreadyDone" class="chip done-chip">已完成</span>
    </div>

    <h1>{{ quest.title }}</h1>
    <p><InlineText :text="quest.scenario" /></p>

    <div v-if="contextText" class="context-box">
      <span>场景上下文</span>
      <pre>{{ contextText }}</pre>
    </div>

    <p class="quest-prompt"><InlineText :text="quest.prompt" /></p>

    <!-- terminal / fill：文本作答 -->
    <template v-if="isTextKind">
      <p class="terminal-label">
        {{ quest.kind === 'terminal' ? '在模拟终端中输入命令' : '填写完整命令（含命令名，判定会检查关键字）' }}
      </p>
      <div class="terminal">
        <div class="terminal-bar"><span></span><span></span><span></span><b>shellquest — simulated terminal</b></div>
        <div class="terminal-body">
          <p><i>quest@server</i>:<b>~</b>$ {{ textAnswer || ' ' }}</p>
          <template v-if="result">
            <p v-if="!result.correct" class="error-text">答案不完整，参考下面的提示再试一次。</p>
            <p v-else-if="showsExpected" class="success-text">{{ result.expected_display }}</p>
            <p v-else class="success-text">✓ 命令已执行</p>
          </template>
        </div>
        <form class="terminal-form" @submit.prevent="submit">
          <span>❯</span>
          <input
            v-model="textAnswer"
            aria-label="输入 Linux 命令"
            autocomplete="off"
            spellcheck="false"
            :placeholder="quest.kind === 'terminal' ? '输入命令后回车' : '例如：uname -r'"
          />
          <button :disabled="!canSubmit || pending">{{ pending ? '判定中…' : '运行' }}</button>
        </form>
      </div>
    </template>

    <!-- choice / judge：选项作答 -->
    <template v-else>
      <ul class="option-list">
        <li v-for="option in quest.options" :key="option.key">
          <button
            type="button"
            :class="['option-item', optionClass(option.key)]"
            :disabled="Boolean(result)"
            @click="pick(option.key)"
          >
            <span class="option-key">{{ option.key }}</span>
            <span class="option-text"><InlineText :text="option.text" /></span>
          </button>
        </li>
      </ul>
      <button v-if="!result" class="primary compact" :disabled="!canSubmit || pending" @click="submit">
        {{ pending ? '判定中…' : '提交答案' }}
      </button>
    </template>

    <p v-if="error" class="feedback error-feedback">{{ error }}</p>

    <div v-if="result" :class="['feedback', result.correct ? 'success-feedback' : 'error-feedback']">
      <strong>
        {{
          result.correct
            ? result.already_completed
              ? '回答正确 · 该题此前已完成，进度已保留'
              : `回答正确 · +${result.xp_awarded} XP${result.unit_completed ? ' · 单元通关 +60 XP' : ''}`
            : '回答不正确'
        }}
      </strong>
      <span v-if="!result.correct && result.expected_display">
        参考答案：<code>{{ result.expected_display }}</code>
      </span>
      <span v-if="result.explanation"><InlineText :text="result.explanation" /></span>
      <span v-if="result.pitfalls" class="feedback-extra"> ⚠ 常见坑：<InlineText :text="result.pitfalls" /> </span>
      <span v-if="result.safer_alt" class="feedback-extra">
        🛡 更稳的做法：<InlineText :text="result.safer_alt" />
      </span>
      <!-- 命令名对 terminal 题来说就是答案，所以只在答对后才给出跳转入口（REQUIREMENTS.md §4.4.8） -->
      <div v-if="result.correct && quest.commands.length" class="quest-commands">
        <span class="muted">涉及命令：</span>
        <RouterLink
          v-for="item in quest.commands"
          :key="item"
          class="filter-chip"
          :to="{ name: 'command-detail', params: { name: item } }"
        >
          {{ item }}
        </RouterLink>
      </div>
      <button v-if="!result.correct" class="secondary compact" @click="retry">再试一次</button>
    </div>
  </article>
</template>
