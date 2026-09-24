"""网络前线：单元 10–12。"""

UNITS = [
    {
        "order": 10,
        "zone": "网络前线",
        "title": "网络不通",
        "goal": "按 DNS、连通性、HTTP 响应三层逐步排查。",
        "knowledge": (
            "网络排查要**分层**，从下往上，不要跳步：\n\n"
            "| 层 | 验证什么 | 命令 |\n"
            "| --- | --- | --- |\n"
            "| DNS | 域名能否解析成 IP | `dig` / `nslookup` / `getent hosts` |\n"
            "| 连通性 | IP 是否可达 | `ping` / `traceroute` |\n"
            "| 传输层 | 端口是否开放 | `nc -zv` / `ss -ltnp` |\n"
            "| 应用层 | HTTP 响应是否正常 | `curl -I` / `curl -v` |\n\n"
            "`ping` 通不代表服务可用（ICMP 与 TCP 是两条路径，且很多服务器禁 ping）；"
            "`ping` 不通也不代表服务不可用。**判断服务可用性以应用层为准。**"
        ),
        "quests": [
            {
                "kind": "terminal",
                "title": "确认域名解析",
                "scenario": "应用日志报 `could not resolve host: api.internal`。在怀疑网络之前，先确认这台机器能不能把该域名解析成 IP。",
                "context": "",
                "prompt": "用一条命令查询 `api.internal` 的 DNS 解析结果。",
                "answer_display": "dig api.internal",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["dig", "api.internal"]},
                "explanation": "`dig` 输出完整的 DNS 应答，包括解析到的 IP、使用的 DNS 服务器与响应状态码。",
                "pitfalls": "直接 `ping` 域名，会把「DNS 失败」和「网络不通」两种错误混在一起，难以区分。",
                "safer_alt": "只想拿 IP 时用 `getent hosts api.internal`，它走系统解析链路（含 `/etc/hosts`），比 `dig` 更贴近应用实际行为。",
                "difficulty": 2,
                "xp_reward": 40,
                "commands": ["dig", "nslookup", "getent"],
                "options": [],
            },
            {
                "kind": "terminal",
                "title": "只看 HTTP 响应头",
                "scenario": "域名能解析、端口也通，但接口行为异常。你需要快速拿到 HTTP 状态码和响应头，不要下载响应体。",
                "context": "",
                "prompt": "用一条命令只请求响应头。",
                "answer_display": "curl -I https://api.internal/health",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["curl", "-I"]},
                "explanation": "`-I`（`--head`）发送 HEAD 请求，只返回响应头，包含状态码、`Content-Type`、缓存与代理相关字段。",
                "pitfalls": "用 `curl` 不加 `-I` 会把整个响应体打到终端，接口返回大 JSON 时会刷屏。",
                "safer_alt": "需要看完整交互过程（TLS 握手、重定向链）时用 `curl -v`；只想拿状态码用 `curl -s -o /dev/null -w '%{http_code}'`。",
                "difficulty": 2,
                "xp_reward": 40,
                "commands": ["curl"],
                "options": [],
            },
            {
                "kind": "choice",
                "title": "快速巩固 · ping 通不等于服务正常",
                "scenario": "`ping api.internal` 有回包，但浏览器访问仍然超时。",
                "context": "",
                "prompt": "下列推断哪一项正确？",
                "answer_display": "ICMP 通只能说明网络层可达，服务是否可用还需检查端口与 HTTP 响应。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "`ping` 走 ICMP，服务监听走 TCP。ICMP 可达而目标端口未监听、或被防火墙拦截，都会表现为「ping 通但访问不通」。",
                "pitfalls": "把 `ping` 通当作服务健康的证据，是排障中最常见的逻辑跳跃。",
                "safer_alt": "下一步按顺序验证：`nc -zv api.internal 443` 看端口，再用 `curl -I` 看应用层响应。",
                "difficulty": 2,
                "xp_reward": 20,
                "commands": ["ping", "curl", "ss"],
                "options": [
                    {"key": "A", "text": "ICMP 通只说明网络层可达，还需检查端口与 HTTP 响应", "is_correct": True},
                    {"key": "B", "text": "说明服务一定正常，问题在客户端", "is_correct": False},
                    {"key": "C", "text": "说明 DNS 解析有问题", "is_correct": False},
                    {"key": "D", "text": "说明需要重启服务器", "is_correct": False},
                ],
            },
        ],
    },
    {
        "order": 11,
        "zone": "网络前线",
        "title": "端口冲突",
        "goal": "定位占用目标端口的进程，并选择最小风险的处理方式。",
        "knowledge": (
            "| 命令 | 作用 |\n"
            "| --- | --- |\n"
            "| `ss -ltnp` | 列出监听中的 TCP 端口及所属进程 |\n"
            "| `ss -lunp` | 同上，UDP |\n"
            "| `lsof -i :8080` | 查看占用 8080 的进程 |\n"
            "| `netstat -tunlp` | 传统写法（新系统建议用 `ss`） |\n\n"
            "`ss` 的选项含义：`-l` 只看监听、`-t` TCP、`-u` UDP、`-n` 不解析服务名、`-p` 显示进程。\n\n"
            "**`-p` 需要权限**：非 root 用户只能看到自己拥有的进程，看不到别人的，容易误判为「端口没被占用」。"
        ),
        "quests": [
            {
                "kind": "terminal",
                "title": "谁占用了 8080",
                "scenario": "部署新版本 API 时，启动日志提示 `Address already in use`。你需要定位占用 8080 端口的进程。限制：不能重启整台服务器，不能误杀无关进程。",
                "context": (
                    "```text\n"
                    "[ERROR] Failed to bind to 0.0.0.0:8080\n"
                    "OSError: [Errno 98] Address already in use\n"
                    "```"
                ),
                "prompt": "用一条命令列出所有监听中的 TCP 端口及其所属进程。",
                "answer_display": "ss -ltnp",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["ss", "-p"]},
                "explanation": "`ss -ltnp` 中 `-l` 限定监听态、`-t` 限定 TCP、`-n` 不做服务名解析、`-p` 显示进程信息，一条命令即可看到端口与 PID 的对应关系。",
                "pitfalls": "不加 `-p` 只能看到端口被占，看不到是谁占的；非 root 用户加 `-p` 也看不到其他用户的进程，需 `sudo`。",
                "safer_alt": "已知端口时用 `lsof -i :8080` 更直接；确认 PID 后先 `ps -p <PID> -o pid,user,cmd` 看清它是什么再决定。",
                "difficulty": 2,
                "xp_reward": 40,
                "commands": ["ss", "lsof", "ps"],
                "options": [],
            },
            {
                "kind": "judge",
                "title": "端口被占用后怎么处理",
                "scenario": "你查到 8080 被 PID 4213 占用，该进程属于 `root`，命令行是 `/usr/sbin/nginx: worker process`。这是本机 Nginx 的反向代理进程。",
                "context": (
                    "```shell\n"
                    "$ sudo ss -ltnp | grep :8080\n"
                    "LISTEN 0 511 0.0.0.0:8080 0.0.0.0:* users:((\"nginx\",pid=4213,fd=6))\n"
                    "```"
                ),
                "prompt": "下列处理方式哪一项最合理？",
                "answer_display": "给 API 换一个端口，或调整 Nginx 配置后重载。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "占用者是本机正常的反向代理服务，杀掉它会中断现有流量。正确做法是调整端口分配，而不是消除「占用者」。",
                "pitfalls": "看到端口被占就直接 `kill -9`，可能直接打挂线上入口。先确认进程身份，再判断谁该让路。",
                "safer_alt": "改 Nginx 配置后用 `nginx -t` 校验语法，再 `systemctl reload nginx` 平滑重载，避免中断连接。",
                "difficulty": 3,
                "xp_reward": 40,
                "commands": ["ss", "lsof", "kill", "systemctl"],
                "options": [
                    {"key": "A", "text": "给 API 换端口，或调整 Nginx 配置后平滑重载", "is_correct": True},
                    {"key": "B", "text": "`kill -9 4213` 释放端口", "is_correct": False},
                    {"key": "C", "text": "重启整台服务器", "is_correct": False},
                    {"key": "D", "text": "停掉所有 nginx 进程再启动 API", "is_correct": False},
                ],
            },
            {
                "kind": "fill",
                "title": "快速巩固 · 按端口查进程",
                "scenario": "已知端口号，直接定位占用进程。",
                "context": "",
                "prompt": "补全命令：`lsof -i :____` 查看占用 8080 端口的进程。",
                "answer_display": "lsof -i :8080",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["lsof", "8080"]},
                "explanation": "`lsof -i` 按网络连接筛选，`:8080` 指定端口，输出包含进程名与 PID。",
                "pitfalls": "漏掉端口前的冒号（写成 `-i 8080`）会变成按协议或服务名筛选，结果不符合预期。",
                "safer_alt": "",
                "difficulty": 1,
                "xp_reward": 20,
                "commands": ["lsof"],
                "options": [],
            },
        ],
    },
    {
        "order": 12,
        "zone": "网络前线",
        "title": "远程发布",
        "goal": "安全传输构建产物，并验证完整性。",
        "knowledge": (
            "| 命令 | 特点 |\n"
            "| --- | --- |\n"
            "| `scp` | 简单，全量传输，**中断后需重头再来** |\n"
            "| `rsync` | 增量传输，支持断点续传、排除规则、校验 |\n"
            "| `ssh` | 远程执行命令、端口转发 |\n\n"
            "`rsync` 关键选项：\n\n"
            "| 选项 | 作用 |\n"
            "| --- | --- |\n"
            "| `-a` | 归档模式（保留权限、时间戳、符号链接） |\n"
            "| `-v` | 输出传输明细 |\n"
            "| `-z` | 传输时压缩 |\n"
            "| `-P` | 显示进度并支持断点续传 |\n"
            "| `--delete` | 删除目标端多余文件（**危险，需谨慎**） |\n"
            "| `-n` | 演练，只显示会做什么，不实际执行 |\n\n"
            "**源路径结尾是否带 `/` 语义不同**：`src/` 表示复制目录内容，`src` 表示复制目录本身。"
        ),
        "quests": [
            {
                "kind": "terminal",
                "title": "增量上传构建产物",
                "scenario": "你要把本地 `dist/` 目录的内容传到测试机的 `/srv/app/releases/2026-09-24/`。此前已传过一次，网络不稳定，希望中断后能续传、且只传变化的部分。",
                "context": "",
                "prompt": "用一条命令完成传输，要求保留权限与时间戳、显示进度并支持断点续传。",
                "answer_display": "rsync -avP dist/ deploy@test-01:/srv/app/releases/2026-09-24/",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["rsync"]},
                "explanation": "`-a` 归档模式保留权限与时间戳，`-v` 输出明细，`-P` 等价于 `--partial --progress`，既显示进度又保留未完成的临时文件以便续传。",
                "pitfalls": "用 `scp` 传大目录，中断后必须从头再来；`dist` 与 `dist/` 的差别会导致多套一层目录。",
                "safer_alt": "不确定结果时先加 `-n`（dry-run）演练一遍，确认文件清单无误再真正执行。",
                "difficulty": 3,
                "xp_reward": 40,
                "commands": ["rsync", "scp", "ssh"],
                "options": [],
            },
            {
                "kind": "choice",
                "title": "源路径结尾的斜杠",
                "scenario": "你需要把本地 `dist/` 的**内容**放到目标目录 `/srv/app/` 下，而不是生成 `/srv/app/dist/`。",
                "context": "",
                "prompt": "下列哪条命令能达到目的？",
                "answer_display": "rsync -av dist/ deploy@test-01:/srv/app/",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "源路径以 `/` 结尾表示「同步该目录的**内容**」；不带 `/` 则表示「同步这个目录本身」，会在目标端新建同名子目录。",
                "pitfalls": "漏写或多写结尾斜杠，会造成目录结构多一层，且 rsync 不会报错，问题往往到部署失败才暴露。",
                "safer_alt": "拿不准时先用 `-n` 演练，输出的文件路径清单能直接验证目录层级是否符合预期。",
                "difficulty": 2,
                "xp_reward": 40,
                "commands": ["rsync"],
                "options": [
                    {"key": "A", "text": "`rsync -av dist/ deploy@test-01:/srv/app/`", "is_correct": True},
                    {"key": "B", "text": "`rsync -av dist deploy@test-01:/srv/app/`", "is_correct": False},
                    {"key": "C", "text": "`scp -r dist deploy@test-01:/srv/app/`", "is_correct": False},
                    {"key": "D", "text": "`rsync -av dist/ deploy@test-01:/srv/app/dist/`", "is_correct": False},
                ],
            },
            {
                "kind": "judge",
                "title": "快速巩固 · --delete 的风险",
                "scenario": "同事建议加 `--delete` 让目标端「和本地完全一致」。目标目录 `/srv/app/releases/` 中还存放着其他历史版本。",
                "context": "",
                "prompt": "关于加 `--delete` 的后果，下列判断哪一项正确？",
                "answer_display": "目标端中源端不存在的文件会被删除，包括其他历史版本。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "`--delete` 的语义是「让目标与源完全镜像」，目标端多出来的文件会被删除，这是不可逆操作。",
                "pitfalls": "把 `--delete` 当作「清理旧文件」的便捷开关，在目标目录含其他数据时会造成数据丢失。",
                "safer_alt": "先加 `-n` 演练，检查输出中是否有 `deleting` 行；确认无误再执行，或改用 `--delete-after` 配合备份。",
                "difficulty": 3,
                "xp_reward": 20,
                "commands": ["rsync"],
                "options": [
                    {"key": "A", "text": "目标端中源端不存在的文件会被删除，包括其他历史版本", "is_correct": True},
                    {"key": "B", "text": "只删除目标端的空目录", "is_correct": False},
                    {"key": "C", "text": "只影响传输失败的文件", "is_correct": False},
                    {"key": "D", "text": "没有任何副作用", "is_correct": False},
                ],
            },
        ],
    },
]
