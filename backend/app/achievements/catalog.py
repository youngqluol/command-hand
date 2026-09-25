"""成就目录：**纯数据，不含判定逻辑**。

判定引擎见 ``app/achievements/__init__.py``。这里只声明「有哪些成就、各自的条件是什么」，
与 ``app/curriculum/`` 存放课程内容是同一个思路 —— 内容与逻辑分开，改内容不必碰逻辑。

``code`` 是持久化标识（写入 ``user_achievements.code``），**一旦发布就不要再改**，
改名会让用户的历史解锁记录失联（见 AGENTS.md §4.9）。
"""

from __future__ import annotations

from dataclasses import dataclass

# 成就分组。顺序即前端展示顺序。
GROUP_STREAK = "坚持"
GROUP_CLEAR = "通关"
GROUP_PERFECT = "无错"
GROUP_GROWTH = "成长"

GROUP_ORDER = [GROUP_STREAK, GROUP_CLEAR, GROUP_PERFECT, GROUP_GROWTH]


@dataclass(frozen=True)
class Achievement:
    """一条成就定义。

    ``rule`` 决定判定方式，与 ``achievements/__init__.py`` 的 ``is_satisfied()`` 一一对应：

    ============== ==========================================================
    rule           ``value`` 的含义
    ============== ==========================================================
    streak         连续打卡天数 >= value
    units_cleared  已完成单元数 >= value
    zone_clear     指定区域（value = 区域名）内全部单元已完成
    zones_cleared  完全通关的区域数 >= value
    perfect_units  无错通关的单元数 >= value
    xp             累计经验 >= value
    level          等级 >= value
    ============== ==========================================================
    """

    code: str
    title: str
    description: str
    icon: str
    group: str
    rule: str
    value: int | str


# 视觉保持克制：以终端感符号与少量图标为主，不做重度游戏化（REQUIREMENTS.md §4.3）。
ACHIEVEMENTS: list[Achievement] = [
    # --- 坚持：连续打卡 ---------------------------------------------------- #
    Achievement("streak_3", "三日不辍", "连续打卡 3 天", "🔥", GROUP_STREAK, "streak", 3),
    Achievement("streak_7", "一周在线", "连续打卡 7 天", "🔥", GROUP_STREAK, "streak", 7),
    Achievement("streak_21", "廿一日之约", "连续打卡 21 天", "🏅", GROUP_STREAK, "streak", 21),
    # --- 通关：单元与区域 -------------------------------------------------- #
    Achievement("unit_first", "破冰", "完成第 1 个课程单元", "⚑", GROUP_CLEAR, "units_cleared", 1),
    Achievement("units_5", "五关斩将", "完成 5 个课程单元", "⚑", GROUP_CLEAR, "units_cleared", 5),
    Achievement("units_10", "十步芳草", "完成 10 个课程单元", "⚑", GROUP_CLEAR, "units_cleared", 10),
    Achievement(
        "units_all", "廿一天毕业", "完成全部 21 个课程单元", "🎓", GROUP_CLEAR, "units_cleared", 21
    ),
    Achievement(
        "zone_file", "文件工坊通关", "通关「文件工坊」全部单元", "📁", GROUP_CLEAR, "zone_clear", "文件工坊"
    ),
    Achievement(
        "zone_system", "系统哨站通关", "通关「系统哨站」全部单元", "⚙", GROUP_CLEAR, "zone_clear", "系统哨站"
    ),
    Achievement(
        "zone_network", "网络前线通关", "通关「网络前线」全部单元", "🌐", GROUP_CLEAR, "zone_clear", "网络前线"
    ),
    Achievement(
        "zone_shell",
        "Shell 作战室通关",
        "通关「Shell 作战室」全部单元",
        "🐚",
        GROUP_CLEAR,
        "zone_clear",
        "Shell 作战室",
    ),
    Achievement(
        "zone_container", "容器基地通关", "通关「容器基地」全部单元", "📦", GROUP_CLEAR, "zone_clear", "容器基地"
    ),
    Achievement(
        "zone_incident",
        "故障指挥中心通关",
        "通关「故障指挥中心」全部单元",
        "🚨",
        GROUP_CLEAR,
        "zone_clear",
        "故障指挥中心",
    ),
    Achievement("zones_all", "六区制霸", "通关全部 6 个主题区域", "🏆", GROUP_CLEAR, "zones_cleared", 6),
    # --- 无错：首次作答即正确 ---------------------------------------------- #
    Achievement(
        "perfect_unit", "一击即中", "某个单元内所有题目首次作答即正确", "🎯", GROUP_PERFECT, "perfect_units", 1
    ),
    Achievement(
        "perfect_units_3", "三连无错", "3 个单元全部首次作答即正确", "🎯", GROUP_PERFECT, "perfect_units", 3
    ),
    Achievement(
        "perfect_units_6", "六连无错", "6 个单元全部首次作答即正确", "💎", GROUP_PERFECT, "perfect_units", 6
    ),
    # --- 成长：经验与等级 -------------------------------------------------- #
    Achievement("xp_500", "初露锋芒", "累计获得 500 经验", "🌱", GROUP_GROWTH, "xp", 500),
    Achievement("xp_2000", "渐入佳境", "累计获得 2000 经验", "🌿", GROUP_GROWTH, "xp", 2000),
    Achievement("xp_5000", "登堂入室", "累计获得 5000 经验", "🌳", GROUP_GROWTH, "xp", 5000),
    Achievement("level_5", "LV.05 中级执令者", "达到等级 5", "⭐", GROUP_GROWTH, "level", 5),
    Achievement("level_10", "LV.10 传奇 ShellMaster", "达到等级 10", "👑", GROUP_GROWTH, "level", 10),
]

BY_CODE: dict[str, Achievement] = {item.code: item for item in ACHIEVEMENTS}

# 目录里出现重复 code 会让 BY_CODE 静默丢条目、并触发唯一约束报错，启动自检直接拦下。
if len(BY_CODE) != len(ACHIEVEMENTS):
    _dupes = sorted({item.code for item in ACHIEVEMENTS if [a.code for a in ACHIEVEMENTS].count(item.code) > 1})
    raise RuntimeError(f"成就目录存在重复 code：{_dupes}")
