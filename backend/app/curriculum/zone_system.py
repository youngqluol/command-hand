"""系统哨站：单元 05–09。"""

UNITS = [
    {
        "order": 5,
        "zone": "系统哨站",
        "title": "权限事故",
        "goal": "判断脚本无法执行是文件权限、属主还是目录权限导致的。",
        "knowledge": (
            "权限位 `rwx` 分三组：**属主 / 属组 / 其他人**。对**文件**和**目录**含义不同：\n\n"
            "| 位 | 对文件 | 对目录 |\n"
            "| --- | --- | --- |\n"
            "| `r` | 读取内容 | 列出目录内容 |\n"
            "| `w` | 修改内容 | 在目录中创建 / 删除文件 |\n"
            "| `x` | 作为程序执行 | **进入该目录**（cd） |\n\n"
            "常见误区：目录缺少 `x` 时，即使文件本身有 `x` 也无法执行，报 `Permission denied`。\n\n"
            "`chmod` 的数字写法：`r=4`、`w=2`、`x=1`，如 `755` = 属主 `rwx`、其余 `r-x`。"
        ),
        "quests": [
            {
                "kind": "terminal",
                "title": "部署脚本无法执行",
                "scenario": "部署脚本 `/srv/app/deploy.sh` 执行时报 `Permission denied`。你已确认文件属主是自己，需要**最小化**地修复权限，不要授予其他人写权限。",
                "context": (
                    "```shell\n"
                    "$ ls -l /srv/app/deploy.sh\n"
                    "-rw-r--r-- 1 deploy deploy 1204 Sep 24 10:02 /srv/app/deploy.sh\n"
                    "```"
                ),
                "prompt": "用一条命令给属主补上执行权限。",
                "answer_display": "chmod u+x /srv/app/deploy.sh",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["chmod", "deploy.sh"]},
                "explanation": "`u+x` 只给属主（user）增加执行位，权限从 `644` 变为 `744`，不扩大其他人的权限。",
                "pitfalls": "直接 `chmod 777` 会让任何用户都能改写这个脚本，等于给服务器开后门。",
                "safer_alt": "需要精确设定时用数字写法 `chmod 755`；属主不对时先 `chown` 再改权限。",
                "difficulty": 2,
                "xp_reward": 40,
                "commands": ["chmod", "chown", "ls"],
                "options": [],
            },
            {
                "kind": "judge",
                "title": "目录缺少执行位",
                "scenario": "一个目录权限是 `drw-r--r--`，里面的脚本本身有 `x` 权限。有同事认为这样就能执行脚本。",
                "context": "```shell\n$ ls -ld /srv/app/scripts\ndrw-r--r-- 2 deploy deploy 4096 Sep 24 10:11 /srv/app/scripts\n```",
                "prompt": "关于「能否进入该目录并执行其中的脚本」，下列判断哪一项正确？",
                "answer_display": "无法进入该目录，因此脚本也执行不了。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "对目录而言 `x` 表示「可进入（可搜索路径）」。目录缺 `x` 时既无法 `cd` 进入，也无法按路径访问其中的文件。",
                "pitfalls": "只盯着文件自身的权限，忽略父目录权限，是权限排障最常见的漏检点。",
                "safer_alt": "排障时对目标路径的**每一级目录**都执行 `namei -l <路径>`，一次性看清全部权限。",
                "difficulty": 3,
                "xp_reward": 40,
                "commands": ["chmod", "ls"],
                "options": [
                    {"key": "A", "text": "无法进入该目录，因此脚本也执行不了", "is_correct": True},
                    {"key": "B", "text": "可以执行，因为脚本自身有 `x` 权限", "is_correct": False},
                    {"key": "C", "text": "可以执行，但看不到脚本内容", "is_correct": False},
                    {"key": "D", "text": "需要 root 才能判断", "is_correct": False},
                ],
            },
            {
                "kind": "fill",
                "title": "快速巩固 · 数字权限",
                "scenario": "把脚本权限设为属主可读写执行、其他用户只读可执行。",
                "context": "",
                "prompt": "补全命令：`chmod ____ /srv/app/deploy.sh`（属主 `rwx`，属组与其他 `r-x`）。",
                "answer_display": "chmod 755 /srv/app/deploy.sh",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["chmod", "755"]},
                "explanation": "`r=4`、`w=2`、`x=1`。`rwx` = 4+2+1 = 7，`r-x` = 4+0+1 = 5，故为 `755`。",
                "pitfalls": "写成 `775` 会给属组写权限；`777` 则给所有人写权限，两者都超出需求。",
                "safer_alt": "",
                "difficulty": 1,
                "xp_reward": 20,
                "commands": ["chmod"],
                "options": [],
            },
        ],
    },
    {
        "order": 6,
        "zone": "系统哨站",
        "title": "用户与访问",
        "goal": "为新同事配置受限访问，避免授予过高权限。",
        "knowledge": (
            "| 命令 | 作用 |\n"
            "| --- | --- |\n"
            "| `id <用户>` | 查看 UID、GID 与附加组 |\n"
            "| `groups <用户>` | 只看所属组 |\n"
            "| `useradd` | 创建用户（`-m` 建家目录，`-G` 指定附加组） |\n"
            "| `usermod -aG` | 追加附加组（**`-a` 不能省**） |\n"
            "| `sudo -l -U <用户>` | 查看该用户被授权的 sudo 范围 |\n\n"
            "给权限的正确顺序是：**先看现状**（`id`）→ **加最小必要组**（`usermod -aG`）→ **验证**（`id` 复查）。\n\n"
            "`usermod -G`（不带 `-a`）会**覆盖**用户已有的附加组，是常见的误操作。"
        ),
        "quests": [
            {
                "kind": "terminal",
                "title": "确认新同事的实际权限",
                "scenario": "新同事 `lisi` 说自己「应该已经有日志目录权限了」，但访问仍然失败。在改任何配置前，先确认他当前的组成员关系。",
                "context": "",
                "prompt": "用一条命令查看 `lisi` 的 UID、GID 与所属的全部组。",
                "answer_display": "id lisi",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["id", "lisi"]},
                "explanation": "`id <用户>` 一次性给出 UID、主组 GID 以及全部附加组，是判断权限的第一手证据。",
                "pitfalls": "只看 `/etc/passwd` 或只问本人，都可能漏掉附加组信息。",
                "safer_alt": "只想确认组关系时用 `groups lisi`；想看 sudo 授权范围用 `sudo -l -U lisi`。",
                "difficulty": 1,
                "xp_reward": 40,
                "commands": ["id", "groups"],
                "options": [],
            },
            {
                "kind": "judge",
                "title": "追加组还是覆盖组",
                "scenario": "`zhangsan` 当前已属于 `docker` 和 `developers` 两个组。你需要再把他加入 `logreaders` 组。同事给出的命令是 `usermod -G logreaders zhangsan`。",
                "context": (
                    "```shell\n"
                    "$ id zhangsan\n"
                    "uid=1002(zhangsan) gid=1002(zhangsan) groups=1002(zhangsan),998(docker),1003(developers)\n"
                    "```"
                ),
                "prompt": "关于这条命令的后果，下列判断哪一项正确？",
                "answer_display": "它会覆盖附加组，导致 zhangsan 失去 docker 与 developers。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "`-G` 是「设定附加组列表」而非「追加」。不加 `-a` 时，原有附加组会被整体替换。",
                "pitfalls": "把 `usermod -aG` 误写成 `usermod -G`，会静默剥夺用户已有权限，且当时不报错。",
                "safer_alt": "正确写法是 `usermod -aG logreaders zhangsan`，改完再用 `id zhangsan` 复查。",
                "difficulty": 3,
                "xp_reward": 40,
                "commands": ["usermod", "id", "groups"],
                "options": [
                    {"key": "A", "text": "覆盖附加组，zhangsan 会失去 docker 与 developers", "is_correct": True},
                    {"key": "B", "text": "追加附加组，三个组都会保留", "is_correct": False},
                    {"key": "C", "text": "命令报错，因为用户已存在", "is_correct": False},
                    {"key": "D", "text": "只修改主组，不影响附加组", "is_correct": False},
                ],
            },
            {
                "kind": "choice",
                "title": "快速巩固 · 最小权限",
                "scenario": "新同事只需要读取 `/var/log/app` 下的日志，不需要写、不需要 sudo。",
                "context": "",
                "prompt": "下列做法哪一项最符合最小权限原则？",
                "answer_display": "把他加入专门的日志读取组，并给该组目录读权限。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "用组来授权可以集中管理，且只授予 `r`，范围最小、可回收。",
                "pitfalls": "直接把用户加入 `sudo` 组或 `root` 组，会让一次日志排查演变成完全的服务器控制权。",
                "safer_alt": "确实需要提权执行个别命令时，在 `/etc/sudoers.d/` 中限定具体命令，而非给全量 sudo。",
                "difficulty": 2,
                "xp_reward": 20,
                "commands": ["usermod", "chmod", "sudo"],
                "options": [
                    {"key": "A", "text": "加入专门的日志读取组，并给该组目录读权限", "is_correct": True},
                    {"key": "B", "text": "加入 `sudo` 组，方便随时排查", "is_correct": False},
                    {"key": "C", "text": "把日志目录改成 `777`", "is_correct": False},
                    {"key": "D", "text": "把日志文件复制一份到他的家目录", "is_correct": False},
                ],
            },
        ],
    },
    {
        "order": 7,
        "zone": "系统哨站",
        "title": "失控的进程",
        "goal": "定位占用 CPU 的进程并安全结束。",
        "knowledge": (
            "排查顺序：**先定位 PID，再确认它是什么，最后才决定如何处理**。\n\n"
            "| 命令 | 作用 |\n"
            "| --- | --- |\n"
            "| `ps aux --sort=-%cpu` | 按 CPU 降序排列进程 |\n"
            "| `pgrep -a <名称>` | 按名称查 PID，并显示命令行 |\n"
            "| `top` / `htop` | 实时监控 |\n"
            "| `kill <PID>` | 发送 `SIGTERM`（15），请求优雅退出 |\n"
            "| `kill -9 <PID>` | 发送 `SIGKILL`，内核强制终止，**不可被捕获** |\n\n"
            "`SIGTERM` 给进程清理资源的机会；`SIGKILL` 不给。**先 15，无效再 9**，"
            "顺序颠倒可能导致数据未落盘或锁文件残留。"
        ),
        "quests": [
            {
                "kind": "terminal",
                "title": "找出吃满 CPU 的进程",
                "scenario": "监控告警显示这台机器 CPU 使用率持续 100%。你需要先拿到占用最高的进程列表，看清 PID、CPU 占比与完整命令。",
                "context": "",
                "prompt": "用一条命令按 CPU 占用从高到低列出全部进程。",
                "answer_display": "ps aux --sort=-%cpu",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["ps", "-%cpu"]},
                "explanation": "`ps aux` 输出全部进程的详细字段，`--sort=-%cpu` 中的负号表示降序。",
                "pitfalls": "只看 `top` 的动态画面容易漏掉瞬时尖峰；不带排序的 `ps aux` 输出过长，人工很难定位。",
                "safer_alt": "已知道进程名时用 `pgrep -a <名称>` 直接拿 PID 与命令行，比全量排序更快。",
                "difficulty": 2,
                "xp_reward": 40,
                "commands": ["ps", "top", "pgrep"],
                "options": [],
            },
            {
                "kind": "judge",
                "title": "该用哪个信号",
                "scenario": "一个 Python 数据处理进程卡死，正在写一个中间结果文件。你希望尽量让它把缓冲区刷盘后再退出。",
                "context": "",
                "prompt": "下列处理顺序哪一项最合理？",
                "answer_display": "先 kill 发送 SIGTERM，等待观察，无效再用 kill -9。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "`SIGTERM` 可被进程捕获，让它有机会刷盘、释放锁、关闭连接；`SIGKILL` 由内核直接终止，进程无法做任何收尾。",
                "pitfalls": "上来就 `kill -9`，可能留下写坏的中间文件和未释放的锁，反而增加恢复成本。",
                "safer_alt": "先确认进程身份（`ps -p <PID> -o pid,user,cmd`），避免误杀同名进程；必要时用 `kill -l` 查看信号列表。",
                "difficulty": 2,
                "xp_reward": 40,
                "commands": ["kill", "ps", "pgrep"],
                "options": [
                    {"key": "A", "text": "先 `kill <PID>` 发送 SIGTERM，观察后再考虑 `-9`", "is_correct": True},
                    {"key": "B", "text": "直接 `kill -9 <PID>`，最快", "is_correct": False},
                    {"key": "C", "text": "直接重启整台服务器", "is_correct": False},
                    {"key": "D", "text": "等它自己结束，不做处理", "is_correct": False},
                ],
            },
            {
                "kind": "fill",
                "title": "快速巩固 · 按名称查 PID",
                "scenario": "已知进程名，需要拿到它的 PID。",
                "context": "",
                "prompt": "补全命令：`____ -a nginx` 按名称查找 nginx 的 PID 并显示命令行。",
                "answer_display": "pgrep -a nginx",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["pgrep"]},
                "explanation": "`pgrep` 按名称匹配进程，`-a`（`--list-full`）同时输出完整命令行，便于确认是不是目标进程。",
                "pitfalls": "`pgrep` 默认只匹配进程名的前若干字符，可能命中多个无关进程，务必看 `-a` 输出的命令行。",
                "safer_alt": "",
                "difficulty": 1,
                "xp_reward": 20,
                "commands": ["pgrep"],
                "options": [],
            },
        ],
    },
    {
        "order": 8,
        "zone": "系统哨站",
        "title": "服务没有启动",
        "goal": "从 systemd 状态与日志中定位服务启动失败的原因。",
        "knowledge": (
            "`systemctl` 管状态，`journalctl` 看日志，两者配合才能定位启动失败。\n\n"
            "| 命令 | 作用 |\n"
            "| --- | --- |\n"
            "| `systemctl status <服务>` | 当前状态 + 最近几行日志 |\n"
            "| `systemctl is-enabled <服务>` | 是否开机自启 |\n"
            "| `systemctl cat <服务>` | 查看单元文件内容 |\n"
            "| `journalctl -u <服务> -n 50` | 该服务最近 50 行日志 |\n"
            "| `journalctl -u <服务> -f` | 实时跟踪该服务日志 |\n"
            "| `journalctl -u <服务> --since '10 min ago'` | 按时间窗口筛选 |\n\n"
            "常见失败原因：配置文件语法错误、端口被占用、依赖服务未启动、工作目录或权限不对。"
        ),
        "quests": [
            {
                "kind": "terminal",
                "title": "API 重启后不可用",
                "scenario": "`shellquest-api` 服务重启后一直没有响应。你需要先确认服务的当前状态与退出原因。",
                "context": "",
                "prompt": "用一条命令查看 `shellquest-api` 的状态与最近的日志摘要。",
                "answer_display": "systemctl status shellquest-api",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["systemctl", "status"]},
                "explanation": "`systemctl status` 一次给出：是否运行中、主 PID、退出码，以及最近若干行日志，是排查的第一步。",
                "pitfalls": "直接 `systemctl restart` 反复重启，会覆盖掉失败现场，让日志里的关键报错更难定位。",
                "safer_alt": "状态里信息不够时用 `journalctl -u shellquest-api -n 50 --no-pager` 看完整最近日志。",
                "difficulty": 1,
                "xp_reward": 40,
                "commands": ["systemctl", "journalctl"],
                "options": [],
            },
            {
                "kind": "choice",
                "title": "按时间窗口筛日志",
                "scenario": "服务是十分钟前重启的，你想只看这十分钟内的日志，避免翻到几天前的历史记录。",
                "context": "",
                "prompt": "下列哪条命令最合适？",
                "answer_display": "journalctl -u shellquest-api --since '10 min ago'",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "`--since` 按时间起点过滤，配合 `-u` 限定服务，能快速把范围收敛到故障窗口。",
                "pitfalls": "不带 `-u` 的 `journalctl` 会输出整机日志，噪音极大；`--since` 的时间格式要加引号。",
                "safer_alt": "配合 `--until` 可限定结束时间；加 `-p err` 只看错误级别及以上。",
                "difficulty": 2,
                "xp_reward": 40,
                "commands": ["journalctl"],
                "options": [
                    {"key": "A", "text": "`journalctl -u shellquest-api --since '10 min ago'`", "is_correct": True},
                    {"key": "B", "text": "`journalctl --since '10 min ago'`", "is_correct": False},
                    {"key": "C", "text": "`cat /var/log/syslog`", "is_correct": False},
                    {"key": "D", "text": "`systemctl restart shellquest-api`", "is_correct": False},
                ],
            },
            {
                "kind": "fill",
                "title": "快速巩固 · 开机自启",
                "scenario": "服务能手动启动，但重启机器后不会自动运行。",
                "context": "",
                "prompt": "补全命令：`systemctl ____ shellquest-api` 设置开机自启。",
                "answer_display": "systemctl enable shellquest-api",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["systemctl", "enable"]},
                "explanation": "`enable` 建立开机自启的符号链接；`disable` 取消。`start` / `stop` 只管当前运行状态。",
                "pitfalls": "把 `start` 当成自启设置，是新手最常见的混淆 —— 它只在本次运行期间生效。",
                "safer_alt": "改完用 `systemctl is-enabled shellquest-api` 验证结果。",
                "difficulty": 1,
                "xp_reward": 20,
                "commands": ["systemctl"],
                "options": [],
            },
        ],
    },
    {
        "order": 9,
        "zone": "系统哨站",
        "title": "磁盘告警",
        "goal": "判断是哪个分区、哪个目录占满了磁盘。",
        "knowledge": (
            "定位磁盘占用的两步法：**先找分区，再找目录**。\n\n"
            "| 命令 | 作用 |\n"
            "| --- | --- |\n"
            "| `df -h` | 各分区已用 / 可用空间（人类可读） |\n"
            "| `df -i` | inode 使用率（**空间没满但 inode 耗尽**也会写入失败） |\n"
            "| `du -sh <目录>` | 统计目录总大小 |\n"
            "| `du -h --max-depth=1 <目录>` | 只看下一级各子目录大小 |\n\n"
            "`df` 看的是**文件系统**层面，`du` 看的是**目录**层面，两者结果可能不一致"
            "（被删除但仍被进程占用的文件不计入 `du`，却仍占用 `df` 的空间）。"
        ),
        "quests": [
            {
                "kind": "terminal",
                "title": "找出写满的分区",
                "scenario": "监控告警：某台服务器磁盘空间不足。你需要先确认是哪个挂载点写满了。",
                "context": "",
                "prompt": "用一条命令以人类可读单位列出所有分区的使用情况。",
                "answer_display": "df -h",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["df", "-h"]},
                "explanation": "`df -h` 按挂载点列出容量、已用、可用与使用率，`-h` 把字节数转成 GB / MB，便于快速扫读。",
                "pitfalls": "只盯着 `Use%` 会漏掉 inode 耗尽的情况 —— 那种场景下 `df -h` 显示空间充足，写入却仍然失败。",
                "safer_alt": "怀疑 inode 问题时补一条 `df -i`。",
                "difficulty": 1,
                "xp_reward": 40,
                "commands": ["df", "du"],
                "options": [],
            },
            {
                "kind": "terminal",
                "title": "定位最占空间的子目录",
                "scenario": "已确认 `/` 分区写满。现在需要找出 `/var` 下哪个子目录占用最多，以便决定清理目标。",
                "context": "",
                "prompt": "用一条命令只看 `/var` 下一级各子目录的大小。",
                "answer_display": "du -h --max-depth=1 /var",
                "judge_type": "contains_all",
                "judge_payload": {"terms": ["du", "/var"]},
                "explanation": "`--max-depth=1` 把输出限制在下一级，避免递归列出成千上万行；`-h` 输出人类可读单位。",
                "pitfalls": "直接 `du -sh /var` 只给出一个总数，无法判断该清理哪个子目录；不带 `--max-depth` 会输出海量行。",
                "safer_alt": "结果过多时用 `du -h --max-depth=1 /var | sort -h` 按大小排序，最大的排最后。",
                "difficulty": 2,
                "xp_reward": 40,
                "commands": ["du", "sort", "df"],
                "options": [],
            },
            {
                "kind": "choice",
                "title": "快速巩固 · 空间没满却写不进去",
                "scenario": "`df -h` 显示 `/data` 只用了 60%，但应用写文件持续报 `No space left on device`。",
                "context": "",
                "prompt": "下一步最应该检查什么？",
                "answer_display": "用 df -i 检查 inode 是否耗尽。",
                "judge_type": "option",
                "judge_payload": {"correct_keys": ["A"]},
                "explanation": "每个文件都占用一个 inode。大量小文件会先耗尽 inode，此时字节空间仍然充裕，但无法创建新文件。",
                "pitfalls": "看到「空间没满」就排除磁盘问题，会在这个方向上浪费大量时间。",
                "safer_alt": "确认是 inode 问题后，用 `find /data -type f | wc -l` 评估文件数量，定位小文件集中的目录。",
                "difficulty": 3,
                "xp_reward": 20,
                "commands": ["df", "find", "wc"],
                "options": [
                    {"key": "A", "text": "用 `df -i` 检查 inode 是否耗尽", "is_correct": True},
                    {"key": "B", "text": "直接扩容磁盘", "is_correct": False},
                    {"key": "C", "text": "重启应用", "is_correct": False},
                    {"key": "D", "text": "检查目录权限", "is_correct": False},
                ],
            },
        ],
    },
]
