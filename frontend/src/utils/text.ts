/**
 * 课程内容里的轻量 Markdown 处理。
 *
 * 题目 `prompt` / `scenario` 里含行内 `` `code` `` 与 `**粗体**`，`context` 里含 ``` 围栏。
 *
 * 这里**不生成 HTML 字符串**，而是解析成片段数组交给 `v-for` 渲染 ——
 * 既能避免 `v-html` 的 XSS 风险，也不用为了它去禁用 lint 规则。
 */

export type InlineSegment = {
  text: string
  code: boolean
  bold: boolean
}

const INLINE_PATTERN = /`([^`]+)`|\*\*([^*]+)\*\*/g

/** 把行内 Markdown 拆成普通文本 / 行内代码 / 粗体三种片段。 */
export function parseInline(text: string): InlineSegment[] {
  const segments: InlineSegment[] = []
  let cursor = 0
  let match: RegExpExecArray | null

  INLINE_PATTERN.lastIndex = 0
  while ((match = INLINE_PATTERN.exec(text)) !== null) {
    if (match.index > cursor) {
      segments.push({ text: text.slice(cursor, match.index), code: false, bold: false })
    }
    const isCode = match[1] !== undefined
    segments.push({ text: match[1] ?? match[2] ?? '', code: isCode, bold: !isCode })
    cursor = match.index + match[0].length
  }

  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor), code: false, bold: false })
  }
  return segments
}

/** 去掉 ``` 围栏行，只保留代码内容。 */
export function unfence(text: string): string {
  return text
    .split('\n')
    .filter((line) => !/^\s*```/.test(line))
    .join('\n')
    .trim()
}
