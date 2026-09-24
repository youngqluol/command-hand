#!/usr/bin/env python
"""从 jaywcjlove/linux-command（MIT）导入命令手册数据。

设计依据 REQUIREMENTS.md §4.4，字段语义见 AGENTS.md §4.8。

用法（工作目录 backend/）：

    .venv/Scripts/python scripts/import_commands.py            # 首次下载并导入
    .venv/Scripts/python scripts/import_commands.py --offline  # 只用本地缓存
    .venv/Scripts/python scripts/import_commands.py --dry-run  # 只统计，不写库
    .venv/Scripts/python scripts/import_commands.py --refresh  # 强制重新下载上游

脚本是**幂等**的：内容未变的命令不会写库，输出「新增 / 更新 / 未变 / 删除」四项计数。
上游没有提供任何分类数据（dist/data.json 只有 n/p/d 三个字段），因此 category 与 tags
全部由 scripts/command_taxonomy.json 自建映射表决定。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.command_seed import export_seed, import_entries  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Command  # noqa: E402

UPSTREAM_REPO = "jaywcjlove/linux-command"
UPSTREAM_LICENSE = "MIT"
DEFAULT_VERSION = "1.22.0"
DEFAULT_REGISTRY = "https://registry.npmjs.org"
DEFAULT_TAXONOMY = Path(__file__).resolve().parent / "command_taxonomy.json"
DEFAULT_CACHE = BACKEND_DIR / ".cache" / "linux-command"
DEFAULT_SEED = BACKEND_DIR / "data" / "commands_seed.json.gz"

# --------------------------------------------------------------------------- #
# 文本清洗
# --------------------------------------------------------------------------- #

# 上游有零宽字符污染围栏的个例（如 netstat.md 的 ``​```shell``），必须先剔除。
_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"), None)

_FENCE_RE = re.compile(r"^\s{0,3}(```|~~~)")
_HEADING_RE = re.compile(r"^(#{2,6})\s+(.+?)\s*$")
_SETEXT_H1_RE = re.compile(r"^=+\s*$")


def strip_zero_width(text: str) -> str:
    return text.translate(_ZERO_WIDTH)


def fence_mask(lines: list[str]) -> tuple[list[bool], bool]:
    """标记每行是否位于围栏代码块内，并返回围栏是否配平。

    采用「成对开关」语义：任意围栏行都切换状态。上游 Markdown 里存在
    ``​```shell`` 这类被零宽字符污染的闭合行，严格闭合语义会把后面的内容整段吞掉。
    """
    inside: list[bool] = []
    open_fence = False
    for line in lines:
        if _FENCE_RE.match(line):
            open_fence = not open_fence
            inside.append(True)
            continue
        inside.append(open_fence)
    return inside, not open_fence


def plain_text(markdown: str) -> str:
    """去掉 Markdown 语法，用于生成 search_text。"""
    text = strip_zero_width(markdown)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[`*_>#|]", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def clean_inline(line: str) -> str:
    """清理示例段落里的行内标记，保留可读文字。"""
    text = strip_zero_width(line).strip()
    text = re.sub(r"^[-*#>\s]+", "", text)
    text = text.replace("**", "").replace("`", "")
    return text.strip()


# --------------------------------------------------------------------------- #
# Markdown 解析
# --------------------------------------------------------------------------- #

SECTION_ALIASES: dict[str, set[str]] = {
    "description": {"补充说明", "说明", "描述", "主要用途", "简介", "功能"},
    "syntax": {"语法", "概要", "用法", "用法格式", "命令格式", "格式", "语法格式"},
    "options": {"选项", "常用选项", "选项参数", "相关选项", "参数选项", "可选参数"},
    "parameters": {"参数", "参数说明", "必需参数"},
    "examples": {"实例", "例子", "示例", "更多实例", "用例", "范例", "应用实例", "使用实例", "应用示例"},
    "return_value": {"返回值", "返回码", "退出码", "退出状态"},
    "notes": {"注意", "注意事项", "警告", "错误用法", "限制"},
    "install": {"安装", "下载安装", "升级", "卸载", "部署"},
    "extended": {
        "扩展知识",
        "知识扩展",
        "知识点",
        "参考资料",
        "参考链接",
        "其他参考链接",
        "相关参考",
        "官网",
        "q&a",
        "相关命令",
        "参见",
        "更多",
        "扩展阅读",
        "内建命令",
        "外部命令",
        "特点",
        "问题解决",
        "配置",
        "目录",
        "help 信息翻译",
    },
}

_ALIAS_TO_ROLE = {
    alias.lower(): role for role, aliases in SECTION_ALIASES.items() for alias in aliases
}


def role_for(title: str) -> str:
    """把上游千奇百怪的章节标题映射到规范角色，未知标题归为 extra（原文保留）。"""
    normalized = strip_zero_width(title).strip().rstrip("：:").lower()
    return _ALIAS_TO_ROLE.get(normalized, "extra")


def split_document(text: str) -> tuple[str, list[dict], bool]:
    """拆出摘要与章节列表。

    返回 ``(summary, sections, balanced)``；``balanced`` 为 False 时调用方应放弃
    结构化结果，直接渲染 body_markdown。
    """
    lines = strip_zero_width(text).split("\n")

    body_start = 0
    if lines and lines[0].startswith("# "):
        body_start = 1
    elif len(lines) > 1 and _SETEXT_H1_RE.match(lines[1]) and lines[0].strip():
        body_start = 2

    inside, balanced = fence_mask(lines)

    heads: list[tuple[int, int, str]] = []
    for index in range(body_start, len(lines)):
        if inside[index]:
            continue
        match = _HEADING_RE.match(lines[index])
        if match:
            heads.append((index, len(match.group(1)), match.group(2).strip()))

    first_head = heads[0][0] if heads else len(lines)
    summary_block = "\n".join(lines[body_start:first_head]).strip()

    sections: list[dict] = []
    for position, (index, level, title) in enumerate(heads):
        end = heads[position + 1][0] if position + 1 < len(heads) else len(lines)
        content = "\n".join(lines[index + 1 : end]).strip()
        sections.append(
            {"title": title, "role": role_for(title), "level": level, "content": content}
        )

    return summary_block, sections, balanced


def first_paragraph(block: str) -> str:
    for line in block.split("\n"):
        cleaned = clean_inline(line)
        if cleaned:
            return cleaned
    return ""


_GROUP_RE = re.compile(r"^\s*[^\s:：#]{1,20}[:：]\s*$")
_FLAG_TOKEN_RE = re.compile(r"^[-+][\w-]*(?:=\S+)?$")


def split_option_line(line: str) -> tuple[str, str] | None:
    """把一行选项拆成 (flag, 说明)，无法识别时返回 None。

    上游至少存在四种写法，按可靠性从高到低依次尝试：

    1. ``-a     # 列出所有文件``        注释分隔
    2. ``-a：显示所有终端机下执行的程序`` 全角/半角冒号分隔
    3. ``-h, --help      帮助信息``      两个以上空格分隔
    4. ``-f 将操作或显示限制为函数名``     单个空格分隔，说明里不含分隔符
    """
    text = line.strip()
    if not text.startswith(("-", "+")):
        return None

    # 1) 注释风格
    match = re.match(r"^(\S.*?)\s+#\s*(.*)$", text)
    if match:
        return match.group(1).strip(), match.group(2).strip()

    # 2) 冒号风格
    match = re.match(r"^(\S.*?)[：:]\s*(\S.*)$", text)
    if match and len(match.group(1)) <= 40:
        return match.group(1).strip(), match.group(2).strip()

    # 3) 多空格风格
    match = re.match(r"^(\S.*?)\s{2,}(\S.*)$", text)
    if match:
        return match.group(1).strip(), match.group(2).strip()

    # 4) 逐 token 收集开头的选项，其余作为说明；说明可为空
    tokens = text.split()
    flags: list[str] = []
    index = 0
    while index < len(tokens) and _FLAG_TOKEN_RE.match(tokens[index].rstrip(",")):
        flags.append(tokens[index].rstrip(","))
        index += 1
    if flags:
        return " ".join(flags), " ".join(tokens[index:]).strip()

    return None


def parse_options(sections: list[dict]) -> list[dict] | None:
    """从「选项」类章节尽力提取结构化选项，少于 2 条视为提取失败。"""
    blocks: list[list[str]] = []
    for section in sections:
        if section["role"] != "options":
            continue
        lines = section["content"].split("\n")
        inside, _ = fence_mask(lines)
        fenced = [line for index, line in enumerate(lines) if inside[index]]
        blocks.append(fenced if fenced else lines)

    options: list[dict] = []
    seen: set[str] = set()
    group: str | None = None
    for block in blocks:
        for raw in block:
            if _FENCE_RE.match(raw) or not raw.strip():
                continue
            if _GROUP_RE.match(raw):
                group = raw.strip().rstrip("：:")
                continue
            parsed = split_option_line(raw)
            if parsed:
                flag, description = parsed
                if flag in seen:
                    continue
                seen.add(flag)
                item = {"flag": flag, "desc": description}
                if group:
                    item["group"] = group
                options.append(item)
                continue
            # 续行：接到上一条选项的说明后面
            if options:
                tail = clean_inline(raw)
                if tail:
                    options[-1]["desc"] = f"{options[-1]['desc']} {tail}".strip()

    return options if len(options) >= 2 else None


def parse_examples(sections: list[dict]) -> list[dict] | None:
    """从「实例」类章节尽力提取 (说明, 代码) 组，空结果视为提取失败。"""
    examples: list[dict] = []
    for section in sections:
        if section["role"] != "examples":
            continue
        lines = section["content"].split("\n")
        inside, _ = fence_mask(lines)
        pending: list[str] = []
        index = 0
        while index < len(lines):
            if inside[index]:
                end = index
                while end < len(lines) and inside[end]:
                    end += 1
                block = [line for line in lines[index:end] if not _FENCE_RE.match(line)]
                code = "\n".join(block).strip()
                description = " ".join(pending).strip()
                pending = []
                if code:
                    examples.append({"description": description, "code": code})
                index = end
                continue
            if lines[index].strip():
                pending.append(clean_inline(lines[index]))
            index += 1

    return examples or None


def extract_syntax(sections: list[dict]) -> str | None:
    for section in sections:
        if section["role"] != "syntax":
            continue
        lines = section["content"].split("\n")
        inside, _ = fence_mask(lines)
        fenced = [line for i, line in enumerate(lines) if inside[i] and not _FENCE_RE.match(line)]
        text = "\n".join(fenced).strip() if fenced else section["content"].strip()
        if text:
            return text
    return None


# --------------------------------------------------------------------------- #
# 分类映射
# --------------------------------------------------------------------------- #


class Taxonomy:
    def __init__(self, payload: dict) -> None:
        self.default_category = payload.get("default_category", "其他")
        self.categories: list[str] = payload.get("categories", [self.default_category])
        self.commands: dict[str, dict] = payload.get("commands", {})
        self.rules: list[tuple[re.Pattern[str], str, list[str]]] = [
            (re.compile(rule["pattern"]), rule["category"], list(rule.get("tags", [])))
            for rule in payload.get("rules", [])
        ]

    def resolve(self, name: str) -> tuple[str, list[str]]:
        explicit = self.commands.get(name)
        if explicit:
            return explicit["category"], list(explicit.get("tags", []))
        for pattern, category, tags in self.rules:
            if pattern.search(name):
                return category, list(tags)
        return self.default_category, []


def load_taxonomy(path: Path) -> Taxonomy:
    payload = json.loads(path.read_text(encoding="utf-8"))
    taxonomy = Taxonomy(payload)
    known = set(taxonomy.categories)
    for rule in payload.get("rules", []):
        if rule["category"] not in known:
            raise SystemExit(f"映射表错误：规则 {rule['pattern']!r} 使用了未知分类 {rule['category']!r}")
    for name, entry in taxonomy.commands.items():
        if entry["category"] not in known:
            raise SystemExit(f"映射表错误：命令 {name!r} 使用了未知分类 {entry['category']!r}")
    return taxonomy


# --------------------------------------------------------------------------- #
# 上游获取
# --------------------------------------------------------------------------- #


def download_and_extract(cache_dir: Path, version: str, registry: str, refresh: bool) -> Path:
    root = cache_dir / f"linux-command-{version}"
    ready = root / ".ready"
    if ready.exists() and not refresh:
        return root

    url = f"{registry.rstrip('/')}/linux-command/-/linux-command-{version}.tgz"
    print(f"[上游] 下载 {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "shellquest-importer/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"下载失败：{exc}\n可改用 --offline 复用本地缓存，或 --source-dir 指定已解包的目录。")

    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    with tempfile.NamedTemporaryFile(suffix=".tgz", delete=False) as handle:
        handle.write(payload)
        archive_path = Path(handle.name)

    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive.getmembers():
                if member.name.startswith("package/") and member.isfile():
                    archive.extract(member, root, filter="data")
    finally:
        archive_path.unlink(missing_ok=True)

    extracted = root / "package"
    if not (extracted / "command").is_dir():
        raise SystemExit(f"上游包结构异常，未找到 command/ 目录：{extracted}")

    ready.write_text(version, encoding="utf-8")
    print(f"[上游] 已解包到 {extracted}")
    return root


def load_index(source_root: Path) -> dict[str, str]:
    index_path = source_root / "package" / "dist" / "data.json"
    if not index_path.exists():
        index_path = source_root / "dist" / "data.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    return {name: entry.get("d", "").strip() for name, entry in payload.items()}


# --------------------------------------------------------------------------- #
# 条目构建
# --------------------------------------------------------------------------- #


def build_entry(name: str, markdown: str, index_summary: str, taxonomy: Taxonomy, version: str) -> dict:
    summary_block, sections, balanced = split_document(markdown)
    if not balanced:
        # 围栏不配平（上游个例）：放弃结构化分区，让前端直接渲染原文，避免吞内容。
        sections = []

    category, tags = taxonomy.resolve(name)
    options = parse_options(sections)
    examples = parse_examples(sections)
    syntax = extract_syntax(sections)

    summary = first_paragraph(summary_block) or index_summary or ""
    if not summary:
        summary = f"{name} 命令"

    plain = plain_text(markdown)
    search_parts = [name, summary, category, *tags]
    if options:
        search_parts.extend(option["flag"] for option in options)
        search_parts.extend(option["desc"] for option in options)
    search_parts.append(plain)
    search_text = " ".join(part for part in search_parts if part).lower()

    canonical = json.dumps(
        {
            "name": name,
            "summary": summary,
            "body": markdown,
            "category": category,
            "tags": sorted(tags),
            "syntax": syntax,
            "sections": sections,
            "options": options,
            "examples": examples,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    return {
        "name": name,
        "summary": summary[:500],
        "body_markdown": markdown,
        "category": category,
        "tags": sorted(set(tags)),
        "syntax": syntax,
        "sections": sections,
        "options": options,
        "examples": examples,
        "search_text": search_text,
        "source_url": f"https://github.com/{UPSTREAM_REPO}/blob/master/command/{name}.md",
        "license": UPSTREAM_LICENSE,
        "source_version": version,
        "content_hash": content_hash,
    }


def collect_entries(source_root: Path, version: str, taxonomy: Taxonomy) -> list[dict]:
    command_dir = source_root / "package" / "command"
    index = load_index(source_root)
    entries: list[dict] = []
    for path in sorted(command_dir.glob("*.md")):
        name = path.stem
        markdown = path.read_text(encoding="utf-8", errors="replace")
        entries.append(build_entry(name, markdown, index.get(name, ""), taxonomy, version))
    return entries


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导入 linux-command 命令手册数据")
    parser.add_argument("--version", default=DEFAULT_VERSION, help=f"上游版本，默认 {DEFAULT_VERSION}")
    parser.add_argument("--registry", default=DEFAULT_REGISTRY, help="npm registry 地址")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE, help="上游包缓存目录")
    parser.add_argument("--source-dir", type=Path, default=None, help="已解包的上游目录（优先于下载）")
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY, help="分类映射表")
    parser.add_argument("--offline", action="store_true", help="只使用本地缓存，不联网")
    parser.add_argument("--refresh", action="store_true", help="强制重新下载上游")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不写库")
    parser.add_argument(
        "--export",
        nargs="?",
        const=DEFAULT_SEED,
        type=Path,
        default=None,
        help=f"导出种子快照（默认 {DEFAULT_SEED}），供无网络环境启动时自动载入",
    )
    parser.add_argument("--report", type=Path, default=None, help="额外输出分类分布报告到指定文件")
    return parser.parse_args(argv)


def resolve_source_dir(path: Path) -> Path:
    """把用户传入的目录规整为「包含 package/ 的目录」。

    同时接受以下三种形态：已解包的 ``package/``、解包根目录、以及仓库中的 ``command/`` 同级目录。
    """
    candidates = [path, path.parent]
    for candidate in candidates:
        if (candidate / "package" / "command").is_dir():
            return candidate
    if (path / "command").is_dir():
        # 直接指向 package/ 目录
        return path.parent
    raise SystemExit(f"--source-dir 下未找到 command/ 目录：{path}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    taxonomy = load_taxonomy(args.taxonomy)

    if args.source_dir:
        source_root = resolve_source_dir(args.source_dir)
    else:
        source_root = download_and_extract(args.cache_dir, args.version, args.registry, args.refresh)

    print("[解析] 读取上游 Markdown ...")
    entries = collect_entries(source_root, args.version, taxonomy)
    print(f"[解析] 共 {len(entries)} 条命令")

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        stats = import_entries(session, entries, dry_run=args.dry_run)

    action = "预演（未写库）" if args.dry_run else "导入完成"
    print(
        f"[{action}] 新增 {stats['created']} / 更新 {stats['updated']} / "
        f"未变 {stats['unchanged']} / 删除 {stats['removed']}"
    )

    distribution: dict[str, int] = {}
    tag_counter: dict[str, int] = {}
    no_options = no_examples = 0
    for entry in entries:
        distribution[entry["category"]] = distribution.get(entry["category"], 0) + 1
        for tag in entry["tags"]:
            tag_counter[tag] = tag_counter.get(tag, 0) + 1
        if not entry["options"]:
            no_options += 1
        if not entry["examples"]:
            no_examples += 1

    print("\n[分类分布]")
    for category in taxonomy.categories:
        print(f"  {category:<12} {distribution.get(category, 0):>4}")

    print("\n[标签分布 Top 20]")
    for tag, count in sorted(tag_counter.items(), key=lambda item: (-item[1], item[0]))[:20]:
        print(f"  {tag:<12} {count:>4}")

    print(f"\n[结构化提取] 选项提取失败 {no_options} 条 / 示例提取失败 {no_examples} 条")

    if args.export:
        size = export_seed(
            entries,
            args.export,
            meta={
                "version": args.version,
                "repo": UPSTREAM_REPO,
                "license": UPSTREAM_LICENSE,
            },
        )
        print(f"[快照] 已导出 {args.export}（{size / 1024:.0f} KB），启动时若 commands 表为空会自动载入")

    if args.report:
        args.report.write_text(
            json.dumps(
                {
                    "stats": stats,
                    "distribution": distribution,
                    "tags": tag_counter,
                    "no_options": no_options,
                    "no_examples": no_examples,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"[报告] 已写入 {args.report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
