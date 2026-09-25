"""命令手册验收核查：对应 REQUIREMENTS.md 4.4.11 的验收标准。

与 `smoke_test.py` 的分工：
- `smoke_test.py` 在**临时空库**上验证链路能不能跑通（课程落库 / 判题 / 检索）。
- 本脚本在**已导入的真实库**上验证数据质量与验收标准（内容无损 / 结构化覆盖率 / 精确命中置顶）。

    cd backend && python scripts/verify_commands.py

只读，不改任何数据。退出码非 0 表示有验收项未通过。
"""

from __future__ import annotations

import gzip
import json
import logging
import random
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

# 本次要跑 600+ 次请求，默认的 INFO 日志会把结果淹掉。只留 WARNING 以上。
logging.getLogger("shellquest").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

SEED_PATH = BACKEND_DIR / "data" / "commands_seed.json.gz"
SAMPLE_SIZE = 20
# 固定种子：抽样结果可复现，失败时能直接照着名单复查。
RANDOM_SEED = 20260925

_failures: list[str] = []


def check(label: str, passed: bool, detail: str = "") -> None:
    """打印一行结果；失败时记账，最后统一以非 0 退出。"""
    mark = "PASS" if passed else "FAIL"
    print(f"[{mark}] {label}{(' ' + detail) if detail else ''}")
    if not passed:
        _failures.append(label)


def main() -> int:
    if not SEED_PATH.exists():
        print(f"缺少离线种子快照：{SEED_PATH}（见 AGENTS.md §4.8）")
        return 2

    with gzip.open(SEED_PATH, "rt", encoding="utf-8") as fh:
        seed = json.load(fh)
    source = {item["name"]: item["body_markdown"] for item in seed["commands"]}
    print(f"种子快照 {len(source)} 条 · 上游 {seed['repo']} v{seed['version']} / {seed['license']}\n")

    with TestClient(app) as client:
        # --- 1. 内容无损：逐条比对 markdown -------------------------------- #
        mismatched: list[str] = []
        raw_fallback: list[str] = []
        structured = 0
        for name, markdown in source.items():
            detail = client.get(f"/api/v1/commands/{name}").json()
            if detail["body_markdown"] != markdown:
                mismatched.append(name)
            if detail["syntax"] or detail["options"] or detail["examples"] or detail["sections"]:
                structured += 1
            else:
                raw_fallback.append(name)

        check(
            "内容无损（逐条比对 markdown）",
            not mismatched,
            f"{len(source) - len(mismatched)}/{len(source)} 一致"
            + (f"，不一致 {mismatched[:5]}" if mismatched else ""),
        )

        listed = client.get("/api/v1/commands", params={"page_size": 1}).json()["total"]
        check("列表条数与快照一致", listed == len(source), f"接口 {listed} / 快照 {len(source)}")

        # 结构化提取是「尽力而为」，允许有回落；这里只记录规模，不判失败。
        print(
            f"       结构化提取：{structured} 条有结构化字段，"
            f"{len(raw_fallback)} 条回落原文 {raw_fallback[:5]}"
        )

        # --- 2. 精确命中置顶 + 详情非空 ------------------------------------ #
        random.seed(RANDOM_SEED)
        sample = random.sample(sorted(source), min(SAMPLE_SIZE, len(source)))

        not_first: list[str] = []
        too_short: list[str] = []
        for name in sample:
            hits = client.get("/api/v1/commands", params={"q": name, "page_size": 5}).json()["items"]
            if not hits or hits[0]["name"] != name:
                not_first.append(f"{name} → {[hit['name'] for hit in hits[:3]]}")
            detail = client.get(f"/api/v1/commands/{name}").json()
            if len(detail["body_markdown"] or "") < 20:
                too_short.append(name)

        check(
            f"抽 {len(sample)} 条命令，精确命中置顶",
            not not_first,
            f"{len(sample) - len(not_first)}/{len(sample)}" + (f"，未置顶 {not_first[:3]}" if not_first else ""),
        )
        check(
            f"抽 {len(sample)} 条命令，详情非空",
            not too_short,
            f"{len(sample) - len(too_short)}/{len(sample)}" + (f"，过短 {too_short[:3]}" if too_short else ""),
        )

        # --- 3. 分面与许可 ------------------------------------------------- #
        facets = client.get("/api/v1/commands/facets").json()
        check(
            "分面数据完整（分类 + 标签 + 首字母）",
            bool(facets.get("categories")) and bool(facets.get("tags")) and bool(facets.get("letters")),
            f"分类 {len(facets.get('categories', []))} / 标签 {len(facets.get('tags', []))} "
            f"/ 首字母 {len(facets.get('letters', []))}",
        )

        detail = client.get("/api/v1/commands/ls").json()
        check(
            "详情页带来源与许可",
            detail["license"] == seed["license"] and bool(detail["source_url"]),
            f"{detail['license']} · {detail['source_version']}",
        )

        # --- 4. 双向关联 --------------------------------------------------- #
        check(
            "命令 → 任务（related_quests 非空）",
            bool(detail["related_quests"]),
            f"ls 关联 {len(detail['related_quests'])} 个关卡",
        )

    print()
    if _failures:
        print(f"未通过 {len(_failures)} 项：{_failures}")
        return 1
    print("全部验收项通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
