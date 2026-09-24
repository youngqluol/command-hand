"""文件工坊：单元 01–04。

内容结构见 REQUIREMENTS.md §4.1.2。
"""

UNITS = [
    {
        "order": 1,
        "zone": "文件工坊",
        "title": "初入服务器",
        "goal": "确认当前身份、所在目录与系统基本信息。",
        "knowledge": (
            "登录一台陌生机器后，先回答三个问题：**我是谁**、**我在哪**、**这是什么系统**。\n\n"
            "| 命令 | 作用 |\n"
            "| --- | --- |\n"
            "| `whoami` | 当前有效用户名 |\n"
            "| `id` | 用户名 + UID + GID + 附加组 |\n"
            "| `pwd` | 当前工作目录的绝对路径 |\n"
            "| `uname -r` | 内核版本号 |\n"
            "| `uname -a` | 内核、架构、主机名、构建时间 |\n"
            "| `hostname` | 主机名 |\n\n"
            "`whoami` 与 `id` 的差别在 `sudo` 场景下尤其重要：`whoami` 反映的是**有效**身份，"
            "而 `$USER` 环境变量可能仍指向原始登录用户。"
        ),
        "quests": [
            {
                "kind": "terminal",
                "title": "确认登录身份与位置",
                "scenario": "你刚 SSH 登录到一台新的测试机。在动手改任何东西之前，需要先确认自己是谁、当前位于哪个目录。",
                "context": "",
                "prompt": "用一条命令同时输出当前用户名和当前工作目录。",
                "answer_display": "whoami && pwd",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["whoami", "pwd"]},
                "explanation": "`whoami` 输出当前有效用户名，`pwd` 输出当前工作目录的绝对路径。用 `&&` 串联表示前一条成功才执行后一条。",
                "pitfalls": "`who` 和 `w` 列出的是登录会话，不是当前身份；`echo $USER` 依赖环境变量，在 `sudo -i` 等场景可能失真。",
                "safer_alt": "需要完整权限上下文时用 `id`，它同时给出 UID、GID 与附加组。",
                "difficulty": 1,
                "xp_reward": 40,
                "commands": ["whoami", "pwd"],
                "options": [],
            },
            {
                "kind": "choice",
                "title": "确认内核版本",
                "scenario": "报障的同学说「这台机器内核太老，所以容器起不来」。你需要先拿到事实，再下结论。",
                "context": "",
                "prompt": "下列哪条命令能**直接**输出当前运行的内核版本号？",
                "answer_display": "uname -r",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "`uname -r` 只输出内核发行版本号（如 `5.15.0-91-generic`），输出干净、适合脚本取值。",
                "pitfalls": "把「发行版版本」当成「内核版本」是排障中的高频误判。`/etc/os-release` 和 `lsb_release` 描述的都是发行版。",
                "safer_alt": "需要完整信息（架构、主机名、构建时间）时用 `uname -a`。",
                "difficulty": 1,
                "xp_reward": 40,
                "commands": ["uname", "hostname"],
                "options": [
                    {"key": "A", "text": "`uname -r`", "is_correct": True},
                    {"key": "B", "text": "`cat /etc/os-release`", "is_correct": False},
                    {"key": "C", "text": "`hostname`", "is_correct": False},
                    {"key": "D", "text": "`lsb_release -a`", "is_correct": False},
                ],
            },
            {
                "kind": "fill",
                "title": "快速巩固 · 内核版本",
                "scenario": "只取内核版本号，不要多余输出。",
                "context": "",
                "prompt": "补全命令：`uname -____` 只输出内核版本号。",
                "answer_display": "uname -r",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["uname", "-r"]},
                "explanation": "`-r` 是 `--kernel-release` 的短选项，只打印内核版本号。",
                "pitfalls": "写成 `-a` 会输出全部信息，脚本取值时还要额外裁剪。",
                "safer_alt": "",
                "difficulty": 1,
                "xp_reward": 20,
                "commands": ["uname"],
                "options": [],
            },
        ],
    },
    {
        "order": 2,
        "zone": "文件工坊",
        "title": "项目文件定位",
        "goal": "在发布目录中按名称与类型定位文件。",
        "knowledge": (
            "`find` 的基本形态是 `find <起点> <表达式>`，它**递归**遍历起点下的所有子目录。\n\n"
            "| 选项 | 作用 |\n"
            "| --- | --- |\n"
            "| `-name` | 按文件名匹配（区分大小写） |\n"
            "| `-iname` | 按文件名匹配（忽略大小写） |\n"
            "| `-path` | 按完整路径匹配 |\n"
            "| `-type f` / `-type d` | 只匹配文件 / 只匹配目录 |\n"
            "| `-maxdepth N` | 限制递归深度 |\n\n"
            "**通配符由 shell 展开，`find -name` 的模式由 find 自己解释**，两者规则不同。"
            "shell 通配符遇到隐藏文件（`.` 开头）不会匹配，所以 `-name '.env'` 要写全名。"
        ),
        "quests": [
            {
                "kind": "terminal",
                "title": "配置文件失踪",
                "scenario": "新版本已解压到 `/srv/app/releases/2026-09-10`，但服务启动时提示找不到环境配置。请在不修改任何文件的前提下，定位该目录及其子目录中的 `.env` 文件。",
                "context": (
                    "```text\n"
                    "/srv/app/\n"
                    "├── releases/2026-09-10/\n"
                    "│   ├── api/\n"
                    "│   └── config/.env\n"
                    "└── shared/\n"
                    "```"
                ),
                "prompt": "在模拟终端中输入命令，递归定位该发布目录下的 `.env` 文件。",
                "answer_display": "find /srv/app/releases/2026-09-10 -name '.env'",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["find", ".env"]},
                "explanation": "`find <起点> -name <模式>` 会递归遍历起点下的所有层级。`-name` 只比对文件名本身，不比对路径。",
                "pitfalls": "`ls` 只能看到一层；`-path` 会把目录名也算进匹配范围，容易误命中。",
                "safer_alt": "大小写不确定时改用 `-iname`。`find` 默认只读，确认结果后再执行删除或修改。",
                "difficulty": 1,
                "xp_reward": 40,
                "commands": ["find", "ls"],
                "options": [],
            },
            {
                "kind": "choice",
                "title": "列出目录下的日志文件",
                "scenario": "你需要确认 `/var/log` 下有哪些 `.log` 文件（只看这一层，不进子目录）。",
                "context": "",
                "prompt": "下列哪条命令最合适？",
                "answer_display": "ls /var/log/*.log",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "`*` 由 shell 展开成匹配的文件名列表，`*.log` 表示「任意字符 + `.log` 结尾」。",
                "pitfalls": "把 `*.log` 误写成 `.log`（漏掉星号）会变成精确匹配名为 `.log` 的文件，结果为空且不报错。",
                "safer_alt": "文件数量极大时 `ls` 可能报 `Argument list too long`，此时用 `find /var/log -maxdepth 1 -name '*.log'`。",
                "difficulty": 1,
                "xp_reward": 40,
                "commands": ["ls", "find"],
                "options": [
                    {"key": "A", "text": "`ls /var/log/*.log`", "is_correct": True},
                    {"key": "B", "text": "`ls /var/log/*`", "is_correct": False},
                    {"key": "C", "text": "`find /var/log -name .log`", "is_correct": False},
                    {"key": "D", "text": "`ls -R /var/log`", "is_correct": False},
                ],
            },
            {
                "kind": "fill",
                "title": "快速巩固 · 忽略大小写",
                "scenario": "文件名大小写不确定，需要忽略大小写查找。",
                "context": "",
                "prompt": "补全命令：`find /etc -____ nginx.conf`，忽略大小写查找 `nginx.conf`。",
                "answer_display": "find /etc -iname nginx.conf",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["-iname"]},
                "explanation": "`-iname` 是 `-name` 的忽略大小写版本，`i` 前缀在 find 中统一表示 case-insensitive。",
                "pitfalls": "`-i`、`-ignorecase` 都不是 find 的合法选项，写了会直接报错。",
                "safer_alt": "",
                "difficulty": 1,
                "xp_reward": 20,
                "commands": ["find"],
                "options": [],
            },
        ],
    },
    {
        "order": 3,
        "zone": "文件工坊",
        "title": "文件整理与备份",
        "goal": "安全归档日志，避免覆盖已有备份。",
        "knowledge": (
            "复制与移动类命令的默认行为是**静默覆盖**，这在备份场景里非常危险。\n\n"
            "| 选项 | 作用 | 风险 |\n"
            "| --- | --- | --- |\n"
            "| `-n` | 目标存在则跳过（no-clobber） | 安全 |\n"
            "| `-i` | 目标存在则交互询问 | 安全但无法脚本化 |\n"
            "| `-f` | 强制覆盖 | **危险** |\n"
            "| `-a` | 归档模式，保留权限与时间戳 | 安全 |\n\n"
            "`rm -r` 递归删除、`rm -f` 强制且不提示，二者叠加即为**静默删除整棵目录树**。"
        ),
        "quests": [
            {
                "kind": "terminal",
                "title": "归档日志且不覆盖备份",
                "scenario": "你要把 `/var/log/app` 下的日志归档到 `/backup/logs/2026-09-24/`。该目录中已存在同名备份文件，**不能覆盖**它们。",
                "context": (
                    "```text\n"
                    "/var/log/app/\n"
                    "├── api.log\n"
                    "└── worker.log\n\n"
                    "/backup/logs/2026-09-24/\n"
                    "└── api.log   ← 已存在，不可覆盖\n"
                    "```"
                ),
                "prompt": "用一条命令完成归档，要求遇到同名文件时跳过而非覆盖。",
                "answer_display": "cp -n /var/log/app/*.log /backup/logs/2026-09-24/",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["cp", "-n"]},
                "explanation": "`-n`（`--no-clobber`）让 cp 在目标已存在时静默跳过，不覆盖也不报错。",
                "pitfalls": "`cp -f` 是**强制覆盖**，与需求正好相反；不带任何选项的 cp 同样直接覆盖且无提示。",
                "safer_alt": "需要人工确认时用 `-i`；需要保留权限与时间戳时用 `-a`。",
                "difficulty": 2,
                "xp_reward": 40,
                "commands": ["cp", "mkdir"],
                "options": [],
            },
            {
                "kind": "judge",
                "title": "评估 rm -rf 的风险",
                "scenario": "同事为了「清理旧日志」，准备执行 `rm -rf /var/log/app/`。你需要在他按下回车前判断这条命令的实际后果。",
                "context": "```shell\n$ rm -rf /var/log/app/\n```",
                "prompt": "关于这条命令，下列判断哪一项正确？",
                "answer_display": "它会删除该目录及其全部内容，且不可恢复。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "`-r` 递归处理子目录，`-f` 强制且不提示，两者叠加意味着整棵目录树被静默删除。",
                "pitfalls": "在 `rm -rf` 里多打一个空格（如 `rm -rf /var/log/app /`）会造成灾难性后果；路径变量为空时同理。",
                "safer_alt": "删除前先用 `ls` 或 `find` 确认范围；能移入回收站就不要直接删；关键目录先做快照。",
                "difficulty": 2,
                "xp_reward": 40,
                "commands": ["rm"],
                "options": [
                    {"key": "A", "text": "删除 `/var/log/app` 目录及其全部内容，且不可恢复", "is_correct": True},
                    {"key": "B", "text": "只删除该目录下的空目录", "is_correct": False},
                    {"key": "C", "text": "删除前会自动备份到 `/tmp`", "is_correct": False},
                    {"key": "D", "text": "每个文件都会先提示确认", "is_correct": False},
                ],
            },
            {
                "kind": "fill",
                "title": "快速巩固 · 创建多级目录",
                "scenario": "目标目录的父级尚不存在。",
                "context": "",
                "prompt": "补全命令，一次性创建多级目录 `/backup/logs/2026-09-24`：`mkdir -____ /backup/logs/2026-09-24`",
                "answer_display": "mkdir -p /backup/logs/2026-09-24",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["mkdir", "-p"]},
                "explanation": "`-p`（`--parents`）自动创建缺失的中间目录，且目标已存在时也不报错。",
                "pitfalls": "不加 `-p` 时，父目录不存在会直接失败并返回非零退出码。",
                "safer_alt": "",
                "difficulty": 1,
                "xp_reward": 20,
                "commands": ["mkdir"],
                "options": [],
            },
        ],
    },
    {
        "order": 4,
        "zone": "文件工坊",
        "title": "文本内容追踪",
        "goal": "从配置与日志中定位异常内容并查看上下文。",
        "knowledge": (
            "查看文本的三种粒度：**整体**（`cat` / `less`）、**首尾**（`head` / `tail`）、**匹配行**（`grep`）。\n\n"
            "`grep` 常用组合：\n\n"
            "| 选项 | 作用 |\n"
            "| --- | --- |\n"
            "| `-r` | 递归搜索目录 |\n"
            "| `-n` | 输出行号 |\n"
            "| `-C N` | 显示匹配行前后各 N 行 |\n"
            "| `-A N` / `-B N` | 只显示后 N 行 / 前 N 行 |\n"
            "| `-i` | 忽略大小写 |\n\n"
            "大文件不要用 `cat`，会刷屏并拖慢终端；`less` 支持 `/` 搜索、`G` 跳到末尾、`q` 退出。"
        ),
        "quests": [
            {
                "kind": "terminal",
                "title": "定位错误的环境变量",
                "scenario": "多个配置文件里有一处错误的环境变量 `API_BASE`。你需要找出它在哪个文件的第几行，并看到前后各 2 行上下文。",
                "context": (
                    "```text\n"
                    "/srv/app/config/\n"
                    "├── app.yml\n"
                    "├── database.yml\n"
                    "└── redis.yml\n"
                    "```"
                ),
                "prompt": "用一条命令递归搜索 `/srv/app/config` 下的 `API_BASE`，输出行号与前后各 2 行。",
                "answer_display": "grep -rn -C 2 API_BASE /srv/app/config",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["grep", "-C", "API_BASE"]},
                "explanation": "`-r` 递归目录，`-n` 输出行号，`-C 2` 显示匹配行前后各 2 行。",
                "pitfalls": "只写 `grep API_BASE /srv/app/config` 而不加 `-r`，grep 遇到目录会报 `Is a directory` 并跳过。",
                "safer_alt": "上下文可用 `-A`（后）和 `-B`（前）精确控制；二进制文件加 `-I` 跳过，避免污染终端。",
                "difficulty": 2,
                "xp_reward": 40,
                "commands": ["grep", "cat"],
                "options": [],
            },
            {
                "kind": "terminal",
                "title": "实时跟踪服务日志",
                "scenario": "你刚重启了 API 服务，需要实时观察日志尾部的新增内容，确认启动是否正常。",
                "context": "",
                "prompt": "用一条命令持续输出 `/var/log/app/api.log` 的新增内容。",
                "answer_display": "tail -f /var/log/app/api.log",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["tail", "-f"]},
                "explanation": "`-f`（`--follow`）在打印完末尾内容后保持文件打开，持续输出后续追加的行。",
                "pitfalls": "`cat` 会一次性打印全文后退出，看不到新增内容；日志发生轮转后 `-f` 可能跟丢文件。",
                "safer_alt": "日志会轮转时用 `tail -F`（大写），它在文件被删除重建后会重新打开。",
                "difficulty": 1,
                "xp_reward": 40,
                "commands": ["tail", "less"],
                "options": [],
            },
            {
                "kind": "choice",
                "title": "快速巩固 · 取样大文件",
                "scenario": "一个 200MB 的日志文件，你只想确认开头是否包含版本号。",
                "context": "",
                "prompt": "下列哪条命令最合适？",
                "answer_display": "head -n 20 /var/log/app/api.log",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "`head -n N` 只输出前 N 行，是取样大文件最快的方式。",
                "pitfalls": "对大文件直接用 `cat` 会把 200MB 全打到终端，严重拖慢会话。",
                "safer_alt": "需要交互浏览用 `less`：`/` 搜索、`G` 跳到末尾、`q` 退出。",
                "difficulty": 1,
                "xp_reward": 20,
                "commands": ["head", "cat", "less"],
                "options": [
                    {"key": "A", "text": "`head -n 20 /var/log/app/api.log`", "is_correct": True},
                    {"key": "B", "text": "`cat /var/log/app/api.log`", "is_correct": False},
                    {"key": "C", "text": "`tail -f /var/log/app/api.log`", "is_correct": False},
                    {"key": "D", "text": "`wc -l /var/log/app/api.log`", "is_correct": False},
                ],
            },
        ],
    },
]
