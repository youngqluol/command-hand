"""故障指挥中心：单元 20–21。"""

UNITS = [
    {
        "order": 20,
        "zone": "故障指挥中心",
        "title": "深夜发布故障",
        "goal": "从 502 开始，按服务、端口、反向代理的顺序完成链式排障。",
        "knowledge": (
            "页面 502 表示**反向代理无法从上游拿到有效响应**。排障要沿着请求链路走，而不是随机试命令。\n\n"
            "推荐顺序：\n\n"
            "1. **确认现象范围** —— 全部接口 502，还是个别路由？\n"
            "2. **上游服务状态** —— `systemctl status <服务>` / `docker ps`\n"
            "3. **上游端口监听** —— `ss -ltnp | grep <端口>`\n"
            "4. **上游日志** —— `journalctl -u <服务> -n 100` / `docker logs --tail 100`\n"
            "5. **反向代理日志** —— Nginx 的 `error.log` 会写明具体原因（连接被拒 / 超时 / 上游返回异常）\n"
            "6. **代理配置** —— `nginx -t` 校验语法，确认 `proxy_pass` 指向正确\n\n"
            "**关键原则：每一步都要有证据，再决定下一步。** 盲目重启会清掉现场，让根因更难定位。"
        ),
        "quests": [
            {
                "kind": "terminal",
                "title": "确认上游服务状态",
                "scenario": "发布完成后页面返回 502。你已知反向代理正常，需要先确认上游 API 服务本身的运行状态。",
                "context": "```text\n502 Bad Gateway\nnginx/1.27.0\n```",
                "prompt": "用一条命令查看 `shellquest-api` 服务的运行状态。",
                "answer_display": "systemctl status shellquest-api",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["systemctl", "status"]},
                "explanation": "502 的第一嫌疑对象是上游服务。`systemctl status` 能立刻给出「是否运行」「退出码」「最近日志」三项关键信息。",
                "pitfalls": "看到 502 就直接重启 Nginx，但 Nginx 只是转发方，重启它通常不解决任何问题，还会丢失现场。",
                "safer_alt": "如果服务在容器里，改用 `docker ps -a` 与 `docker logs --tail 100 <容器>`。",
                "difficulty": 2,
                "xp_reward": 40,
                "commands": ["systemctl", "journalctl", "docker"],
                "options": [],
            },
            {
                "kind": "choice",
                "title": "下一步查什么",
                "scenario": "你已经确认：`shellquest-api` 服务处于 `active (running)`，但页面仍然 502。",
                "context": (
                    "```shell\n"
                    "$ systemctl status shellquest-api\n"
                    "Active: active (running) since Thu 2026-09-24 23:41:02 CST\n"
                    "```"
                ),
                "prompt": "下一步最应该验证什么？",
                "answer_display": "服务是否真的在监听配置的端口。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "服务进程存在不代表端口已就绪 —— 可能仍在初始化、绑定失败、或监听了与代理配置不一致的端口。查 `ss -ltnp` 能直接验证。",
                "pitfalls": "看到 `active (running)` 就断定服务正常，直接跳到检查代理配置，会漏掉「进程在但端口没起来」这种最常见的情况。",
                "safer_alt": "同时用 `curl -I http://127.0.0.1:8000/health` 从本机直接打上游，绕开代理判断问题在不在上游。",
                "difficulty": 3,
                "xp_reward": 40,
                "commands": ["ss", "curl", "systemctl"],
                "options": [
                    {"key": "A", "text": "服务是否真的在监听配置的端口", "is_correct": True},
                    {"key": "B", "text": "重启服务器", "is_correct": False},
                    {"key": "C", "text": "检查数据库连接池", "is_correct": False},
                    {"key": "D", "text": "重新发布一次", "is_correct": False},
                ],
            },
            {
                "kind": "fill",
                "title": "快速巩固 · 校验代理配置",
                "scenario": "修改了 Nginx 配置，需要在不中断服务的前提下先校验语法。",
                "context": "",
                "prompt": "补全命令：`____ -t` 校验 Nginx 配置语法。",
                "answer_display": "nginx -t",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["nginx", "-t"]},
                "explanation": "`nginx -t` 只做语法与路径检查，不加载新配置、不中断现有连接，是改配置后的必要前置步骤。",
                "pitfalls": "跳过校验直接 `restart`，配置有误会导致整个入口服务起不来，从 502 升级为全站不可用。",
                "safer_alt": "校验通过后用 `systemctl reload nginx` 平滑重载，避免丢弃正在处理的连接。",
                "difficulty": 2,
                "xp_reward": 20,
                "commands": ["nginx", "systemctl"],
                "options": [],
            },
        ],
    },
    {
        "order": 21,
        "zone": "故障指挥中心",
        "title": "终局演练",
        "goal": "在多重故障现场收集证据，并选择最小风险的处理方案。",
        "knowledge": (
            "多个故障同时出现时，**先判断它们之间是否存在因果链**，往往一个根因会引发连锁反应。\n\n"
            "典型链路：\n\n"
            "```text\n"
            "磁盘写满  →  容器无法写入  →  进程崩溃重启  →  接口超时\n"
            "```\n\n"
            "**处置原则**：\n\n"
            "1. **先取证，后动手** —— 重启会清掉现场。\n"
            "2. **先止血，后根治** —— 优先恢复可用性，再定位根因。\n"
            "3. **最小风险操作优先** —— 能清理临时文件就不要删目录；能重启单个容器就不要重启整机。\n"
            "4. **每次只改一个变量** —— 同时改多处会让你无法判断是哪一步起了作用。\n"
            "5. **留下操作记录** —— 记下时间点与执行内容，事后复盘依赖它。"
        ),
        "quests": [
            {
                "kind": "choice",
                "title": "先做什么",
                "scenario": "开发机同时出现三个现象：磁盘使用率 100%、容器反复重启、接口超时。你只有几分钟窗口做第一次处置。",
                "context": (
                    "```text\n"
                    "现象 1：df -h 显示 / 分区 Use% = 100%\n"
                    "现象 2：docker ps 显示 api 容器 Restarting (1) 3 seconds ago\n"
                    "现象 3：curl 接口超时\n"
                    "```"
                ),
                "prompt": "第一步最合理的操作是什么？",
                "answer_display": "先确认磁盘占用分布，判断是否为根因，再决定清理对象。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "三个现象高度可能是同一条因果链：磁盘写满导致容器崩溃重启，进而接口超时。先确认磁盘占用分布，才能判断清理目标，且这是只读操作，风险为零。",
                "pitfalls": "先重启服务器看似「一招解决」，实际会清掉容器日志与进程状态，让根因无从查证，且磁盘仍会很快写满。",
                "safer_alt": "确认是日志占满后，先清可再生的日志（`journalctl --vacuum-size=500M` 或截断应用日志），而不是删除数据目录。",
                "difficulty": 3,
                "xp_reward": 40,
                "commands": ["df", "du", "docker"],
                "options": [
                    {"key": "A", "text": "先 `df -h` 与 `du` 确认磁盘占用分布", "is_correct": True},
                    {"key": "B", "text": "直接重启整台服务器", "is_correct": False},
                    {"key": "C", "text": "先 `rm -rf /var/log/*` 清理日志", "is_correct": False},
                    {"key": "D", "text": "先扩容磁盘再观察", "is_correct": False},
                ],
            },
            {
                "kind": "judge",
                "title": "清理方案的选择",
                "scenario": "已确认 `/var/log` 下的应用日志占了 40GB。其中包含一个正在被进程写入的 `app.log`，以及若干归档文件。",
                "context": (
                    "```shell\n"
                    "$ du -sh /var/log/*\n"
                    "4.0K  /var/log/app/app.log\n"
                    "38G   /var/log/app/archive/\n"
                    "```"
                ),
                "prompt": "下列处置方案哪一项风险最低且有效？",
                "answer_display": "先清理归档目录中已过期的日志文件，再评估是否需要调整轮转策略。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "归档文件是已轮转的历史日志，通常可安全清理；且占据了绝大部分空间，清理收益最高。保留正在写入的日志，避免影响进程。",
                "pitfalls": "直接删除正在被写入的 `app.log` 不会真正释放空间（进程仍持有文件句柄），还会丢失当前排障所需的现场。",
                "safer_alt": "清理后用 `df -h` 复核；随后调整 `logrotate` 策略，设定保留天数与总大小上限，避免复发。",
                "difficulty": 3,
                "xp_reward": 40,
                "commands": ["du", "df", "rm"],
                "options": [
                    {"key": "A", "text": "清理归档目录中已过期的日志文件", "is_correct": True},
                    {"key": "B", "text": "直接 `rm` 正在写入的 `app.log`", "is_correct": False},
                    {"key": "C", "text": "删除整个 `/var/log/app` 目录", "is_correct": False},
                    {"key": "D", "text": "什么都不做，等待自动轮转", "is_correct": False},
                ],
            },
            {
                "kind": "terminal",
                "title": "快速巩固 · 确认服务已恢复",
                "scenario": "清理完成后，需要确认容器已稳定运行、不再反复重启。",
                "context": "",
                "prompt": "用一条命令查看所有容器（含已退出的）及其状态。",
                "answer_display": "docker ps -a",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["docker", "ps"]},
                "explanation": "`docker ps -a` 列出全部容器及 `STATUS` 字段。状态显示 `Up N minutes` 且时间持续增长，说明已稳定；若仍是 `Restarting`，则根因未解决。",
                "pitfalls": "只看 `docker ps` 会漏掉已退出的容器 —— 而崩溃退出的容器恰恰是排查重点。",
                "safer_alt": "配合 `docker logs --tail 50 <容器>` 确认重启原因已消失。",
                "difficulty": 1,
                "xp_reward": 20,
                "commands": ["docker"],
                "options": [],
            },
        ],
    },
]
