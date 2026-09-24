"""Shell 作战室：单元 13–16。"""

UNITS = [
    {
        "order": 13,
        "zone": "Shell 作战室",
        "title": "日志筛查管道",
        "goal": "用管道组合筛选异常状态码并统计来源。",
        "knowledge": (
            "管道的本质是**把上一个命令的标准输出接到下一个命令的标准输入**，每个命令只做一件事。\n\n"
            "| 命令 | 作用 |\n"
            "| --- | --- |\n"
            "| `grep` | 按模式筛选行 |\n"
            "| `awk '{print $N}'` | 按列提取 |\n"
            "| `sort` | 排序（`-n` 按数值，`-r` 逆序） |\n"
            "| `uniq -c` | 统计**相邻**重复行出现次数 |\n"
            "| `wc -l` | 统计行数 |\n"
            "| `head -n N` | 取前 N 行 |\n\n"
            "**关键陷阱**：`uniq -c` 只统计**相邻**的重复行。要统计全局重复，必须**先 `sort` 再 `uniq`**。\n\n"
            "统计类任务的经典骨架：`grep 筛选 → awk 取列 → sort 排序 → uniq -c 计数 → sort -nr 排名`。"
        ),
        "quests": [
            {
                "kind": "terminal",
                "title": "统计 500 错误最多的来源 IP",
                "scenario": "线上出现大量 500 错误。你需要从访问日志中找出触发 500 次数最多的来源 IP。",
                "context": (
                    "```text\n"
                    "10.0.1.7 - - [24/Sep/2026:10:01:02 +0800] \"GET /api/orders HTTP/1.1\" 500 231\n"
                    "10.0.1.9 - - [24/Sep/2026:10:01:03 +0800] \"GET /health HTTP/1.1\" 200 12\n"
                    "10.0.1.7 - - [24/Sep/2026:10:01:05 +0800] \"POST /api/pay HTTP/1.1\" 500 231\n"
                    "```"
                ),
                "prompt": "写出完整的管道命令：筛选状态码 500 的请求，按来源 IP 统计次数并降序排列。",
                "answer_display": "grep ' 500 ' access.log | awk '{print $1}' | sort | uniq -c | sort -nr",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["grep", "awk", "sort", "uniq"]},
                "explanation": "`grep ' 500 '` 用两侧空格避免误匹配 `5000` 之类的数字；`awk '{print $1}'` 取第一列 IP；`sort | uniq -c` 先排序再计数；最后 `sort -nr` 按次数降序排名。",
                "pitfalls": "漏掉第一个 `sort` 直接用 `uniq -c`，只会统计相邻重复行，结果完全错误且不会报错。",
                "safer_alt": "更精确的做法是按日志格式指定列：`awk '$9 == 500 {print $1}' access.log | sort | uniq -c | sort -nr`，避免 `grep` 匹配到请求体中的 500。",
                "difficulty": 3,
                "xp_reward": 40,
                "commands": ["grep", "awk", "sort", "uniq", "wc"],
                "options": [],
            },
            {
                "kind": "choice",
                "title": "uniq 为什么不生效",
                "scenario": "同事写了 `cat access.log | uniq -c | sort -nr | head`，想统计最频繁的日志行，但结果明显不对。",
                "context": "",
                "prompt": "问题出在哪里？",
                "answer_display": "uniq 只统计相邻重复行，必须先 sort。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "`uniq` 的设计前提是输入已排序。未排序时，同一内容的行分散在不同位置，各自只被计为 1。",
                "pitfalls": "这个错误不会报错、不会警告，只会安静地给出错误结果 —— 是管道类任务中最隐蔽的坑。",
                "safer_alt": "正确骨架是 `sort | uniq -c`；若只想统计总数，用 `wc -l` 更直接。",
                "difficulty": 2,
                "xp_reward": 40,
                "commands": ["uniq", "sort", "cat", "wc"],
                "options": [
                    {"key": "A", "text": "`uniq` 只统计相邻重复行，必须先 `sort`", "is_correct": True},
                    {"key": "B", "text": "`-c` 选项写错了", "is_correct": False},
                    {"key": "C", "text": "`cat` 不能配合管道使用", "is_correct": False},
                    {"key": "D", "text": "`head` 截断了统计结果", "is_correct": False},
                ],
            },
            {
                "kind": "fill",
                "title": "快速巩固 · 统计行数",
                "scenario": "只想确认日志总行数。",
                "context": "",
                "prompt": "补全命令：`wc -____ access.log` 统计文件行数。",
                "answer_display": "wc -l access.log",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["wc", "-l"]},
                "explanation": "`-l`（`--lines`）只输出行数，输出干净，便于在管道中继续处理。",
                "pitfalls": "不加选项的 `wc` 会同时输出行数、词数、字节数，脚本取值时需要额外裁剪。",
                "safer_alt": "",
                "difficulty": 1,
                "xp_reward": 20,
                "commands": ["wc"],
                "options": [],
            },
        ],
    },
    {
        "order": 14,
        "zone": "Shell 作战室",
        "title": "输出与错误",
        "goal": "同时保存标准输出与标准错误，便于复盘。",
        "knowledge": (
            "Linux 用文件描述符区分三类流：\n\n"
            "| 编号 | 名称 | 默认去向 |\n"
            "| --- | --- | --- |\n"
            "| `0` | 标准输入 stdin | 键盘 |\n"
            "| `1` | 标准输出 stdout | 终端 |\n"
            "| `2` | 标准错误 stderr | 终端 |\n\n"
            "重定向写法：\n\n"
            "| 写法 | 含义 |\n"
            "| --- | --- |\n"
            "| `> f` | 覆盖写入 stdout |\n"
            "| `>> f` | 追加写入 stdout |\n"
            "| `2> f` | 覆盖写入 stderr |\n"
            "| `2>&1` | 把 stderr 重定向到 stdout 当前指向的位置 |\n"
            "| `&> f` | stdout 与 stderr 都写入 f（bash 扩展） |\n"
            "| `\\| tee f` | 同时输出到终端与文件 |\n\n"
            "**顺序很重要**：`> f 2>&1` 表示「两者都进 f」；`2>&1 > f` 表示「stderr 先指向终端，再让 stdout 进 f」，结果 stderr 仍在终端。"
        ),
        "quests": [
            {
                "kind": "terminal",
                "title": "保存完整构建日志",
                "scenario": "构建任务失败，但终端只显示了错误信息，缺少上下文。你需要重新执行构建，把**正常输出与错误输出**都保存到 `build.log`，同时仍然在终端看到过程。",
                "context": "",
                "prompt": "写出完整命令，使 stdout 与 stderr 都写入 `build.log` 且终端仍可见。",
                "answer_display": "npm run build 2>&1 | tee build.log",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["2>&1", "tee"]},
                "explanation": "`2>&1` 先把 stderr 并入 stdout，`| tee build.log` 再把合并后的流同时写到文件和终端，两者都不丢。",
                "pitfalls": "只写 `> build.log` 会丢掉全部错误信息 —— 而错误恰恰是复盘时最需要的内容。",
                "safer_alt": "不需要实时观察时用 `&> build.log` 更简洁；需要保留上次日志时把 `>` 换成 `>>`。",
                "difficulty": 3,
                "xp_reward": 40,
                "commands": ["tee", "cat", "less"],
                "options": [],
            },
            {
                "kind": "judge",
                "title": "重定向的顺序",
                "scenario": "同事写了 `command 2>&1 > output.log`，期望把 stdout 和 stderr 都写进 `output.log`。实际执行后，错误信息仍然打印在终端上。",
                "context": "```shell\n$ command 2>&1 > output.log\n```",
                "prompt": "关于这个结果，下列解释哪一项正确？",
                "answer_display": "顺序反了：2>&1 先执行，此时 stdout 仍指向终端，所以 stderr 也留在终端。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "重定向**从左到右**生效。`2>&1` 执行时 stdout 还没被改写，仍指向终端，于是 stderr 也指向终端；随后 `> output.log` 只改变了 stdout。",
                "pitfalls": "把 `2>&1` 当成「把两者合并」的固定咒语，不理解它复制的是**当前位置**，写反顺序却看不出错。",
                "safer_alt": "正确顺序是 `command > output.log 2>&1`；bash 下也可以用更直观的 `command &> output.log`。",
                "difficulty": 3,
                "xp_reward": 40,
                "commands": ["tee"],
                "options": [
                    {"key": "A", "text": "顺序反了：`2>&1` 先执行时 stdout 仍指向终端", "is_correct": True},
                    {"key": "B", "text": "`> output.log` 不支持同时写入两个流", "is_correct": False},
                    {"key": "C", "text": "应该改用 `>>`", "is_correct": False},
                    {"key": "D", "text": "这是命令本身的 bug", "is_correct": False},
                ],
            },
            {
                "kind": "fill",
                "title": "快速巩固 · 合并错误流",
                "scenario": "把标准错误并入标准输出。",
                "context": "",
                "prompt": "补全命令：`command ____ | grep ERROR` 让 grep 也能筛选到错误输出。",
                "answer_display": "command 2>&1 | grep ERROR",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["2>&1"]},
                "explanation": "管道默认只传递 stdout。`2>&1` 把 stderr 并入 stdout 后，才能被下游的 grep 看到。",
                "pitfalls": "不写 `2>&1` 时，错误信息绕过管道直接打到终端，grep 一条也筛不到。",
                "safer_alt": "",
                "difficulty": 2,
                "xp_reward": 20,
                "commands": ["grep"],
                "options": [],
            },
        ],
    },
    {
        "order": 15,
        "zone": "Shell 作战室",
        "title": "批量维护",
        "goal": "批量处理一组文件，避免逐个手工操作。",
        "knowledge": (
            "| 方式 | 特点 |\n"
            "| --- | --- |\n"
            "| `find ... -exec cmd {} \\;` | 每个文件调用一次 cmd |\n"
            "| `find ... -exec cmd {} +` | 批量传给一次 cmd，效率高 |\n"
            "| `find ... -print0 \\| xargs -0 cmd` | 同样批量，且**正确处理含空格的文件名** |\n"
            "| `xargs -n 1` | 每次只传一个参数 |\n\n"
            "**`xargs` 的经典坑**：默认按空白切分参数，文件名含空格时会被拆成多个参数。"
            "解法是用 `-print0` 配合 `xargs -0`，用 NUL 字符作为分隔符。\n\n"
            "**先用 `-n` / `echo` 演练**是批量操作的安全习惯。"
        ),
        "quests": [
            {
                "kind": "terminal",
                "title": "批量检查配置文件",
                "scenario": "`/srv/app/conf.d/` 下有上百个 `.conf` 文件，文件名可能包含空格。你需要对每个文件统计行数，避免逐个手工处理。",
                "context": "",
                "prompt": "用一条命令对目录下所有 `.conf` 文件统计行数，要求能正确处理含空格的文件名。",
                "answer_display": "find /srv/app/conf.d -name '*.conf' -print0 | xargs -0 wc -l",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["find", "xargs"]},
                "explanation": "`-print0` 用 NUL 分隔输出，`xargs -0` 按 NUL 解析参数，两者配对后即使文件名含空格或换行也不会被错误拆分。",
                "pitfalls": "直接 `find ... | xargs wc -l` 在遇到含空格的文件名时会把一个文件名拆成多个参数，报「文件不存在」或统计错误。",
                "safer_alt": "先加 `-n` 或把 `wc -l` 换成 `echo` 演练，确认文件清单无误再真正执行。",
                "difficulty": 3,
                "xp_reward": 40,
                "commands": ["find", "xargs", "wc"],
                "options": [],
            },
            {
                "kind": "judge",
                "title": "文件名含空格",
                "scenario": "目录里有一个名为 `my config.conf` 的文件。同事执行 `find . -name '*.conf' | xargs wc -l` 后，报错提示找不到 `my` 和 `config.conf`。",
                "context": (
                    "```shell\n"
                    "$ find . -name '*.conf' | xargs wc -l\n"
                    "wc: my: No such file or directory\n"
                    "wc: config.conf: No such file or directory\n"
                    "```"
                ),
                "prompt": "正确的修复方式是什么？",
                "answer_display": "改用 find -print0 配合 xargs -0。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "`xargs` 默认按空白切分输入，含空格的文件名会被拆成多个参数。`-print0` + `xargs -0` 改用 NUL 分隔，从根本上消除歧义。",
                "pitfalls": "给文件名加引号只是治标；真正的解法是改用 NUL 分隔符。",
                "safer_alt": "也可以完全避开 xargs：`find . -name '*.conf' -exec wc -l {} +`。",
                "difficulty": 3,
                "xp_reward": 40,
                "commands": ["find", "xargs"],
                "options": [
                    {"key": "A", "text": "改用 `find -print0` 配合 `xargs -0`", "is_correct": True},
                    {"key": "B", "text": "重命名文件去掉空格", "is_correct": False},
                    {"key": "C", "text": "把 `wc -l` 换成 `wc -c`", "is_correct": False},
                    {"key": "D", "text": "给 `xargs` 加 `-n 1`", "is_correct": False},
                ],
            },
            {
                "kind": "choice",
                "title": "快速巩固 · exec 的两种结尾",
                "scenario": "需要删除一批 `.tmp` 文件，你希望**尽量减少进程创建次数**。",
                "context": "",
                "prompt": "下列写法哪一种效率更高？",
                "answer_display": "find . -name '*.tmp' -exec rm {} +",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "`\\;` 对每个文件启动一次进程；`+` 把多个文件合并到一次调用，进程创建次数大幅减少。",
                "pitfalls": "文件数量大时用 `\\;` 会明显变慢，且大量进程创建本身也是负担。",
                "safer_alt": "删除前先用 `-print` 或 `echo` 替代 `rm` 演练一遍，确认匹配范围。",
                "difficulty": 2,
                "xp_reward": 20,
                "commands": ["find", "xargs", "rm"],
                "options": [
                    {"key": "A", "text": "`find . -name '*.tmp' -exec rm {} +`", "is_correct": True},
                    {"key": "B", "text": "`find . -name '*.tmp' -exec rm {} \\;`", "is_correct": False},
                    {"key": "C", "text": "`rm -rf .`", "is_correct": False},
                    {"key": "D", "text": "`find . -name '*.tmp'`", "is_correct": False},
                ],
            },
        ],
    },
    {
        "order": 16,
        "zone": "Shell 作战室",
        "title": "值班小脚本",
        "goal": "编写服务存活检查脚本，并输出机器可读的结果。",
        "knowledge": (
            "脚本的三块拼图：**变量**、**条件判断**、**退出码**。\n\n"
            "| 语法 | 作用 |\n"
            "| --- | --- |\n"
            "| `VAR=$(cmd)` | 把命令输出赋给变量 |\n"
            "| `if cmd; then ... fi` | 按命令退出码判断（`0` 为真） |\n"
            "| `exit N` | 以退出码 N 结束脚本 |\n"
            "| `set -euo pipefail` | 遇错退出 / 用未定义变量报错 / 管道任一环失败即失败 |\n\n"
            "**退出码约定**：`0` 表示成功，非 `0` 表示失败。监控系统靠这个值判断脚本结果，"
            "所以脚本**必须显式 `exit`**，不要依赖最后一条命令的隐式退出码。\n\n"
            "`curl -fsS` 的组合含义：`-f` 遇 4xx/5xx 返回非零、`-s` 静默、`-S` 静默但仍显示错误。"
        ),
        "quests": [
            {
                "kind": "terminal",
                "title": "检查服务是否存活",
                "scenario": "值班前需要确认 API 是否可用，并让结果能被监控系统读取：成功返回 `0`，失败返回非 `0`，且失败时能看到原因。",
                "context": "",
                "prompt": "用一条命令检查 `http://127.0.0.1:8000/health`，要求失败时返回非零退出码且输出错误信息。",
                "answer_display": "curl -fsS http://127.0.0.1:8000/health",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["curl", "127.0.0.1:8000/health"]},
                "explanation": "`-f` 让 curl 在 HTTP 4xx/5xx 时返回非零退出码，`-s` 去掉进度条，`-S` 保留错误信息。三者组合正好满足「可脚本判断 + 失败可读」。",
                "pitfalls": "只用 `curl -s` 时，服务返回 500 也会得到退出码 0，脚本会误判为健康。",
                "safer_alt": "只需状态码时用 `curl -s -o /dev/null -w '%{http_code}'`；需要超时控制时加 `--max-time 5`。",
                "difficulty": 3,
                "xp_reward": 40,
                "commands": ["curl", "bash"],
                "options": [],
            },
            {
                "kind": "judge",
                "title": "脚本退出码",
                "scenario": "监控系统只根据脚本的**退出码**判断服务状态。某脚本最后一行是 `echo \"服务正常\"`，中间没有任何 `exit`。",
                "context": (
                    "```shell\n"
                    "#!/usr/bin/env bash\n"
                    "curl -fsS http://127.0.0.1:8000/health\n"
                    "echo \"检查完成\"\n"
                    "```"
                ),
                "prompt": "关于这个脚本的退出码，下列判断哪一项正确？",
                "answer_display": "退出码由最后一条 echo 决定，永远是 0，监控无法发现故障。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "脚本的退出码是**最后一条命令**的退出码。`echo` 几乎总是成功返回 0，因此 curl 的失败被掩盖了。",
                "pitfalls": "在检查命令之后追加任何成功命令（echo、日志写入等），都会把失败信号吃掉。",
                "safer_alt": "用 `if curl -fsS ...; then echo ok; else echo fail; exit 1; fi` 显式控制退出码。",
                "difficulty": 3,
                "xp_reward": 40,
                "commands": ["curl", "bash"],
                "options": [
                    {"key": "A", "text": "退出码由最后的 `echo` 决定，恒为 0，故障被掩盖", "is_correct": True},
                    {"key": "B", "text": "退出码自动取 curl 的结果", "is_correct": False},
                    {"key": "C", "text": "脚本会报语法错误", "is_correct": False},
                    {"key": "D", "text": "退出码为 curl 与 echo 之和", "is_correct": False},
                ],
            },
            {
                "kind": "fill",
                "title": "快速巩固 · 命令替换",
                "scenario": "把命令输出存进变量。",
                "context": "",
                "prompt": "补全脚本，把当前时间存入变量：`NOW=____date____`（使用命令替换）。",
                "answer_display": "NOW=$(date)",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["$(", "date"]},
                "explanation": "`$(...)` 是命令替换，先执行括号内命令，再把其标准输出作为值赋给变量。",
                "pitfalls": "写成 `NOW=date` 会把字面量 `date` 赋给变量，而不是执行命令。",
                "safer_alt": "反引号 `` `date` `` 也能实现，但嵌套时可读性差，现代写法统一用 `$()`。",
                "difficulty": 2,
                "xp_reward": 20,
                "commands": ["date", "bash"],
                "options": [],
            },
        ],
    },
]
