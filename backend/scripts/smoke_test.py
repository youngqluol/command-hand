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
from datetime import date, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

# 必须在导入 app 之前设好 DATABASE_URL：`app.database` 在导入期就读取它建引擎。
_DB_FD, _DB_PATH = tempfile.mkstemp(prefix="shellquest_smoke_", suffix=".db")
os.close(_DB_FD)
os.unlink(_DB_PATH)  # 让 SQLAlchemy 自己建文件，避免 mkstemp 留下的空文件干扰
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.achievements import ACHIEVEMENTS  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import CheckIn, CourseUnit, Quest, User  # noqa: E402

EXPECTED_UNITS = 21
EXPECTED_QUESTS = 63
EXPECTED_COMMANDS = 614
EXPECTED_ACHIEVEMENTS = 22

_failures: list[str] = []


def check(label: str, passed: bool, detail: str = "") -> None:
    """打印一行结果；失败时记账，最后统一以非 0 退出。"""
    mark = "PASS" if passed else "FAIL"
    print(f"[{mark}] {label}{(' ' + detail) if detail else ''}")
    if not passed:
        _failures.append(label)


def correct_payload(quest: Quest) -> dict:
    """从库里读出这道题的正确答案，避免把 63 道题的答案写死在测试里。

    课程内容由 curriculum/ 定义，这里只是把「标准答案」按判题接口的入参形状回填。
    """
    if quest.kind in {"choice", "judge"}:
        return {"option_keys": [option.key for option in quest.options if option.is_correct]}
    return {"answer": quest.answer_display}


def unlocked_codes(client: TestClient, headers: dict[str, str]) -> set[str]:
    payload = client.get("/api/v1/achievements", headers=headers).json()
    return {
        item["code"]
        for group in payload["groups"]
        for item in group["items"]
        if item["unlocked"]
    }


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
        # 先故意答错一次：后面用它验证「答错过就不算无错通关」。
        missed = client.post(
            f"/api/v1/quests/{first_quest['id']}/submit",
            headers=headers,
            json={"answer": "zzz-definitely-not-a-real-answer"},
        ).json()
        check(
            "错答判负",
            not missed["correct"] and missed["xp_awarded"] == 0,
            f"correct={missed['correct']} +{missed['xp_awarded']}XP",
        )

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

        # --- 成就目录 ------------------------------------------------------ #
        catalog = client.get("/api/v1/achievements", headers=headers).json()
        check(
            "成就目录",
            catalog["total"] == EXPECTED_ACHIEVEMENTS and catalog["unlocked"] == 0,
            f"{catalog['unlocked']}/{catalog['total']} 已解锁",
        )
        check(
            "成就需登录",
            client.get("/api/v1/achievements").status_code == 401,
            "未带 token 应 401",
        )
        check(
            "成就带进度",
            any(item["progress"] for group in catalog["groups"] for item in group["items"]),
            "至少一条成就应带 progress",
        )

        # --- 完成第 1 个单元：通关类与无错类成就 ---------------------------- #
        with SessionLocal() as db:
            unit_one = db.scalar(select(CourseUnit).where(CourseUnit.order == 1))
            unit_one_payloads = [(q.id, correct_payload(q)) for q in unit_one.quests]
        last: dict = {}
        for quest_id, payload in unit_one_payloads:
            last = client.post(
                f"/api/v1/quests/{quest_id}/submit", headers=headers, json=payload
            ).json()

        check("单元完成", last.get("unit_completed") is True, f"unit_completed={last.get('unit_completed')}")
        codes = unlocked_codes(client, headers)
        check("解锁「破冰」", "unit_first" in codes, f"已解锁 {sorted(codes)}")
        # 第 1 题先答错过，所以这个单元不能算无错通关。
        check("答错过不算无错", "perfect_unit" not in codes, "perfect_unit 不应解锁")
        check(
            "作答响应回传新成就",
            "unit_first" in {item["code"] for item in last.get("achievements", [])},
            str([item["code"] for item in last.get("achievements", [])]),
        )

        # --- 打卡与连续天数成就 -------------------------------------------- #
        checkin = client.get("/api/v1/checkin/status", headers=headers).json()
        check("打卡状态", "today_checked_in" in checkin, f"today={checkin['today_checked_in']}")

        with SessionLocal() as db:
            # 造出「昨天打过卡、已连续 2 天」的状态，再打今天的卡 → 连续 3 天。
            # 删掉打卡记录时要把那部分经验一并退回，否则后面的排行榜断言会被测试数据带偏。
            user_row = db.scalar(select(User).where(User.username == "smoke"))
            user_row.streak_days = 2
            user_row.last_checkin_date = date.today() - timedelta(days=1)
            for row in list(db.scalars(select(CheckIn).where(CheckIn.user_id == user_row.id))):
                user_row.xp -= row.xp_awarded
                db.delete(row)
            db.commit()

        checked = client.post("/api/v1/checkin", headers=headers).json()
        check(
            "打卡连续天数",
            checked["status"]["streak_days"] == 3,
            f"streak={checked['status']['streak_days']}",
        )
        check(
            "解锁「三日不辍」",
            "streak_3" in {item["code"] for item in checked["achievements"]},
            str([item["code"] for item in checked["achievements"]]),
        )

        skills = client.get("/api/v1/user/skills", headers=headers).json()
        check(
            "技能树",
            skills["total_nodes"] == EXPECTED_UNITS,
            f"{skills['unlocked_nodes']}/{skills['total_nodes']}",
        )

        # --- 另一个用户全程首答正确 → 应解锁无错通关 ------------------------ #
        registered2 = client.post(
            "/api/v1/auth/register", json={"username": "smoke2", "password": "password123"}
        ).json()
        headers2 = {"X-Session-Token": registered2["token"]}
        with SessionLocal() as db:
            first_two = list(db.scalars(select(CourseUnit).where(CourseUnit.order <= 2)))
            first_two_payloads = [(q.id, correct_payload(q)) for unit in first_two for q in unit.quests]
        for quest_id, payload in first_two_payloads:
            client.post(f"/api/v1/quests/{quest_id}/submit", headers=headers2, json=payload)

        codes2 = unlocked_codes(client, headers2)
        check(
            "首答全对解锁无错通关",
            {"unit_first", "perfect_unit"} <= codes2,
            f"已解锁 {sorted(codes2)}",
        )

        # --- 排行榜 -------------------------------------------------------- #
        board = client.get("/api/v1/leaderboard").json()
        check(
            "排行榜公开可读",
            board["total_users"] == 2 and len(board["entries"]) == 2,
            f"{board['total_users']} 名用户 / {len(board['entries'])} 条",
        )
        xps = [entry["xp"] for entry in board["entries"]]
        check("排行榜按经验降序", xps == sorted(xps, reverse=True), str(xps))
        check(
            "排行榜名次连续",
            [entry["rank"] for entry in board["entries"]] == [1, 2],
            str([entry["rank"] for entry in board["entries"]]),
        )
        mine = client.get("/api/v1/leaderboard", headers=headers2).json()["me"]
        check(
            "排行榜返回自己的名次",
            mine is not None and mine["is_me"] and mine["rank"] == 1,
            f"me={mine}",
        )
        check(
            "排行榜不泄露私密字段",
            all(
                set(entry) == {"rank", "username", "level", "level_title", "xp", "streak_days", "is_me"}
                for entry in board["entries"]
            ),
            str(sorted(board["entries"][0])),
        )

        # --- 训练路径切换（REQUIREMENTS.md §3） ----------------------------- #
        # 用第三个用户，避免影响上面基于 XP / 用户数 的排行榜断言。
        registered3 = client.post(
            "/api/v1/auth/register", json={"username": "smoke3", "password": "password123"}
        ).json()
        headers3 = {"X-Session-Token": registered3["token"]}
        check(
            "默认训练路径",
            registered3["user"]["training_mode"] == "camp",
            registered3["user"]["training_mode"],
        )

        units3 = client.get("/api/v1/units", headers=headers3).json()
        check(
            "训练营模式串行解锁",
            units3[0]["status"] == "current" and units3[1]["status"] == "locked",
            f"U1={units3[0]['status']} U2={units3[1]['status']}",
        )
        blocked = client.post(
            f"/api/v1/quests/{units3[1]['quests'][0]['id']}/submit",
            headers=headers3,
            json={"answer": "x"},
        )
        check("训练营模式拦截越级", blocked.status_code == 403, f"HTTP {blocked.status_code}")

        switched = client.post("/api/v1/user/mode", headers=headers3, json={"mode": "free"}).json()
        check("切换为自由闯关", switched["training_mode"] == "free", switched["training_mode"])

        units3 = client.get("/api/v1/units", headers=headers3).json()
        check(
            "自由闯关不设关卡锁",
            units3[0]["status"] == "available" and units3[1]["status"] == "available",
            f"U1={units3[0]['status']} U2={units3[1]['status']}",
        )
        # 单元可进入还不够，题目的状态也必须是可作答（漏改 compute_quest_statuses 会在这里挂）。
        check(
            "自由闯关下题目可作答",
            units3[1]["quests"][0]["status"] == "current",
            units3[1]["quests"][0]["status"],
        )
        allowed = client.post(
            f"/api/v1/quests/{units3[1]['quests'][0]['id']}/submit",
            headers=headers3,
            json={"answer": "x"},
        )
        check("自由闯关可越级作答", allowed.status_code == 200, f"HTTP {allowed.status_code}")

        reverted = client.post("/api/v1/user/mode", headers=headers3, json={"mode": "camp"}).json()
        units3 = client.get("/api/v1/units", headers=headers3).json()
        check(
            "切回训练营恢复关卡锁",
            reverted["training_mode"] == "camp" and units3[1]["status"] == "locked",
            f"mode={reverted['training_mode']} U2={units3[1]['status']}",
        )
        check(
            "非法训练路径被拒",
            client.post("/api/v1/user/mode", headers=headers3, json={"mode": "nope"}).status_code == 422,
            "应 422",
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
