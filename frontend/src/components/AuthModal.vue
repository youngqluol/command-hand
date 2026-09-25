<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

import { ApiError, isNetworkError } from '../api/client'
import { authenticate } from '../stores/session'
import { authModalOpen, authMode, closeAuth } from '../stores/ui'

/**
 * 登录 / 注册弹窗。
 *
 * 校验规则**照抄后端** `schemas.RegisterRequest`（用户名 3–32 位 `[A-Za-z0-9_-]`，密码 8–128 位），
 * 前端先拦一遍只是为了把错误直接落在输入框下方；真正的权威校验仍在服务端。
 * 表单加了 `novalidate`：浏览器原生的气泡提示没法做成行内文案，且样式不可控。
 */

const USERNAME_PATTERN = /^[a-zA-Z0-9_-]+$/
/** 焦点圈内可聚焦的元素。用于 Tab 环绕（见 `trapFocus`）。 */
const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])'

const credentials = ref({ username: '', password: '' })
const pending = ref(false)

/** 字段级错误。空串表示通过 —— 用空串而非 undefined，模板里可以直接当布尔用。 */
const fieldErrors = ref({ username: '', password: '' })
/** 服务端/网络类错误没有归属字段，单独占一行。 */
const formError = ref('')
/** 只有用户碰过的字段才报错：一打开弹窗就满屏红字很劝退。 */
const touched = ref({ username: false, password: false })

const usernameInput = ref<HTMLInputElement | null>(null)
const passwordInput = ref<HTMLInputElement | null>(null)
/** 弹窗面板本身。带 `tabindex="-1"`，打开时聚焦它把焦点移进弹窗。 */
const panel = ref<HTMLFormElement | null>(null)

const title = computed(() => (authMode.value === 'login' ? '回到训练场' : '创建你的档案'))
const subtitle = computed(() =>
  authMode.value === 'login' ? '登录以同步你的进度与经验。' : '只需用户名和密码，进度保存在你自己的账户里。',
)

/** 校验通过时输入框下方显示的要求；不通过时被错误文案顶掉。 */
const usernameHint = computed(() =>
  authMode.value === 'login' ? '3–32 位字母、数字、下划线或连字符' : '3–32 位，可用字母、数字、下划线、连字符',
)
const passwordHint = computed(() => (authMode.value === 'login' ? '至少 8 位' : '至少 8 位，建议混合大小写与数字'))

function validateUsername(value: string): string {
  if (!value) return '请输入用户名'
  if (value.length < 3) return '用户名至少 3 个字符'
  if (value.length > 32) return '用户名最多 32 个字符'
  if (!USERNAME_PATTERN.test(value)) return '只能使用字母、数字、下划线或连字符'
  return ''
}

function validatePassword(value: string): string {
  if (!value) return '请输入密码'
  if (value.length < 8) return '密码至少 8 个字符'
  if (value.length > 128) return '密码最多 128 个字符'
  return ''
}

function validateField(field: 'username' | 'password'): void {
  fieldErrors.value[field] =
    field === 'username' ? validateUsername(credentials.value.username) : validatePassword(credentials.value.password)
}

function resetValidation(): void {
  fieldErrors.value = { username: '', password: '' }
  formError.value = ''
  touched.value = { username: false, password: false }
}

/** 失焦即校验一次；之后每次输入实时复验，用户改对了红字立刻消失。 */
function onBlur(field: 'username' | 'password'): void {
  touched.value[field] = true
  validateField(field)
}

function onInput(field: 'username' | 'password'): void {
  if (touched.value[field]) validateField(field)
}

/** 登录 ⇄ 注册。切换时清掉上一模式留下的红字，否则会显示与当前模式无关的错误。 */
function switchMode(): void {
  authMode.value = authMode.value === 'login' ? 'register' : 'login'
  resetValidation()
}

/* ---------------------------------------------------------------------- */
/* 弹窗交互：锁定背景滚动 / ESC 关闭 / 焦点圈在弹窗内                       */
/* ---------------------------------------------------------------------- */

/** 打开前的 body 内联样式，关闭时原样还原。 */
let previousBodyOverflow = ''
let previousBodyPaddingRight = ''

/**
 * 锁定背景滚动。
 *
 * `body { overflow: hidden }` 会被规范提升到视口（`html` 的 overflow 是 visible），
 * 所以视口不再滚动、但 `body` 自身的 used value 仍是 visible —— `position: sticky`
 * 的顶栏因此不受影响，滚动位置也不会丢。
 *
 * 滚动条消失会让整页宽度变化、内容左右跳一下，所以补一段 `padding-right`
 * 抵掉滚动条宽度（只有桌面端有经典滚动条，移动端这个值是 0）。
 */
function lockScroll(): void {
  const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth
  previousBodyOverflow = document.body.style.overflow
  previousBodyPaddingRight = document.body.style.paddingRight
  document.body.style.overflow = 'hidden'
  if (scrollbarWidth > 0) document.body.style.paddingRight = `${scrollbarWidth}px`
}

function unlockScroll(): void {
  document.body.style.overflow = previousBodyOverflow
  document.body.style.paddingRight = previousBodyPaddingRight
}

/**
 * 把 Tab 焦点圈在弹窗里。不做的话焦点会跑到弹窗**背后**的页面上 ——
 * 键盘用户看不见自己焦点在哪，回车还可能触发到背后的链接。
 * 只在首尾补环绕，中间交给浏览器默认行为。
 */
function trapFocus(event: KeyboardEvent): void {
  const scope = panel.value
  if (!scope) return
  const items = [...scope.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.getClientRects().length > 0)
  if (!items.length) return
  const first = items[0]
  const last = items[items.length - 1]
  const active = document.activeElement
  const inside = scope.contains(active)
  if (event.shiftKey) {
    if (active === first || !inside) {
      event.preventDefault()
      last.focus()
    }
  } else if (active === last || !inside) {
    event.preventDefault()
    first.focus()
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.preventDefault()
    closeAuth()
    return
  }
  if (event.key === 'Tab') trapFocus(event)
}

// 关掉弹窗就清掉残留的错误与输入，避免下次打开还显示上一次的报错。
watch(authModalOpen, (open) => {
  if (open) {
    window.addEventListener('keydown', onKeydown)
    lockScroll()
    // 聚焦面板而不是第一个输入框：移动端聚焦输入框会立刻弹出软键盘，把半屏内容挡掉。
    // 面板带 tabindex="-1"，聚焦后按 Tab 会落到关闭按钮，再往后就是输入框。
    void nextTick(() => panel.value?.focus())
    return
  }
  window.removeEventListener('keydown', onKeydown)
  unlockScroll()
  resetValidation()
  credentials.value = { username: '', password: '' }
})

// 弹窗组件常驻在 App.vue，正常不会卸载；这里只为「带锁卸载」兜底。
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  unlockScroll()
})

/* ---------------------------------------------------------------------- */
/* 提交                                                                    */
/* ---------------------------------------------------------------------- */

/** 把焦点挪到第一个出错的输入框，键盘用户不用自己找错在哪。 */
async function focusFirstInvalid(): Promise<void> {
  // 必须等 DOM 更新完，否则读到的还是上一次渲染的 fieldErrors。
  await nextTick()
  if (fieldErrors.value.username) usernameInput.value?.focus()
  else if (fieldErrors.value.password) passwordInput.value?.focus()
}

/** 服务端错误落到对应输入框：409 是用户名被占，401 是密码不对，其余（网络/5xx）放表单级。 */
function routeServerError(err: unknown): void {
  if (isNetworkError(err)) {
    formError.value = '无法连接到 API 服务，请确认后端已启动。'
    return
  }
  const status = err instanceof ApiError ? err.status : 0
  if (status === 409) {
    touched.value.username = true
    fieldErrors.value.username = (err as Error).message
    return
  }
  if (status === 401) {
    touched.value.password = true
    fieldErrors.value.password = (err as Error).message
    return
  }
  formError.value = (err as Error).message
}

async function submit(): Promise<void> {
  formError.value = ''
  touched.value = { username: true, password: true }
  validateField('username')
  validateField('password')
  if (fieldErrors.value.username || fieldErrors.value.password) {
    await focusFirstInvalid()
    return
  }

  pending.value = true
  try {
    await authenticate(authMode.value, credentials.value)
    closeAuth()
  } catch (err) {
    routeServerError(err)
    // 服务端把错误归到某个字段时，同样要聚焦 —— 否则用户只看到红字却不知道光标该去哪。
    await focusFirstInvalid()
  } finally {
    pending.value = false
  }
}
</script>

<template>
  <Transition name="modal">
    <div v-if="authModalOpen" class="modal-backdrop" @click.self="closeAuth">
      <!--
        role="dialog" 直接放在 <form> 上，而不是再加一层 wrapper：多一层会打断
        `.modal-backdrop` 的 grid 居中与 `.auth-modal` 的 `width: min(100%, 390px)` 取值链。
        `aria-labelledby` 指向标题，读屏会先念「回到训练场，对话框」。
      -->
      <form
        ref="panel"
        class="auth-modal panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-modal-title"
        tabindex="-1"
        novalidate
        @submit.prevent="submit"
      >
        <button type="button" class="close" aria-label="关闭" @click="closeAuth">×</button>
        <p class="eyebrow">账户</p>
        <h2 id="auth-modal-title">{{ title }}</h2>
        <p class="auth-subtitle">{{ subtitle }}</p>

        <label class="auth-field">
          <span>用户名</span>
          <input
            ref="usernameInput"
            v-model="credentials.username"
            :class="{ invalid: Boolean(fieldErrors.username) }"
            :aria-invalid="Boolean(fieldErrors.username)"
            aria-describedby="auth-username-hint"
            autocomplete="username"
            maxlength="32"
            placeholder="例如 linus"
            @blur="onBlur('username')"
            @input="onInput('username')"
          />
          <small
            id="auth-username-hint"
            class="auth-field-hint"
            :class="{ error: Boolean(fieldErrors.username) }"
            role="status"
          >
            {{ fieldErrors.username || usernameHint }}
          </small>
        </label>

        <label class="auth-field">
          <span>密码</span>
          <input
            ref="passwordInput"
            v-model="credentials.password"
            type="password"
            :class="{ invalid: Boolean(fieldErrors.password) }"
            :aria-invalid="Boolean(fieldErrors.password)"
            aria-describedby="auth-password-hint"
            :autocomplete="authMode === 'login' ? 'current-password' : 'new-password'"
            maxlength="128"
            placeholder="至少 8 位"
            @blur="onBlur('password')"
            @input="onInput('password')"
          />
          <small
            id="auth-password-hint"
            class="auth-field-hint"
            :class="{ error: Boolean(fieldErrors.password) }"
            role="status"
          >
            {{ fieldErrors.password || passwordHint }}
          </small>
        </label>

        <p v-if="formError" class="auth-error" role="alert">{{ formError }}</p>

        <button class="primary" type="submit" :disabled="pending">
          {{ pending ? '处理中…' : authMode === 'login' ? '登录' : '注册并开始' }} →
        </button>
        <button type="button" class="text-button auth-switch" @click="switchMode">
          {{ authMode === 'login' ? '还没有账户？注册' : '已有账户？登录' }}
        </button>
      </form>
    </div>
  </Transition>
</template>
