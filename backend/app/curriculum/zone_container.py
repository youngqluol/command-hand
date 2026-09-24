"""容器基地：单元 17–19。"""

UNITS = [
    {
        "order": 17,
        "zone": "容器基地",
        "title": "镜像构建失败",
        "goal": "根据 Dockerfile 与构建日志定位失败层，并修复构建命令。",
        "knowledge": (
            "镜像构建是**分层**的，Dockerfile 中每条指令生成一层，**任何一层失败，其后的层都不会执行**。\n\n"
            "| 命令 | 作用 |\n"
            "| --- | --- |\n"
            "| `docker build -t <名称> <上下文>` | 构建镜像 |\n"
            "| `docker build --no-cache` | 忽略缓存，从零构建 |\n"
            "| `docker images` | 列出本地镜像 |\n"
            "| `docker history <镜像>` | 查看镜像的分层历史 |\n\n"
            "**缓存的影响**：Docker 会复用未变化的层。改了 `COPY` 的文件但没改依赖，"
            "依赖层会命中缓存；反之，如果先 `COPY . .` 再 `RUN npm install`，"
            "任何源码改动都会让依赖重装一遍。**先拷依赖清单，再装依赖，最后拷源码**是标准顺序。\n\n"
            "`.dockerignore` 决定哪些文件不进构建上下文，漏配会把 `node_modules` 等一起送进去。"
        ),
        "quests": [
            {
                "kind": "choice",
                "title": "依赖安装层失败",
                "scenario": "构建日志显示在 `RUN npm install` 这一步失败，报找不到 `package.json`。Dockerfile 片段如下。",
                "context": (
                    "```dockerfile\n"
                    "FROM node:24-alpine\n"
                    "WORKDIR /app\n"
                    "COPY . .\n"
                    "RUN npm install\n"
                    "```"
                ),
                "prompt": "最可能的失败原因是什么？",
                "answer_display": "WORKDIR 目录下没有 package.json，可能是 .dockerignore 把它排除了。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "`COPY . .` 只复制**构建上下文**中的文件，而上下文受 `.dockerignore` 过滤。若其中排除了 `package.json`，工作目录里就没有它。",
                "pitfalls": "只盯着 Dockerfile 找问题，忽略 `.dockerignore` 与构建上下文范围，会长时间找不到原因。",
                "safer_alt": "用 `docker build --no-cache` 排除缓存干扰；用 `docker run --rm <镜像> ls -la /app` 直接查看层内实际文件。",
                "difficulty": 3,
                "xp_reward": 40,
                "commands": ["docker", "cat", "ls"],
                "options": [
                    {"key": "A", "text": "`package.json` 被 `.dockerignore` 排除，未进入构建上下文", "is_correct": True},
                    {"key": "B", "text": "node 版本太低", "is_correct": False},
                    {"key": "C", "text": "WORKDIR 指令写错了", "is_correct": False},
                    {"key": "D", "text": "网络无法访问 npm 源", "is_correct": False},
                ],
            },
            {
                "kind": "judge",
                "title": "缓存导致改动不生效",
                "scenario": "你只改了 `src/App.vue` 一行代码，重新构建后发现镜像里还是旧内容。Dockerfile 顺序是 `COPY . .` → `RUN npm install` → `RUN npm run build`。",
                "context": (
                    "```dockerfile\n"
                    "COPY . .\n"
                    "RUN npm install\n"
                    "RUN npm run build\n"
                    "```"
                ),
                "prompt": "下列排查思路哪一项最合理？",
                "answer_display": "先用 --no-cache 排除缓存干扰，确认后再调整 Dockerfile 顺序。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "先做一次 `--no-cache` 构建，可以快速区分「代码没进去」还是「缓存复用了旧层」。确认是缓存问题后，把依赖清单与源码的复制拆开，让依赖层能独立缓存。",
                "pitfalls": "不验证就盲目改 Dockerfile，可能在缓存和真实问题之间反复摇摆，浪费大量时间。",
                "safer_alt": "推荐顺序：`COPY package*.json ./` → `RUN pnpm install` → `COPY . .` → `RUN pnpm run build`，源码改动不会触发依赖重装。",
                "difficulty": 3,
                "xp_reward": 40,
                "commands": ["docker"],
                "options": [
                    {"key": "A", "text": "先用 `--no-cache` 排除缓存干扰，确认后再调整 Dockerfile 顺序", "is_correct": True},
                    {"key": "B", "text": "直接删掉所有镜像重新构建", "is_correct": False},
                    {"key": "C", "text": "重启 Docker 服务", "is_correct": False},
                    {"key": "D", "text": "把 `npm run build` 改成 `npm start`", "is_correct": False},
                ],
            },
            {
                "kind": "fill",
                "title": "快速巩固 · 指定镜像名",
                "scenario": "构建镜像并命名为 `shellquest-web`。",
                "context": "",
                "prompt": "补全命令：`docker build ____ shellquest-web .`",
                "answer_display": "docker build -t shellquest-web .",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["docker", "build", "-t"]},
                "explanation": "`-t`（`--tag`）为镜像打标签，格式为 `名称:标签`，省略标签时默认为 `latest`。末尾的 `.` 是构建上下文路径，不可省略。",
                "pitfalls": "漏掉末尾的 `.` 会报 `requires exactly 1 argument`；把 `.` 写成 `./` 在部分场景下会扩大上下文范围。",
                "safer_alt": "",
                "difficulty": 1,
                "xp_reward": 20,
                "commands": ["docker"],
                "options": [],
            },
        ],
    },
    {
        "order": 18,
        "zone": "容器基地",
        "title": "容器未响应",
        "goal": "按状态、日志、进程、端口映射的顺序检查容器。",
        "knowledge": (
            "容器「在运行」不等于「服务可用」。排查顺序：**状态 → 日志 → 进程 → 端口**。\n\n"
            "| 命令 | 作用 |\n"
            "| --- | --- |\n"
            "| `docker ps` | 运行中的容器（`-a` 含已退出） |\n"
            "| `docker logs --tail 100 <容器>` | 最近 100 行日志 |\n"
            "| `docker logs -f <容器>` | 实时跟踪日志 |\n"
            "| `docker exec -it <容器> sh` | 进入容器执行命令 |\n"
            "| `docker port <容器>` | 查看端口映射 |\n"
            "| `docker inspect <容器>` | 完整配置与状态（JSON） |\n\n"
            "**端口映射的经典陷阱**：容器内服务监听 `127.0.0.1:8000` 时，"
            "即使做了 `-p 8000:8000`，宿主机也访问不到 —— 因为回环地址只接受容器内部连接。"
            "**服务必须监听 `0.0.0.0`。**"
        ),
        "quests": [
            {
                "kind": "terminal",
                "title": "查看容器日志",
                "scenario": "`shellquest-api` 容器显示为运行中，但接口无响应。先看它最近的日志，确认应用是否真的启动成功。",
                "context": "",
                "prompt": "用一条命令查看该容器最近 100 行日志。",
                "answer_display": "docker logs --tail 100 shellquest-api",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["docker", "logs"]},
                "explanation": "`--tail 100` 只取末尾 100 行，避免容器长期运行时刷出海量日志。",
                "pitfalls": "`docker logs` 只能看到容器主进程的 stdout/stderr；如果应用把日志写进文件，需要 `docker exec` 进去看。",
                "safer_alt": "需要持续观察启动过程时用 `docker logs -f --tail 50 <容器>`。",
                "difficulty": 1,
                "xp_reward": 40,
                "commands": ["docker"],
                "options": [],
            },
            {
                "kind": "judge",
                "title": "端口映射了却访问不到",
                "scenario": "容器启动命令是 `docker run -p 8000:8000 shellquest-api`。容器内进程确实在监听 8000，但宿主机 `curl 127.0.0.1:8000` 超时。",
                "context": (
                    "```shell\n"
                    "$ docker port shellquest-api\n"
                    "8000/tcp -> 0.0.0.0:8000\n\n"
                    "$ docker exec shellquest-api ss -ltn\n"
                    "LISTEN 0 511 127.0.0.1:8000 0.0.0.0:*\n"
                    "```"
                ),
                "prompt": "根因是什么？",
                "answer_display": "容器内服务只监听 127.0.0.1，宿主机无法通过端口映射访问。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "端口映射把宿主机流量转发到容器网卡。服务只绑 `127.0.0.1` 时，仅接受容器**内部**回环连接，来自宿主机的转发请求会被拒绝。",
                "pitfalls": "只检查 `docker port` 看到映射存在就认为端口没问题，忽略了容器内**监听地址**这一层。",
                "safer_alt": "把服务启动参数改为监听 `0.0.0.0`（如 uvicorn `--host 0.0.0.0`），并用 `docker exec <容器> ss -ltn` 复核。",
                "difficulty": 3,
                "xp_reward": 40,
                "commands": ["docker", "ss", "curl"],
                "options": [
                    {"key": "A", "text": "容器内服务只监听 `127.0.0.1`，宿主机转发不进去", "is_correct": True},
                    {"key": "B", "text": "端口映射写反了，应为 `-p 8000:8000`", "is_correct": False},
                    {"key": "C", "text": "宿主机防火墙拦截了", "is_correct": False},
                    {"key": "D", "text": "容器需要重启", "is_correct": False},
                ],
            },
            {
                "kind": "fill",
                "title": "快速巩固 · 进入容器",
                "scenario": "需要进入运行中的容器排查。",
                "context": "",
                "prompt": "补全命令：`docker exec -____ shellquest-api sh` 以交互方式进入容器。",
                "answer_display": "docker exec -it shellquest-api sh",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["docker", "exec"]},
                "explanation": "`-i` 保持标准输入打开，`-t` 分配伪终端，二者合写为 `-it` 才能获得可交互的 shell。",
                "pitfalls": "只写 `-i` 或只写 `-t`，命令会立即退出或无法输入；容器里通常没有 bash，优先用 `sh`。",
                "safer_alt": "",
                "difficulty": 1,
                "xp_reward": 20,
                "commands": ["docker"],
                "options": [],
            },
        ],
    },
    {
        "order": 19,
        "zone": "容器基地",
        "title": "数据不会丢",
        "goal": "为数据库容器设计并验证数据持久化。",
        "knowledge": (
            "容器的文件系统是**临时的**：容器被删除，其中写入的数据一并消失。\n\n"
            "| 方式 | 说明 | 适用场景 |\n"
            "| --- | --- | --- |\n"
            "| 匿名卷 | `docker run -v /var/lib/mysql` | 临时使用，不便管理 |\n"
            "| 具名卷 | `docker run -v mysql_data:/var/lib/mysql` | **推荐**，由 Docker 管理 |\n"
            "| 绑定挂载 | `docker run -v /host/path:/container/path` | 需直接访问宿主机目录 |\n\n"
            "| 命令 | 作用 |\n"
            "| --- | --- |\n"
            "| `docker volume ls` | 列出全部卷 |\n"
            "| `docker volume inspect <卷>` | 查看卷的挂载点与创建信息 |\n"
            "| `docker volume rm <卷>` | 删除卷（**数据一并删除**） |\n\n"
            "`docker compose down -v` 中的 `-v` 会**同时删除卷**，这是数据丢失的常见来源。"
        ),
        "quests": [
            {
                "kind": "terminal",
                "title": "确认数据卷已挂载",
                "scenario": "数据库容器重建后数据丢失。你怀疑数据目录没有做持久化。先列出当前已有的数据卷，确认是否存在数据库专用卷。",
                "context": "",
                "prompt": "用一条命令列出本机全部 Docker 数据卷。",
                "answer_display": "docker volume ls",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["docker", "volume"]},
                "explanation": "`docker volume ls` 列出全部卷及驱动类型。若没有与数据库对应的卷，说明容器写入的是可写层，容器一删数据即失。",
                "pitfalls": "只看 `docker ps` 确认容器在跑，无法发现数据没有持久化 —— 这个问题只在容器被重建时才暴露。",
                "safer_alt": "进一步用 `docker inspect <容器>` 查看 `Mounts` 字段，确认数据目录实际指向哪个卷或宿主机路径。",
                "difficulty": 2,
                "xp_reward": 40,
                "commands": ["docker"],
                "options": [],
            },
            {
                "kind": "judge",
                "title": "down -v 的后果",
                "scenario": "数据库容器已经配置了具名卷 `mysql_data`。同事执行 `docker compose down -v` 来「重启一下环境」。",
                "context": "",
                "prompt": "关于这条命令，下列判断哪一项正确？",
                "answer_display": "会同时删除具名卷，数据库数据全部丢失。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "`down` 停止并删除容器与网络；额外的 `-v`（`--volumes`）会连具名卷一起删除，这正是持久化数据所在。",
                "pitfalls": "把 `down -v` 当作「彻底重启」的常规操作，在有状态服务上等同于删库。",
                "safer_alt": "只重建容器用 `docker compose down`（不带 `-v`），或 `docker compose up -d --force-recreate`。",
                "difficulty": 3,
                "xp_reward": 40,
                "commands": ["docker"],
                "options": [
                    {"key": "A", "text": "会同时删除具名卷，数据库数据全部丢失", "is_correct": True},
                    {"key": "B", "text": "只删除容器，卷会保留", "is_correct": False},
                    {"key": "C", "text": "只删除未使用的匿名卷", "is_correct": False},
                    {"key": "D", "text": "等同于 `docker compose stop`", "is_correct": False},
                ],
            },
            {
                "kind": "choice",
                "title": "快速巩固 · 选择挂载方式",
                "scenario": "生产环境的 MySQL 容器需要持久化数据，且希望由 Docker 统一管理存储位置、便于迁移。",
                "context": "",
                "prompt": "下列方案哪一种最合适？",
                "answer_display": "使用具名卷 mysql_data:/var/lib/mysql。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "具名卷由 Docker 管理，不依赖宿主机目录结构，跨环境迁移更方便，也不会被 `down` 误删（除非显式加 `-v`）。",
                "pitfalls": "用匿名卷会导致难以定位和备份；绑定挂载需要自行处理宿主机目录权限与 SELinux 上下文。",
                "safer_alt": "需要把数据放在特定宿主机路径（如已有备份策略）时，再改用绑定挂载。",
                "difficulty": 2,
                "xp_reward": 20,
                "commands": ["docker"],
                "options": [
                    {"key": "A", "text": "具名卷 `mysql_data:/var/lib/mysql`", "is_correct": True},
                    {"key": "B", "text": "匿名卷", "is_correct": False},
                    {"key": "C", "text": "不挂载，依赖容器可写层", "is_correct": False},
                    {"key": "D", "text": "每天 `docker commit` 一次", "is_correct": False},
                ],
            },
        ],
    },
]
