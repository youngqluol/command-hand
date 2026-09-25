# ShellQuest

面向全栈开发者与架构师的 Linux 实战训练场：场景化任务、技能树成长与命令速查。

## 本地启动

### 前端

> 前端**只使用 pnpm**，不使用 npm / yarn。首次使用请先启用 Corepack：`corepack enable`。
> 误用 npm 会被 `preinstall` 钩子拦截。

```bash
cd frontend
pnpm install
pnpm run dev
```

前端结构：`src/views/`（一屏一个文件，对应一条路由）、`src/components/`（可复用块）、
`src/stores/`（模块级 `ref` 单例，无 Pinia）、`src/api/client.ts`（唯一的 fetch 封装）。
路由用 history 模式，新增页面需在 `src/router/index.ts` 注册。详见 `AGENTS.md` §5。

代码检查与格式化（提交前必须通过 `lint` 与 `build`）：

```bash
pnpm run lint          # ESLint 检查
pnpm run lint:fix      # ESLint 自动修复
pnpm run format        # Prettier 格式化
pnpm run format:check  # Prettier 检查格式
pnpm run build         # vue-tsc 类型检查 + 生产构建
```

### 后端

```bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

课程内容位于 `backend/app/curriculum/`（21 个单元 / 63 道题），启动时会自动自检并幂等同步到数据库。
改完课程内容后可以先单独跑自检：

```bash
.venv/Scripts/python -c "from app.main import validate_curriculum; validate_curriculum()"
```

命令手册（614 条命令，来自 [jaywcjlove/linux-command](https://github.com/jaywcjlove/linux-command)，MIT 许可）
的离线快照已提交在 `backend/data/commands_seed.json.gz`，启动时若数据库为空会自动载入，**无需联网**。
需要更新上游内容时手动执行导入脚本：

```bash
.venv/Scripts/python scripts/import_commands.py --export   # 拉取上游 → 解析 → 写库 → 更新快照
```

端到端冒烟测试（临时 SQLite 库，不碰开发库）：

```bash
.venv/Scripts/python scripts/smoke_test.py   # 课程 / 认证 / 判题 / 解锁 / 命令手册 / 检索 / 打卡 / 技能树
```

> 若数据库是旧版本（表结构不同），首次启动会因表结构不匹配而报错，
> 需要先删除 `backend/shellquest.db` 再启动。详见 `AGENTS.md` §6。

访问 `http://localhost:5173`，API 文档位于 `http://localhost:8000/docs`。

## Docker 部署

Docker Desktop 可用时，在项目根目录执行：

```bash
docker compose up --build
```

前端默认运行在 `http://localhost:8080`，API 运行在 `http://localhost:8000`。

## 文档

- [产品需求](REQUIREMENTS.md)
- [课程与关卡设计](COURSE_DESIGN.md)
