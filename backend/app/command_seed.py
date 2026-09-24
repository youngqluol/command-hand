"""命令手册的落库与种子快照加载。

`scripts/import_commands.py` 负责「取上游 + 解析」，本模块负责「写库」，
两边共用同一份写入逻辑，保证在线导入与离线种子加载的结果完全一致。

为什么需要种子快照：上游内容只在维护期离线导入，而 Docker 构建期没有网络、
运行期数据库又是空的。把导入结果导出成 `data/commands_seed.json.gz` 随仓库分发，
启动时发现 `commands` 表为空就自动灌入，运行期便不依赖任何外部站点（见 4.4.2）。
"""

from __future__ import annotations

import gzip
import json
import logging
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Command, CommandTag

logger = logging.getLogger("shellquest")

# entry 中属于 commands 表列字段的部分；tags 走关联表，不在此列。
COLUMN_FIELDS = (
    "name",
    "summary",
    "body_markdown",
    "category",
    "syntax",
    "sections",
    "options",
    "examples",
    "search_text",
    "source_url",
    "license",
    "source_version",
    "content_hash",
)

SEED_META_FIELDS = ("version", "repo", "license")


def sync_tags(session: Session, row: Command, desired: list[str]) -> None:
    """只增删差异标签，避免 (command_id, tag) 唯一约束冲突。"""
    current = {tag.tag: tag for tag in row.tags}
    for tag, obj in current.items():
        if tag not in desired:
            session.delete(obj)
    for tag in desired:
        if tag not in current:
            session.add(CommandTag(command_id=row.id, tag=tag))


def import_entries(session: Session, entries: list[dict], dry_run: bool = False) -> dict[str, int]:
    """幂等写入。以 `content_hash` 判断是否变化，未变的条目完全不写库。"""
    existing = {row.name: row for row in session.scalars(select(Command))}
    created = updated = unchanged = 0
    seen: set[str] = set()

    for entry in entries:
        name = entry["name"]
        seen.add(name)
        row = existing.get(name)

        if row is None:
            created += 1
            if dry_run:
                continue
            row = Command(**{field: entry[field] for field in COLUMN_FIELDS})
            session.add(row)
            session.flush()
            sync_tags(session, row, entry["tags"])
            continue

        if row.content_hash == entry["content_hash"]:
            unchanged += 1
            continue

        updated += 1
        if dry_run:
            continue
        for field in COLUMN_FIELDS:
            setattr(row, field, entry[field])
        session.flush()
        sync_tags(session, row, entry["tags"])

    removed = [name for name in existing if name not in seen]
    if removed and not dry_run:
        for name in removed:
            session.delete(existing[name])

    if not dry_run:
        session.commit()

    return {"created": created, "updated": updated, "unchanged": unchanged, "removed": len(removed)}


def export_seed(entries: list[dict], path: Path, meta: dict | None = None) -> int:
    """把导入结果导出为可提交的 gzip 快照。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**(meta or {}), "count": len(entries), "commands": entries}
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    return path.stat().st_size


def command_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Command)) or 0


def ensure_commands_seeded(session: Session, seed_path: Path) -> dict[str, int] | None:
    """`commands` 表为空且存在种子快照时灌入；否则什么都不做。"""
    if command_count(session) > 0:
        return None
    if not seed_path.exists():
        logger.warning(
            "commands 表为空且未找到种子快照 %s，命令查询模块将没有数据。"
            "请执行 backend/scripts/import_commands.py 导入。",
            seed_path,
        )
        return None

    with gzip.open(seed_path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    entries = payload.get("commands", [])
    if not entries:
        logger.warning("种子快照 %s 内容为空", seed_path)
        return None

    stats = import_entries(session, entries)
    logger.info(
        "已从种子快照载入命令手册：%d 条（上游版本 %s）", stats["created"], payload.get("version", "未知")
    )
    return stats
