/**
 * Markdown 渲染。用于课程单元的 `knowledge` 与命令手册的 `body_markdown` / 章节内容。
 *
 * 内容有两个来源：我们自己撰写的 `curriculum/`，以及上游 `jaywcjlove/linux-command` 的原文。
 * 后者不是完全可信的（Markdown 允许内联 HTML），因此**必须**过一遍 DOMPurify。
 *
 * 渲染结果交给 `v-html`，`MarkdownBlock.vue` 里对 `vue/no-v-html` 做了行内豁免 —— 见该文件注释。
 */

import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({
  html: true,
  linkify: true,
  breaks: false,
})

// 外链一律新开标签页，避免用户点进上游文档后回不来。
const defaultLinkOpen =
  md.renderer.rules.link_open ?? ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))

md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const targetIndex = tokens[idx].attrIndex('target')
  if (targetIndex < 0) tokens[idx].attrPush(['target', '_blank'])
  else tokens[idx].attrs![targetIndex][1] = '_blank'

  const relIndex = tokens[idx].attrIndex('rel')
  if (relIndex < 0) tokens[idx].attrPush(['rel', 'noopener noreferrer'])
  else tokens[idx].attrs![relIndex][1] = 'noopener noreferrer'

  return defaultLinkOpen(tokens, idx, options, env, self)
}

/** Markdown 源码 → 已净化的 HTML 字符串。 */
export function renderMarkdown(source: string): string {
  if (!source) return ''
  return DOMPurify.sanitize(md.render(source), { ADD_ATTR: ['target'] })
}
