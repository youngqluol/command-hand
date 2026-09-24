"""端到端冒烟测试：课程落库 → 认证 → 判题 → 解锁 → 命令手册 → 检索。

在**临时 SQLite 库**上跑完整链路，不碰开发库、不留文件。前端联调前先跑一遍，
可以快速确认后端接口没被改坏（见 AGENTS.md §2 常用命令）。

    cd backend && python scripts/smoke_test.py

依赖 `requirements-dev.txt` 里的 httpx（`fastapi.testclient.TestClient` 需要）。
退出码非 0 表示有断言失败。
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

# 必须在导入 app 之前设好 DATABASE_URL：`app.database` 在导入期就读取它建引擎。
_DB_FD, _DB_PATH = tempfile.mkstemp(prefix="shellquest_smoke_", suffix=".db")
os.close(_DB_FD)
os.unlink(_DB_PATH)  # 让 SQLAlchemy 自己建文件，避免 mkstemp 留下的空文件干扰
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402

EXPECTED_UNITS = 21
EXPECTED_QUESTS = 63
EXPECTED_COMMANDS = 614

_failures: list[str] = []


def check(label: str, passed: bool, detail: str = "") -> None:
    """打印一行结果；失败时记账，最后统一以非 0 退出。"""
    mark = "PASS" if passed else "FAIL"
    print(f"[{mark}] {label}{(' ' + detail) if detail else ''}")
    if not passed:
        _failures.append(label)


def main() -> int:
    with TestClient(app) as client:
        # --- 课程 ---------------------------------------------------------- #
        units = client.get("/api/v1/units").json()
        quest_total = sum(unit["quest_count"] for unit in units)
        check(
            "课程落库",
            len(units) == EXPECTED_UNITS and quest_total == EXPECTED_QUESTS,
            f"单元 {len(units)} / 题 {quest_total}",
        )

        # --- 认证 ---------------------------------------------------------- #
        registered = client.post(
            "/api/v1/auth/register", json={"username": "smoke", "password": "password123"}
        )
        check("注册", registered.status_code == 201, f"HTTP {registered.status_code}")
        headers = {"X-Session-Token": registered.json()["token"]}

        # --- 判题与解锁 ---------------------------------------------------- #
        first_quest = units[0]["quests"][0]
        submitted = client.post(
            f"/api/v1/quests/{first_quest['id']}/submit",
            headers=headers,
            json={"answer": "whoami && pwd"},
        ).json()
        check(
            "判题",
            submitted["correct"] and submitted["xp_awarded"] > 0,
            f"correct={submitted['correct']} +{submitted['xp_awarded']}XP",
        )

        locked = client.post(
            f"/api/v1/quests/{units[1]['quests'][0]['id']}/submit",
            headers=headers,
            json={"answer": "x"},
        )
        check("单元锁", locked.status_code == 403, f"HTTP {locked.status_code}")

        progress = client.get("/api/v1/user/progress", headers=headers).json()
        check(
            "进度",
            progress["total_units"] == EXPECTED_UNITS,
            f"current_unit={progress['current_unit_id']}",
        )

        # --- 命令手册 ------------------------------------------------------ #
        facets = client.get("/api/v1/commands/facets").json()
        check(
            "命令手册载入",
            facets["total"] == EXPECTED_COMMANDS,
            f"{facets['total']} 条 / 分类 {len(facets['categories'])} / 标签 {len(facets['tags'])}",
        )

        detail = client.get("/api/v1/commands/ls").json()
        check(
            "命令详情",
            detail["name"] == "ls" and detail["license"] == "MIT",
            f"options={len(detail['options'])} examples={len(detail['examples'])} "
            f"related_quests={len(detail['related_quests'])}",
        )
        missing = client.get("/api/v1/commands/definitely-not-a-command")
        check("命令详情 404", missing.status_code == 404, f"HTTP {missing.status_code}")

        # --- 检索 ---------------------------------------------------------- #
        keyword = client.get("/api/v1/commands", params={"q": "端口", "page_size": 4}).json()
        top_names = [item["name"] for item in keyword["items"]]
        check("关键词检索", bool(top_names) and top_names[0] in {"lsof", "ss", "netstat"}, str(top_names))

        natural = client.get(
            "/api/v1/commands/natural", params={"q": "查看某个端口被谁占用"}
        ).json()
        hit = natural["hits"][0] if natural["hits"] else None
        unit_order = hit["related_quests"][0]["unit_order"] if hit and hit["related_quests"] else None
        # U11 是「端口冲突」，命中它才算自然语言检索真的对上了课程主题。
        check(
            "自然语言检索",
            unit_order == 11,
            f"首条 {hit['command']['name'] if hit else '-'} → U{unit_order}",
        )
        check("兜底建议", len(natural["suggestions"]) > 0, str(natural["suggestions"][:5]))

        # --- 打卡与技能树 -------------------------------------------------- #
        checkin = client.get("/api/v1/checkin/status", headers=headers).json()
        check("打卡状态", "today_checked_in" in checkin, f"today={checkin['today_checked_in']}")

        skills = client.get("/api/v1/user/skills", headers=headers).json()
        check(
            "技能树",
            skills["total_nodes"] == EXPECTED_UNITS,
            f"{skills['unlocked_nodes']}/{skills['total_nodes']}",
        )

    if _failures:
        print(f"\n失败 {len(_failures)} 项：{', '.join(_failures)}")
        return 1
    print("\n全部通过")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        # Windows 上引擎会持有文件句柄，且释放有延迟：先 dispose，再重试删除。
        engine.dispose()
        for _ in range(5):
            try:
                Path(_DB_PATH).unlink(missing_ok=True)
                break
            except PermissionError:
                time.sleep(0.2)
