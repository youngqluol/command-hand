/**
 * 接口类型，与后端 `app/schemas.py` 一一对应。
 *
 * 改后端字段时**必须同步这里**（AGENTS.md §12.1）。命名保持与后端一致的下划线风格，
 * 这样从响应体直接赋值不需要任何转换，也便于比对。
 */

export type QuestStatus = 'done' | 'current' | 'locked'
export type UnitStatus = 'done' | 'current' | 'locked'
export type QuestKind = 'terminal' | 'fill' | 'choice' | 'judge'

export type UserSummary = {
  id: number
  username: string
  xp: number
  streak_days: number
  created_at: string
  level: number
  level_title: string
  level_xp_earned: number
  level_xp_total: number
}

export type AuthResponse = {
  token: string
  user: UserSummary
}

export type QuestOption = {
  key: string
  text: string
}

export type Quest = {
  id: number
  order: number
  unit_id: number
  unit_order: number
  zone: string
  kind: QuestKind
  title: string
  scenario: string
  context: string
  prompt: string
  difficulty: number
  xp_reward: number
  options: QuestOption[]
  commands: string[]
  /** 未登录时为 null */
  status: QuestStatus | null
}

export type Unit = {
  id: number
  order: number
  zone: string
  title: string
  goal: string
  knowledge: string
  quest_count: number
  completed_quests: number
  xp_total: number
  /** 未登录时为 null */
  status: UnitStatus | null
  quests: Quest[]
}

export type SubmitResponse = {
  correct: boolean
  already_completed: boolean
  xp_awarded: number
  unit_completed: boolean
  /** 正确答案的展示形式，仅在提交后下发 */
  expected_display: string
  correct_keys: string[]
  explanation: string
  pitfalls: string
  safer_alt: string
  user: UserSummary
  /** 本次作答新解锁的成就，可能为空 */
  achievements: AchievementUnlock[]
}

export type UserProgress = {
  user: UserSummary
  total_units: number
  completed_units: number
  total_quests: number
  completed_quests: number
  completion_percent: number
  current_unit_id: number | null
  units: Unit[]
}

export type CheckInStatus = {
  today_checked_in: boolean
  streak_days: number
  last_checkin_date: string | null
  consecutive_dates: string[]
}

export type CheckInResponse = {
  already_checked_in: boolean
  xp_awarded: number
  status: CheckInStatus
  user: UserSummary
  /** 本次打卡新解锁的成就，可能为空 */
  achievements: AchievementUnlock[]
}

export type SkillNode = {
  unit_id: number
  index: number
  title: string
  unlocked: boolean
  unlocked_at: string | null
}

export type SkillZone = {
  zone: string
  zone_index: number
  total_nodes: number
  unlocked_nodes: number
  unlocked_percent: number
  nodes: SkillNode[]
}

export type SkillTree = {
  total_nodes: number
  unlocked_nodes: number
  total_percent: number
  zones: SkillZone[]
}

// --------------------------------------------------------------------------- //
// 成就与排行榜（REQUIREMENTS.md §4.3 / §4.5）
// --------------------------------------------------------------------------- //

/** 作答 / 打卡响应里回传的新解锁成就，用于弹提示。 */
export type AchievementUnlock = {
  code: string
  title: string
  description: string
  icon: string
  group: string
}

export type AchievementProgress = {
  current: number
  target: number
}

export type AchievementItem = {
  code: string
  title: string
  description: string
  icon: string
  group: string
  unlocked: boolean
  unlocked_at: string | null
  /** 无法量化的规则为 null */
  progress: AchievementProgress | null
}

export type AchievementGroup = {
  group: string
  total: number
  unlocked: number
  items: AchievementItem[]
}

export type AchievementList = {
  total: number
  unlocked: number
  unlocked_percent: number
  groups: AchievementGroup[]
}

export type LeaderboardEntry = {
  rank: number
  username: string
  level: number
  level_title: string
  xp: number
  streak_days: number
  is_me: boolean
}

export type Leaderboard = {
  total_users: number
  entries: LeaderboardEntry[]
  /** 未登录时为 null */
  me: LeaderboardEntry | null
}

// --------------------------------------------------------------------------- //
// 命令查询（REQUIREMENTS.md §4.4）
// --------------------------------------------------------------------------- //

export type CommandListItem = {
  name: string
  summary: string
  category: string
  tags: string[]
}

export type CommandSection = {
  title: string
  /** 用于按 4.4.5 的顺序排版；`extra` 表示未识别的标题 */
  role: string
  level: number
  content: string
}

export type CommandOption = {
  flag: string
  desc: string
  group: string | null
}

export type CommandExample = {
  description: string
  code: string
}

export type RelatedQuest = {
  unit_id: number
  unit_order: number
  zone: string
  unit_title: string
  quest_id: number
  quest_order: number
  quest_title: string
  quest_kind: QuestKind
}

export type CommandDetail = CommandListItem & {
  syntax: string | null
  sections: CommandSection[]
  options: CommandOption[] | null
  examples: CommandExample[] | null
  body_markdown: string
  source_url: string
  license: string
  source_version: string
  related_commands: CommandListItem[]
  related_quests: RelatedQuest[]
}

export type CommandPage = {
  total: number
  page: number
  page_size: number
  items: CommandListItem[]
}

export type CommandFacets = {
  total: number
  categories: Array<{ category: string; count: number }>
  tags: Array<{ tag: string; count: number }>
  letters: Array<{ letter: string; count: number }>
}

export type CommandSearchHit = {
  command: CommandListItem
  score: number
  matched_field: string
  snippet: string
  related_quests: RelatedQuest[]
}

export type CommandSearchResult = {
  mode: 'keyword' | 'natural'
  query: string
  total: number
  hits: CommandSearchHit[]
  suggestions: string[]
}
