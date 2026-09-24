# AGENTS.md

给在此仓库中工作的 AI 编码代理的指南。人类贡献者同样适用。

---

## 0. 铁律（优先级高于本文其他所有约定）

以下四条规则适用于**每一次改动**，无例外。与其他章节冲突时，以本节为准。

### 0.1 每次改动都必须记录到相应文件

任何改动都必须落到仓库文件里。只存在于对话、临时脚本或某个人脑子里的改动，视为**未完成**。

改动类型与必须同步更新的文件的对应关系见 **第 12 节**。

自查标准：**一个只读仓库文件的新人，能否完整复现并理解这次改动？** 不能，就说明记录缺失。

### 0.2 项目更新后必须同步调整 AGENTS.md

`AGENTS.md` 是本仓库的**活文档**，不是一次性产物。它必须与代码**在同一次改动内**保持一致，不接受「先合代码，回头再补文档」。

出现下列任一情况时，必须在同一次改动中更新对应章节：

| 变化 | 需更新的章节 |
| --- | --- |
| 目录结构、文件职责变化 | §3 |
| 新增 / 删除 / 修改接口 | §4、§2 |
| 新增 / 修改数据模型、表、字段 | §4.4、§6 |
| 新增 / 修改课程单元、题目、题型、判题规则 | §4.4、§4.5、§4.7、`COURSE_DESIGN.md` |
| 业务规则调整（XP、等级、称号、解锁、打卡） | §4.5 |
| 前端工具链、目录约定、样式约定变化 | §5 |
| 依赖、启动方式、端口变化 | §2 |
| 某个「已知缺口」被补齐 | §7 —— **必须删除该条目** |
| 引入新的技术组件，或让既有组件真正生效 | §1 及相关章节 |
| 新增约定或禁止项 | §8、§10、§11 |

**若发现本文档描述与代码不符，以代码为准，并在同一次改动中修正本文档。**

### 0.3 前端必须集成 ESLint，代码规范、格式美观

- 前端**必须**配置 ESLint，保证 `pnpm run lint` 可执行且**零错误**。
- 提交前必须通过 lint 与类型检查，不得提交带 lint 错误的代码。
- 格式统一由工具决定，**不依赖人工审美**：缩进、引号、分号、行宽、尾随逗号、空行均按配置执行。
- 新增前端代码不得引入新的 lint 错误。确需豁免某条规则时，必须使用**行内** `// eslint-disable-next-line` 并注明原因；**禁止整文件 `/* eslint-disable */`**。
- 具体工具链、命令与规则集见 **第 5.6 节**。

### 0.4 前端只允许使用 pnpm

- 前端**只使用 pnpm** 管理依赖。**禁止**使用 npm、yarn、bun 安装或更新前端依赖。
- **禁止**在 `frontend/` 下产生 `package-lock.json`、`yarn.lock`、`bun.lockb` 等非 pnpm 锁文件。发现即删除。
- 唯一合法的锁文件是 `frontend/pnpm-lock.yaml`，且**必须提交**。
- 已通过 `preinstall` 钩子（`npx only-allow pnpm`）强制拦截误用；**不得移除该钩子**。
- 版本由 `package.json` 的 `packageManager` 字段锁定，通过 Corepack 生效；**修改它必须同时更新 Dockerfile 与本节**。
- 具体命令、Docker 构建方式与常见问题见 **第 5.7 节**。

---

## 1. 项目速览

**ShellQuest** — 面向全栈开发者与架构师的 21 天 Linux 命令实战训练 Web 应用。
以场景化任务闯关 + 技能树成长 + 命令速查为核心，深色终端风格。

- 前端：Vue 3 + TypeScript + Vite
- 后端：Python 3.13 + FastAPI + SQLAlchemy 2.0（同步 ORM）
- 数据库：MySQL 8.4（Docker 生产路径）/ SQLite（本地开发默认回退）
- 缓存：Redis 7 —— **仅在 compose 中声明，代码中完全未使用**
- 部署：Docker Compose

文档入口：`README.md`（启动方式）、`REQUIREMENTS.md`（MVP 需求）、`COURSE_DESIGN.md`（21 单元课程设计）。
**需求以 `REQUIREMENTS.md` 为准**；当代码与需求冲突时，先确认再改。

---

## 2. 常用命令

### 后端（工作目录 `backend/`）

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows；Linux/macOS 为 source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health
- 依赖变更请同时更新 `requirements.txt`；`requirements-dev.txt` 通过 `-r requirements.txt` 继承，只放开发期依赖（目前仅 `httpx`）。

改完 `curriculum/` 下的课程内容后，**先跑自检再启动服务**（自检失败时服务根本起不来，提前跑能看清报错）：

```bash
.venv/Scripts/python -c "from app.main import validate_curriculum; validate_curriculum()"
```

自检覆盖：`order` 连续性、区域名合法性、题型/判题器合法性、`judge_payload` 结构、
选择题选项与 `correct_keys` 的一致性、每题是否关联了命令。详见 §4.7。

### 前端（工作目录 `frontend/`）

**只使用 pnpm**（见 §0.4）。首次使用先启用 Corepack：`corepack enable`。

```bash
pnpm install
pnpm run dev           # http://localhost:5173，/api 代理到 localhost:8000
pnpm run build         # vue-tsc -b && vite build —— 类型检查 + 构建，提交前必过
pnpm run preview
pnpm run lint          # ESLint 检查，必须零错误（见 §0.3）
pnpm run lint:fix      # ESLint 检查并自动修复
pnpm run format        # Prettier 格式化全仓库
pnpm run format:check  # Prettier 检查格式，不写入
```

**提交前必须跑通 `pnpm run lint` 与 `pnpm run build`。** `build` 会先执行 `vue-tsc`，任何类型错误都会导致构建失败（历史上多次出现 `fix: 修复构建错误`）。

细节与常见问题见 §5.7。

### 全栈

```bash
docker compose up --build     # 前端 :8080，后端 :8000，MySQL :3306，Redis :6379
```

---

## 3. 目录结构与职责

```
backend/
  app/
    main.py        # 全部 HTTP 路由 + 判题引擎 + 课程落库 + 解锁算法 + 打卡逻辑
    models.py      # SQLAlchemy 模型，9 张表
    schemas.py     # Pydantic 请求/响应模型 + 等级、称号、经验进度计算
    database.py    # engine / SessionLocal / Base
    security.py    # scrypt 口令哈希与校验
    curriculum/    # 课程内容：21 个单元 / 63 道题，按主题区域分 6 个模块
      __init__.py      # 汇总 6 个区域模块为 UNITS，顺序必须与 ZONE_ORDER 一致
      zone_file.py     # 文件工坊     单元 01–04
      zone_system.py   # 系统哨站     单元 05–09
      zone_network.py  # 网络前线     单元 10–12
      zone_shell.py    # Shell 作战室 单元 13–16
      zone_container.py# 容器基地     单元 17–19
      zone_incident.py # 故障指挥中心 单元 20–21
  requirements.txt
  requirements-dev.txt
  shellquest.db    # 本地 SQLite（gitignore，勿提交）

frontend/
  src/
    App.vue        # 全部界面 + 全部业务逻辑（单文件，约 470 行）
    main.ts        # createApp 挂载
    styles.css     # 全局样式（深色终端风）
    vite-env.d.ts
  index.html
  nginx.conf       # 生产：静态托管 + /api 反代到 backend:8000
  Dockerfile       # 多阶段：corepack + pnpm 构建 → nginx 托管
  .dockerignore    # 排除 node_modules / dist（pnpm 的 node_modules 含符号链接）
  vite.config.ts   # dev 代理 /api → localhost:8000
  eslint.config.js     # ESLint flat config（见 §5.6）
  .prettierrc          # Prettier 格式配置
  .prettierignore      # Prettier 忽略清单
  pnpm-lock.yaml       # 唯一合法锁文件，必须提交（见 §5.7）
  pnpm-workspace.yaml  # pnpm 11 的配置载体：allowBuilds 等

.gitattributes     # 固定 LF，避免 autocrlf 干扰 format:check
```

**注意：`frontend/src/` 只有 4 个文件，没有组件拆分、没有 vue-router、没有 Pinia。** 仓库中显示的 1000+ 文件全部来自 `node_modules`。

---

## 4. 后端约定

### 4.1 路由注册方式

所有路由都用 `@app.get` / `@app.post` 直接装饰在 `main.py` 里，**没有 `APIRouter`、没有 `routers/` 目录**。新增接口请沿用此模式，保持单文件。

统一前缀 `/api/v1`，health 除外。

### 4.2 数据库会话

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

依赖注入用 `db: Session = Depends(get_db)`。

### 4.3 认证

**不是 JWT。** 服务端生成随机 token 落库，前端每次请求携带请求头：

```
X-Session-Token: <token>
```

- 签发：`create_session()` → `secrets.token_urlsafe(32)` → 写入 `user_sessions` 表
- 校验：`get_current_user()` 依赖，未登录/失效分别返回 401「请先登录」/「登录状态已失效」
- 前端存储：`localStorage['shellquest-session']`
- `user_sessions` **无过期时间、无登出接口**（已知缺口）

### 4.4 数据模型（`models.py`）

三层结构：**课程单元 → 题目 → 选项**。`CourseUnit` 是技能节点与解锁的基本单位，`Quest` 是单元下的一道题。
字段语义与题型定义见 `REQUIREMENTS.md` §4.1.2。

| 表 | 说明 | 关键约束 |
| --- | --- | --- |
| `users` | 用户 + `xp` / `streak_days` / `last_checkin_date` | `username` 唯一 |
| `course_units` | 课程单元（21 个），含 `zone` / `title` / `goal` / `knowledge` | `order` 唯一（1..21） |
| `quests` | 题目（63 道），含题型、场景、判题规则 | `order` 唯一（1..63），`unit_id` 外键 |
| `quest_options` | `choice` / `judge` 题型的选项 | `(quest_id, key)` 唯一 |
| `quest_commands` | 题目 ↔ 命令名的关联，供命令查询双向跳转 | `(quest_id, command_name)` 唯一 |
| `quest_completions` | 完成记录 | `(user_id, quest_id)` 唯一 |
| `user_sessions` | 登录会话 | `token` 唯一 |
| `check_ins` | 每日打卡 | `(user_id, checkin_date)` 唯一 |
| `skill_progress` | 技能节点点亮，**绑定课程单元** | `(user_id, unit_id)` 唯一 |

`quests.judge_payload` 是 `JSON` 列，其结构由 `judge_type` 决定：

| `judge_type` | `judge_payload` 结构 |
| --- | --- |
| `contains_all` / `contains_any` | `{"terms": ["...", "..."]}` |
| `equals` | `{"value": "..."}` |
| `regex` | `{"pattern": "..."}` |
| `option` | `{"correct_keys": ["A"]}` |

⚠️ **JSON 列不跟踪原地修改。** 更新 `judge_payload` 必须整体赋新 dict（`quest.judge_payload = {...}`），
写 `quest.judge_payload["terms"] = [...]` 不会落库。

### 4.5 关键业务规则（改动前务必理解）

**单元解锁** — `compute_unit_statuses()`：

- 按 `CourseUnit.order` 升序**严格串行**推进：单元 N 解锁 ⟺ 单元 1..N-1 全部完成。
- 全部题目完成 → `done`；第一个未完成的单元 → `current`；其余 → `locked`。
- 全局同一时刻**只有一个** `status == "current"` 的单元。
- 状态枚举：`Literal["done", "current", "locked"]`（定义在 `schemas.py`）。

**题目状态** — `compute_quest_statuses()`：

- 已完成的题 → `done`（即使它所在单元已不是 `current`，历史完成记录依然显示为已完成）。
- 当前单元内未完成的题 → `current`（**同一单元内的题可以任意顺序作答**）。
- 锁定单元内的题 → `locked`。
- `POST /api/v1/quests/{id}/submit` 会再次校验，对 `locked` 单元返回 403「该课程单元尚未解锁」。

**判题引擎** — `judge_answer()`，支持 5 种判题器：

| `judge_type` | 规则 |
| --- | --- |
| `contains_all` | 归一化后，所有 `terms` 都必须出现 |
| `contains_any` | 归一化后，任一 `terms` 出现即可 |
| `regex` | 归一化后，`re.search(pattern, text, re.IGNORECASE)` 命中 |
| `equals` | 归一化后完全相等 |
| `option` | 提交的 `option_keys` 集合与 `correct_keys` **完全一致**（大小写不敏感） |

`normalize_answer()` 的归一化步骤（用户输入与标准答案走同一套）：去首尾空白 → 去常见提示符前缀
（`$` / `#` / `>` / `PS...>`）→ 统一弯引号与反引号为半角 → 折叠连续空白 → 转小写。
**这就是为什么 `$ whoami && pwd` 与 `whoami && pwd` 判为同一个答案。**

⚠️ **`contains_all` 不是「包含答案字符串」，而是「包含若干关键词」。** 关键词之间是 AND 关系，
但**不校验顺序、不校验参数个数**。例如 `terms: ["find", ".env"]` 会接受 `find /x -name .env`，
也会接受 `echo find .env`。这是刻意的取舍（见 `REQUIREMENTS.md` §4.1.2「判题边界」），
需要严格匹配时改用 `regex` 或 `equals`。

**经验值**

| 行为 | XP | 定义位置 |
| --- | --- | --- |
| 完成一道题 | `quest.xp_reward`（20 / 40 两档，随难度） | 逐题声明在 `curriculum/` 中 |
| 完成整个单元 | 60 | `main.py` 的 `UNIT_COMPLETION_BONUS` |
| 每日打卡 | 30 | `main.py` 的 `DAILY_CHECKIN_XP` |
| 升级阈值 | 1000 | `schemas.py` 的 `XP_PER_LEVEL` |

重复提交同一道题**不重复给经验**，返回 `already_completed=true, xp_awarded=0`（但依然返回答案与解析）。
首次答对时会**顺带自动打卡**（若当日未打卡）。

**等级与称号** — `schemas.py`：`level = xp // 1000 + 1`，称号 4 档：初级探索者(1-3) / 中级执令者(4-6) / 高级指挥官(7-9) / 传奇 ShellMaster(10+)。等级相关字段通过 Pydantic `@computed_field` 计算，**不在数据库中存储**。

**技能树** — `build_skill_tree()`：按 `ZONE_ORDER` 的 6 个区域聚合，每个区域内的节点索引 = 该区域内单元按 `order` 排序后的下标。节点在**单元全部完成**时点亮（`grant_skill_if_unit_done()`）。
`ZONE_ORDER` 之外的区域会被追加到末尾而非丢弃。

### 4.6 区域常量必须三处同步

```python
# main.py
ZONE_ORDER = ["文件工坊", "系统哨站", "网络前线", "Shell 作战室", "容器基地", "故障指挥中心"]
```

这 6 个字符串**必须与 `curriculum/` 中每个单元声明的 `zone` 字面量完全一致**（含全角/半角空格），
且 `curriculum/__init__.py` 的模块拼接顺序必须与 `ZONE_ORDER` 一致。

`validate_curriculum()` 会在启动时校验「单元的 `zone` 是否属于 `ZONE_ORDER`」并**直接抛错**，
因此**拼错区域名不会再静默消失**，而是服务启动失败。但**区域之间的相对顺序**无法自动校验，
调整顺序时仍需人工确认 `ZONE_ORDER` 与 `__init__.py` 同步。

### 4.7 课程内容与落库

课程内容全部在 `app/curriculum/`，**`main.py` 与任何其他文件都不硬编码题目**。

启动流程（`lifespan`）：

1. `validate_curriculum()` —— 自检数据。任何一处不合法就 `RuntimeError`，**服务起不来**。
2. `Base.metadata.create_all()` —— 只建缺失的表。
3. `seed_curriculum()` —— 以 `order` 为稳定键做**幂等 UPSERT**。

**`seed_curriculum()` 的行为（与旧的 `seed_quests()` 完全不同，务必注意）**

- 内容没变 → **完全不写库**（逐字段比对，包括选项与命令关联），启动是无副作用的。
- 内容变了 → 只更新变化的那道题的标量字段，并**重建它的选项与命令关联**。
- **用户进度不会丢**：`quest_completions` / `skill_progress` 按 `id` 关联，而 `id` 由 `order` 稳定推导，不随内容更新变化。

因此**修改 `curriculum/` 下的内容后，重启服务即可生效**，不再需要删库。
只有在**增删单元或题目导致 `order` 整体位移**时才需要重建数据库（历史完成记录会错位）。

单元种子结构（每个区域模块导出一个 `UNITS` 列表）：

```python
{
    "order": 1, "zone": "文件工坊", "title": "...", "goal": "...", "knowledge": "...(Markdown)",
    "quests": [
        {
            "kind": "terminal",              # terminal | fill | choice | judge
            "title": "...", "scenario": "...", "context": "```text ... ```", "prompt": "...",
            "answer_display": "...",         # 仅用于提交后展示，列表接口不下发
            "judge_type": "contains_all", "judge_payload": {"terms": [...]},
            "explanation": "...", "pitfalls": "...", "safer_alt": "...",
            "difficulty": 1, "xp_reward": 40,
            "commands": ["whoami", "pwd"],   # 必须非空，否则校验失败
            "options": [],                   # choice / judge 题型才非空
        },
    ],
}
```

**题目的 `order` 由列表位置自动推导（全局连续 1..63），种子数据里不写 `order`。**
在列表中间插入题目会导致其后所有题目的 `order` 位移，进而使历史完成记录错位 —— 优先追加到末尾。

---

## 5. 前端约定

### 5.1 API 调用

```ts
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '') || ''
```

- 开发：`API_BASE` 为空 → 相对路径 `/api/...` → Vite 代理到 `localhost:8000`
- 生产：nginx 反代 `/api/` 到 `backend:8000`
- 全部使用原生 `fetch`，**没有 axios**。错误处理为 `try/catch` + `console.warn`。

### 5.2 类型定义

所有接口类型（`Quest` / `UserSummary` / `CheckInStatusType` / `SkillTreeType` 等）**定义在 `App.vue` 的 `<script setup>` 顶部**，不使用 `.d.ts` 或独立 `types/` 目录。

### 5.3 状态管理

全部使用 `ref` / `computed`，**无 Pinia、无 Vuex**。登录态在 `onMounted` 中通过 `/api/v1/auth/me` 恢复。

### 5.4 降级策略（重要）

前端在 API 不可用时**不会崩溃**，而是使用本地兜底数据：

- `fallbackQuests`：3 条演示任务
- `DEFAULT_LEVEL`：guest 用户（0 XP / LV.01）
- `apiUnavailable` ref 控制顶部橙色告警条

**新增功能时请沿用此降级模式**，不要引入「白屏」失败态。

### 5.5 样式

- 全局样式集中在 `styles.css`，**没有 CSS Modules、没有 Tailwind、没有 scoped style**。
- 主题为**深色终端风**，主色 `#70e09b`（终端绿），背景 `#090e13`。
- 字体：`IBM Plex Sans`（正文）+ `DM Mono`（等宽/命令），通过 Google Fonts `@import` 引入。
- 响应式断点：`@media (max-width: 720px)`。
- 格式由 Prettier 统一维护（见 §5.6），**不要手工调整缩进或换行**。

### 5.6 代码质量与格式（ESLint + Prettier）

**前端必须集成 ESLint。** 这是硬性要求，不是可选项（见 §0.3）。**当前已接入**，配置如下。

**已接入的工具链**

| 用途 | 工具 | 配置文件 |
| --- | --- | --- |
| 代码检查 | `eslint` + `eslint-plugin-vue` + `typescript-eslint` | `frontend/eslint.config.js`（flat config） |
| 格式统一 | `prettier` + `eslint-config-prettier` | `frontend/.prettierrc.json`、`frontend/.prettierignore` |

不使用已废弃的 `.eslintrc.*`。`eslint-config-prettier` 必须位于配置数组**最后一项**，用于关闭与 Prettier 冲突的风格规则。

**脚本**（用 pnpm 执行，见 §5.7）

```bash
pnpm run lint          # 检查，不自动修复
pnpm run lint:fix      # 检查并自动修复
pnpm run format        # Prettier 格式化全仓库
pnpm run format:check  # Prettier 检查格式，不写入
```

**格式基线（由 `.prettierrc.json` 强制执行）**

```json
{
  "semi": false,
  "singleQuote": true,
  "printWidth": 120,
  "tabWidth": 2,
  "trailingComma": "all",
  "arrowParens": "always",
  "endOfLine": "lf"
}
```

**项目自定义规则（`eslint.config.js` 中显式设置的部分）**

- `no-console`: `warn`，但允许 `console.warn` / `console.error` —— 前端降级路径依赖它们输出诊断信息（见 §5.4）。
- `no-undef`: 对 `.vue` 关闭。`.vue` 的 `<script setup lang="ts">` 由 TypeScript 负责未定义标识符检查，避免与 ESLint 重复误报。
- `vue/multi-word-component-names`: 忽略 `App`。`App.vue` 是根组件，属于该规则的公认例外。
- `.vue` 的 `parserOptions.parser` 指向 `typescript-eslint` 的 parser，以正确解析 `<script setup lang="ts">`。

**要求**

1. `pnpm run lint` 必须**零错误**；`pnpm run build` 必须同时通过类型检查（`vue-tsc`）与构建（`vite build`）。两者都不通过不得提交。
2. 新增代码不得引入新的 lint 错误。确需豁免时使用**行内** `// eslint-disable-next-line` 并注明原因；**禁止整文件 `/* eslint-disable */`**。
3. 不得为了让 lint 通过而降低规则等级或添加全局豁免 —— 应修正代码本身。
4. 调整规则集或格式配置属于影响全仓库的改动，需在提交说明中写明理由。
5. 变更工具链后必须同步更新本节、§2 与 §7。

**已知限制（务必注意）**

Prettier 会重排 Vue 模板中的内联事件处理器。若属性值包含**多条语句**：

```html
<!-- 危险：Prettier 会把它拆成多行，丢失语句分隔符 -->
<button @click="authMode = 'register'; authError = ''">切换</button>
```

格式化后会变成两个没有分隔符的表达式，Vue 模板编译直接报 `Unexpected token`，**构建失败**。

**因此：内联事件处理器只允许单条语句。** 需要多条语句时，抽成 `<script setup>` 中的方法：

```html
<button @click="switchAuthMode">切换</button>
```

**历史说明**

存量代码已于接入时**全量格式化并单独提交**，未与功能改动混合。后续新增或修改文件请直接依赖 `pnpm run format`，不要手工调整格式。

### 5.7 包管理器（pnpm 唯一）

**前端只使用 pnpm**（见 §0.4）。锁定版本见 `package.json` 的 `packageManager` 字段。

**强制机制**

| 机制 | 位置 | 作用 |
| --- | --- | --- |
| `packageManager` | `package.json` | 经 Corepack 锁定 pnpm 版本 |
| `preinstall` | `package.json` | `npx only-allow pnpm`，拦截 npm / yarn / bun |
| `engines` | `package.json` | 声明 node ≥ 20、pnpm ≥ 11 |

`packageManager` 与 Dockerfile 中的 pnpm 版本**必须一致**，改一处要改另一处。

**唯一合法锁文件**

`frontend/pnpm-lock.yaml`，**必须提交**。以下文件一旦出现即为误用，应删除：

- `package-lock.json`（npm）
- `yarn.lock`（yarn）
- `bun.lockb`（bun）

`pnpm-lock.yaml` 已加入 `.prettierignore`，**不要对其运行格式化**。

**pnpm-workspace.yaml**

pnpm 11 把部分配置放在 `pnpm-workspace.yaml` 而非 `package.json`。当前包含：

- `allowBuilds.esbuild: true` —— **必需**。pnpm 默认禁止依赖执行安装脚本；不放开 esbuild 的 postinstall，`vite build` 会失败。
- `minimumReleaseAgeExclude` —— pnpm 自动写入的版本豁免清单，属工具自身记账，**不要手工清理**。

**Docker 构建**

```dockerfile
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
```

- 必须 `COPY` 三个文件：`pnpm-workspace.yaml` 会影响安装行为，漏掉会导致 `allowBuilds` 不生效。
- 必须用 `--frozen-lockfile`：CI / Docker 中锁文件与 `package.json` 不一致时应直接失败，而非静默重解析。
- `corepack enable` 需要访问 pnpm 分发源，Dockerfile 中已设置 `COREPACK_NPM_REGISTRY` 指向国内镜像。

**常见问题**

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `Use pnpm instead` | 误用 npm / yarn | 改用 `pnpm` |
| `ERR_PNPM_IGNORED_BUILDS` | 依赖安装脚本被拦 | 在 `pnpm-workspace.yaml` 的 `allowBuilds` 中放行该依赖 |
| 项目根出现 `_tmp_*` 文件 | pnpm 探测存储位置时的残留 | 已加入 `.gitignore`，确认无用后可删除 |
| `ERR_PNPM_OUTDATED_LOCKFILE` | 锁文件与 `package.json` 不同步 | 本地执行 `pnpm install` 后提交锁文件 |

---

## 6. 数据库与迁移

**没有 Alembic，没有迁移文件。** 建表依赖启动时的 `Base.metadata.create_all(bind=engine)`。

⚠️ **`create_all` 只建缺失的表，不会修改已存在表的结构。**

这意味着：**给现有模型新增/修改列后，运行中的应用不会自动生效。** 处理方式：

- 本地 SQLite：删除 `backend/shellquest.db` 后重启（会丢失数据）
- Docker MySQL：`docker compose down -v` 重建卷（会丢失数据）
- 需要保数据时：手写 `ALTER TABLE` 并记录在 PR 描述中

引入 Alembic 属于架构级变更，**请先与维护者确认**。

**表结构 vs 表内容，两者的更新机制不同，不要混淆：**

| 改了什么 | 需要做什么 |
| --- | --- |
| `models.py` 的**表/列定义** | 必须重建数据库（见上） |
| `curriculum/` 的**题目内容** | 重启即可，`seed_curriculum()` 会幂等同步（见 §4.7） |
| `curriculum/` 中**增删单元/题目**（`order` 位移） | 必须重建数据库，否则历史完成记录错位 |

---

## 7. 已知缺口（不要误以为已实现）

以下功能在 `REQUIREMENTS.md` 中有定义，但**代码中尚未实现**：

| 需求 | 现状 |
| --- | --- |
| 4.4 命令速查 + 自然语言搜索 | 后端无接口；前端搜索页是**硬编码**，任何输入都只显示 `ss -ltnp` 一张卡片 |
| 4.1 自由闯关主题地图 | 无地图视图。**数据结构已就绪**（`/api/v1/units` 返回按 `zone` 分组的单元 + 状态），但前端尚无地图页面 |
| 4.3 成就 / 徽章 / 公开排行榜 | 前后端均无实现 |
| 4.4.10 题目 ↔ 命令双向跳转 | **数据已就绪**（`quest_commands` 表 + 每题 `commands` 字段），但命令查询模块尚未实现，跳转链路未打通 |

已补齐、从本表移除的条目：

- ~~4.1.1 场景化出题~~ —— 已由 `CourseUnit` / `Quest` / `QuestOption` 三层模型 + `curriculum/` 承载
- ~~4.2 多种练习题型~~ —— 已支持 `terminal` / `fill` / `choice` / `judge` 四种题型与 5 种判题器

其他待改进项：

- `login` 复用了 `RegisterRequest`（语义上应拆出 `LoginRequest`）
- `redis` 已在 compose 中启动但代码零引用；需求中的排行榜/会话若落地，应优先接入 Redis
- `submit_quest()` 中 `db.commit()` 被多次调用（`do_checkin` 内一次 + 函数末尾一次），逻辑可合并
- `main.py` 仍是单文件承载全部路由；接口数量增长后需要评估是否拆分 `APIRouter`
- `curriculum/` 的题目内容目前为**手工撰写**，尚未与上游命令库做交叉校验（命令名可能写错）

---

## 8. 编码风格

### Python

- 4 空格缩进，行宽约 110
- 完整类型标注：函数参数与返回值均标注（`def health() -> dict[str, str]:`）
- 使用 Python 3.10+ 语法：`str | None`、`list[Quest]`
- SQLAlchemy 使用 2.0 风格：`Mapped[int]` + `mapped_column(...)`，查询用 `select()` + `db.scalars()` / `db.scalar()`
- 日志用模块级 `logger`（`logging.getLogger("shellquest")`），**不要用 `print`**
- 面向用户的错误信息用中文（如 `"用户名已被占用"`、`"任务不存在"`）

### TypeScript / Vue

- `<script setup lang="ts">` + Composition API，**不用 Options API**
- 函数显式标注返回类型（`async function submitAuth(): Promise<void>`）
- `tsconfig.app.json` 开启了 `strict` 与 `verbatimModuleSyntax`，类型导入需用 `import type`
- 面向用户的文案用中文

### 注释

- **不要写解释「代码在做什么」的注释**，代码本身应清晰
- 仅在「为什么这么做」不明显时补充注释
- 现有代码注释很少，请保持一致

---

## 9. 提交规范

历史提交使用 `type: 描述` 前缀：

```
fix: 修复构建错误
fix: 镜像路径换成国内
feat: gitignore
```

- `feat:` 新功能 / `fix:` 修复 / `docs:` 文档 / `refactor:` 重构 / `chore:` 杂项
- 描述可用中文
- 保持提交粒度小而聚焦，避免一次提交混合无关改动

---

## 10. 变更检查清单

改动前后自查：

- [ ] 修改了 `models.py` 的结构 → 是否处理了已有数据库（`create_all` 不会改列）？是否更新了本文档第 4.4 节？
- [ ] 修改了 `curriculum/` 的题目内容 → 是否跑过启动自检（`validate_curriculum`）？内容改动无需删库，增删题目则需删库（见 §4.7、§6）
- [ ] 新增或调整区域 → `main.py` 的 `ZONE_ORDER`、`curriculum/__init__.py` 的拼接顺序、各单元的 `zone` 字面量是否三处一致？
- [ ] 调整了 XP / 等级 / 称号数值 → `main.py`、`schemas.py`、`App.vue` 的 `DEFAULT_LEVEL` 是否同步？
- [ ] 新增接口 → 是否加了 `/api/v1` 前缀？是否需要 `Depends(get_current_user)`？是否已加入 `schemas.py` 的响应模型？
- [ ] 新增接口 → 是否**泄露了答案**（`answer_display` / `judge_payload` / `is_correct`）？答案只允许在提交接口返回
- [ ] 前端改动 → `pnpm run build` 是否通过（含 `vue-tsc` 类型检查）？`pnpm run lint` 是否零错误？（见 §0.3）
- [ ] 本次改动涉及的文件，是否都已按 §12.1 同步更新了对应文档？（见 §0.1）
- [ ] `AGENTS.md` 是否已按 §0.2 同步？若有缺口被补齐，§7 的条目是否已删除？
- [ ] 新增依赖 → 是否写入了 `requirements.txt` 或 `package.json`？
- [ ] 是否引入了新的 secrets？→ 必须走环境变量，**不得硬编码，不得提交 `.env`**

---

## 11. 不要做的事

- ❌ 不要提交 `.env`、`*.db`、`node_modules/`、`dist/`、`.venv/`（`.gitignore` 已覆盖）
- ❌ 不要绕过 `security.py` 自行实现口令处理；如需更换算法，连同已有哈希的兼容策略一并处理
- ❌ 不要在响应中暴露 `password_hash`（`UserSummary` 已排除，新增用户相关 schema 时注意）
- ❌ 不要删除 `shellquest.db` 之外的任何用户数据，除非明确要求并已确认
- ❌ 不要为「顺手优化」而重构 `App.vue` 的单文件结构或引入路由/状态库 —— 这属于架构决策，先问
- ❌ 不要把 Redis 当作已接入的能力来使用，除非你真的完成了接入
- ❌ 不要用 npm / yarn / bun 安装前端依赖，也不要提交非 pnpm 锁文件（见 §0.4、§5.7）
- ❌ 不要在课程列表 / 题目详情接口中下发答案字段（`answer_display` / `judge_payload` / 选项的 `is_correct`）。
  答案只允许由 `POST /api/v1/quests/{id}/submit` 返回，否则前端可直接读到答案
- ❌ 不要在 `main.py` 或其他后端文件中硬编码题目内容 —— 课程内容一律放 `curriculum/`（见 §4.7）

---

## 12. 文档同步

本节是 **§0.1「每次改动都必须记录到相应文件」** 的执行细则。

### 12.1 改动 → 文件对应关系

| 变更 | 必须更新 |
| --- | --- |
| 启动方式、端口、环境变量、依赖 | `README.md` |
| 功能范围、接口行为、验收标准 | `REQUIREMENTS.md` |
| 课程单元、主题区域、题型配比 | `COURSE_DESIGN.md` |
| 目录结构、架构、约定、命令、已知缺口 | `AGENTS.md`（本文件） |
| 数据结构（模型 / 表 / 字段） | `AGENTS.md` §4.4 + §6 |
| 课程内容（题目、选项、判题规则、命令关联） | `AGENTS.md` §4.4 + §4.7 + `COURSE_DESIGN.md` |
| 业务规则（XP、等级、解锁、打卡） | `AGENTS.md` §4.5 |
| 前端工具链与代码质量配置 | `AGENTS.md` §5.6 + `README.md` |
| 包管理器与锁文件策略 | `AGENTS.md` §5.7 + `README.md` |

一次改动可能同时命中多行 —— **全部都要更新**。

### 12.2 记录原则

- **同一次改动内完成**：文档与代码在同一个提交里，不接受「先合代码，回头补文档」。
- **文档要写「为什么」**：只记录结论而不记录理由的文档，下次改动时没人敢动。
- **缺口被补齐时必须删除对应条目**，不要让 §7 变成永不清理的待办清单。
- **描述与代码不符时以代码为准**，并在同一次改动中修正文档。

### 12.3 不写什么

- 不写流水账（「今天改了 X」）—— 提交历史已经承担了这个职责。
- 不写临时路径、调试命令、个人环境信息。
- 不写能从代码直接读出的内容。
