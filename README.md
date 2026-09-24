# ShellQuest

面向全栈开发者与架构师的 Linux 实战训练场：场景化任务、技能树成长与命令速查。

## 本地启动

### 前端

```bash
cd frontend
npm install
npm run dev
```

代码检查与格式化（提交前必须通过 `lint` 与 `build`）：

```bash
npm run lint          # ESLint 检查
npm run lint:fix      # ESLint 自动修复
npm run format        # Prettier 格式化
npm run format:check  # Prettier 检查格式
npm run build         # vue-tsc 类型检查 + 生产构建
```

### 后端

```bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

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
