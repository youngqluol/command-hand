"""命令检索：关键词加权评分 + 自然语言（问题描述 → 命令）匹配。

设计依据 REQUIREMENTS.md §4.4.7：

- 关键词搜索的字段权重（高 → 低）：命令名 > 标签 > 一句话简介 > 选项 > 正文。
- 自然语言搜索首期采用轻量关键词 / 规则匹配，**词表不单独维护**，而是从课程关卡的
  声明（`title` + `scenario` + `prompt` + `commands`）派生，与「命令 ↔ 任务」关联同源。
- 中文不做分词，用 2-gram / 3-gram + 英文词元的方式建索引，配合 IDF 抑制「查看」「如何」
  这类高频噪声词。
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .models import Command, CourseUnit, Quest, QuestCommand

_ASCII_WORD = re.compile(r"[a-z0-9][a-z0-9._+-]*")
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
_CJK_ONLY = re.compile(r"^[\u4e00-\u9fff]+$")
_MARKDOWN_NOISE = re.compile(r"[`*_>#|]")

# n-gram 越长信息量越大，权重越高。
NGRAM_WEIGHTS = {2: 1.0, 3: 2.0}
LONG_NGRAM_WEIGHT = 2.5
WORD_WEIGHT = 1.5


def term_weight(term: str) -> float:
    if _CJK_ONLY.match(term):
        return NGRAM_WEIGHTS.get(len(term), LONG_NGRAM_WEIGHT)
    return WORD_WEIGHT


def select_matched_terms(query_terms: set[str], document_terms: Counter) -> list[str]:
    """只保留「最长匹配」的词元。

    中文按 n-gram 索引时，一个词会同时产生 2-gram 与 3-gram（「服务器」→ 服务 / 务器 /
    服务器）。若三个都计分，等于把同一个词重复算了三遍，会把仅命中一个常见词的长文档
    顶到命中两个关键词的短文档前面。因此：命中更长的 n-gram 后，其子串不再计分。
    """
    accepted: list[str] = []
    for term in sorted(query_terms, key=len, reverse=True):
        if term not in document_terms:
            continue
        if any(term != longer and term in longer for longer in accepted):
            continue
        accepted.append(term)
    return accepted


STOPWORDS = {
    "的",
    "了",
    "是",
    "在",
    "和",
    "与",
    "或",
    "把",
    "被",
    "给",
    "让",
    "对",
    "从",
    "到",
    "个",
    "这",
    "那",
    "有",
    "没",
    "不",
    "要",
    "会",
    "能",
    "可以",
    "如何",
    "怎么",
    "怎样",
    "什么",
    "哪些",
    "哪个",
    "为什么",
    "查看",
    "查询",
    "显示",
    "使用",
    "一个",
    "一下",
    "命令",
    "方式",
    "方法",
    "the",
    "a",
    "an",
    "of",
    "to",
    "for",
    "and",
    "or",
    "in",
    "on",
    "is",
    "how",
    "what",
    "which",
    "list",
    "show",
}

# 查询词元权重：命令名精确命中权重最高，正文最低。
FIELD_WEIGHTS = {
    "name_exact": 1000.0,
    "name_prefix": 600.0,
    "name_contains": 400.0,
    "tag_exact": 300.0,
    "summary": 200.0,
    "option": 120.0,
    "body": 60.0,
}

# 课程关卡声明过的命令（`quest_commands`）在并列时优先。
# 依据 4.4.7「命令 ↔ 任务关联与描述映射同源」：这些就是课程真正在教的命令，
# 搜索「端口」时应当把 `ss` / `netstat` / `lsof` 排在 `iftop` / `iperf` 之前。
COURSE_COMMAND_BOOST = 150.0

# 兜底建议的泛词截断阈值：命中超过这个比例的语料就算「不具区分度」。
# 「怎么压缩一个目录」里「目录」命中 182/614，且对 `ls` 触发 tag_exact + 课程加成，
# 累加后会盖过真正相关的 `tar` / `gzip`。IDF 只能削弱泛词、削不平，故直接丢弃。
SUGGEST_MAX_DF_RATIO = 0.25

# 兜底建议里每个词元只取最强的这么多条候选。
SUGGEST_TERM_TOPK = 6


def tokenize(text: str) -> list[str]:
    """中英混合的轻量词元化：英文按词、中文按 2-gram / 3-gram。"""
    lowered = _MARKDOWN_NOISE.sub(" ", text.lower())
    tokens: list[str] = list(_ASCII_WORD.findall(lowered))
    for run in _CJK_RUN.findall(lowered):
        length = len(run)
        if length <= 4:
            tokens.append(run)
        for size in (2, 3):
            for start in range(length - size + 1):
                tokens.append(run[start : start + size])
    return [token for token in tokens if token not in STOPWORDS]


# --------------------------------------------------------------------------- #
# 关键词搜索
# --------------------------------------------------------------------------- #


@dataclass
class KeywordHit:
    command: Command
    score: float
    matched_field: str
    snippet: str


def _snippet(haystack: str, needle: str, width: int = 70) -> str:
    index = haystack.lower().find(needle)
    if index < 0:
        return ""
    start = max(0, index - width // 2)
    end = min(len(haystack), index + len(needle) + width // 2)
    text = re.sub(r"\s+", " ", haystack[start:end]).strip()
    return f"{'…' if start > 0 else ''}{text}{'…' if end < len(haystack) else ''}"


def score_command(row: Command, tags: list[str], needle: str) -> tuple[float, str, str]:
    """按字段权重打分，返回 (得分, 命中的最高权重字段, 命中片段)。

    各字段**累加**而非取首个命中：一个命令若在名称、标签、简介、正文里都提到「端口」，
    它就该排在只在正文里提过一次的命令前面。只在首个命中字段上打分会让
    `ss` 和 `ifstat` 在搜索「端口」时并列，退化成按字母序排列。
    """
    name = row.name.lower()
    lowered_tags = {tag.lower() for tag in tags}

    score = 0.0
    best_field = ""
    best_weight = 0.0
    snippet = ""

    def add(weight: float, field_name: str, text: str) -> None:
        nonlocal score, best_field, best_weight, snippet
        score += weight
        if weight > best_weight:
            best_weight = weight
            best_field = field_name
            snippet = text

    if name == needle:
        add(FIELD_WEIGHTS["name_exact"], "name", row.name)
    elif name.startswith(needle):
        add(FIELD_WEIGHTS["name_prefix"], "name", row.name)
    elif needle in name:
        add(FIELD_WEIGHTS["name_contains"], "name", row.name)

    if needle in lowered_tags:
        add(FIELD_WEIGHTS["tag_exact"], "tag", needle)

    if needle in (row.summary or "").lower():
        add(FIELD_WEIGHTS["summary"], "summary", _snippet(row.summary, needle))

    for option in row.options or []:
        haystack = f"{option.get('flag', '')} {option.get('desc', '')}".lower()
        if needle in haystack:
            add(
                FIELD_WEIGHTS["option"],
                "option",
                f"{option.get('flag', '')} {option.get('desc', '')}".strip(),
            )
            break

    if needle in (row.body_markdown or "").lower():
        add(FIELD_WEIGHTS["body"], "body", _snippet(row.body_markdown, needle))

    return score, best_field, snippet


def suggest_commands(db: Session, query: str, limit: int = 8) -> list[Command]:
    """自然语言问法的关键词兜底建议。

    整句问法直接拿去做 `LIKE` 必然命中不了（「查看某个端口被谁占用」不是任何命令的子串），
    因此拆成词元逐个检索再合并。取中文 2-gram 与英文词：中文 3-gram 作为检索词过于具体
    （「个端口」「端口被」基本命中不到），2-gram 才是合适的粒度。

    合并时按**跨词元累计得分**排序，而不是「哪个词先命中就用哪个」——否则「查看」「占用」
    这类泛词的偶然命中会把真正相关的 `lsof` 挤到后面。累计时乘词元的 IDF 削弱泛词，
    命中面超过 `SUGGEST_MAX_DF_RATIO` 的词直接丢弃（IDF 只能削弱、削不平）。
    """
    terms = [term for term in tokenize(query) if _ASCII_WORD.match(term) or len(term) == 2]
    if not terms:
        return []

    corpus = db.scalar(select(func.count()).select_from(Command)) or 0
    if not corpus:
        return []

    totals: dict[str, float] = {}
    best: dict[str, KeywordHit] = {}
    for term in terms:
        # 每个词元只取最强的几条。放宽到 limit*2 会让 `rsync` 这种「选项里提到压缩」的
        # 弱命中被课程加成抬进候选，而用户问「怎么压缩目录」想要的显然是 `gzip` / `tar`。
        hits, total = keyword_search(db, term, limit=SUGGEST_TERM_TOPK)
        if not hits or total > corpus * SUGGEST_MAX_DF_RATIO:
            continue
        idf = math.log(1.0 + corpus / (1.0 + total))
        for hit in hits:
            name = hit.command.name
            totals[name] = totals.get(name, 0.0) + hit.score * idf
            if name not in best or hit.score > best[name].score:
                best[name] = hit

    ranked = sorted(totals, key=lambda name: (-totals[name], name))
    return [best[name].command for name in ranked[:limit]]


def course_command_names(db: Session) -> set[str]:
    """课程关卡声明过的全部命令名（见 4.4.8，数据源是 quest_commands）。"""
    return set(db.scalars(select(QuestCommand.command_name).distinct()))


def keyword_search(
    db: Session,
    query: str,
    limit: int = 30,
    offset: int = 0,
    conditions: list | None = None,
) -> tuple[list[KeywordHit], int]:
    """关键词检索。命令名精确 / 前缀命中优先，其余按字段权重累加排序。

    ``conditions`` 是额外的 SQLAlchemy 过滤条件（分类 / 标签 / 首字母），
    会同时作用于粗筛与退化后的全量扫描，保证分面筛选与搜索可叠加。
    """
    needle = query.strip().lower()
    if not needle:
        return [], 0
    extra = conditions or []

    # 先用 search_text 做粗筛，避免把 600 篇正文全部读进内存再打分。
    rows = list(
        db.scalars(
            select(Command)
            .where(Command.search_text.like(f"%{needle}%"), *extra)
            .options(selectinload(Command.tags))
        )
    )
    if not rows:
        # 粗筛落空时退化为一次全量打分（例如查询串里含被 Markdown 语法拆开的字符）。
        rows = list(db.scalars(select(Command).where(*extra).options(selectinload(Command.tags))))

    course_commands = course_command_names(db)
    scored: list[KeywordHit] = []
    for row in rows:
        tags = [tag.tag for tag in row.tags]
        score, field_name, snippet = score_command(row, tags, needle)
        if score <= 0:
            continue
        if row.name in course_commands:
            score += COURSE_COMMAND_BOOST
        scored.append(KeywordHit(command=row, score=score, matched_field=field_name, snippet=snippet))

    scored.sort(key=lambda hit: (-hit.score, hit.command.name))
    return scored[offset : offset + limit], len(scored)


# --------------------------------------------------------------------------- #
# 自然语言搜索
# --------------------------------------------------------------------------- #


@dataclass
class QuestPhrasing:
    """一个课程关卡派生出的「问题描述 → 命令」条目。"""

    unit_id: int
    unit_order: int
    zone: str
    unit_title: str
    quest_id: int
    quest_order: int
    quest_title: str
    quest_kind: str
    scenario: str
    commands: list[str]
    terms: Counter = field(default_factory=Counter)


@dataclass
class NaturalHit:
    phrasing: QuestPhrasing
    score: float
    matched_terms: list[str]


class PhrasingIndex:
    """从课程关卡声明构建的倒排索引。

    数据源是 `curriculum/` 里的 `title` / `scenario` / `prompt` / `commands`
    （以及所属单元的标题与目标），因此新增课程单元会自动获得自然语言检索能力，
    无需另维护词表。

    打分用 BM25：只用 IDF 加权求和会让长文本天然占优，只用长度归一又会让短文本占优，
    BM25 的饱和度与长度归一恰好解决这两头的问题。
    """

    BM25_K1 = 1.2
    BM25_B = 0.75
    COMMAND_HIT_BOOST = 2.0

    def __init__(self, phrasings: list[QuestPhrasing]) -> None:
        self.phrasings = phrasings
        self.document_frequency: Counter = Counter()
        self.lengths: list[int] = []
        for phrasing in phrasings:
            for term in set(phrasing.terms):
                self.document_frequency[term] += 1
            self.lengths.append(sum(phrasing.terms.values()) or 1)
        self.total_documents = max(1, len(phrasings))
        self.average_length = sum(self.lengths) / len(self.lengths) if self.lengths else 1.0

    def idf(self, term: str) -> float:
        df = self.document_frequency.get(term, 0)
        return math.log(1 + (self.total_documents - df + 0.5) / (df + 0.5))

    def search(self, query: str, limit: int = 6, min_score: float = 1.0) -> list[NaturalHit]:
        query_terms = set(tokenize(query))
        if not query_terms:
            return []

        hits: list[NaturalHit] = []
        for phrasing, length in zip(self.phrasings, self.lengths):
            normalization = self.BM25_K1 * (
                1 - self.BM25_B + self.BM25_B * length / self.average_length
            )
            matched_terms = select_matched_terms(query_terms, phrasing.terms)

            score = 0.0
            for term in matched_terms:
                frequency = phrasing.terms[term]
                score += (
                    term_weight(term)
                    * self.idf(term)
                    * (frequency * (self.BM25_K1 + 1))
                    / (frequency + normalization)
                )

            command_hits = query_terms & set(phrasing.commands)
            for token in command_hits:
                score += self.COMMAND_HIT_BOOST * self.idf(token)

            if score > 0:
                hits.append(
                    NaturalHit(
                        phrasing=phrasing,
                        score=round(score, 4),
                        matched_terms=sorted(set(matched_terms) | command_hits),
                    )
                )

        hits = [hit for hit in hits if hit.score >= min_score]
        hits.sort(key=lambda hit: (-hit.score, hit.phrasing.quest_order))
        return hits[:limit]


def build_phrasing_index(db: Session) -> PhrasingIndex:
    units = list(
        db.scalars(
            select(CourseUnit)
            .order_by(CourseUnit.order)
            .options(selectinload(CourseUnit.quests).selectinload(Quest.commands))
        )
    )
    phrasings: list[QuestPhrasing] = []
    for unit in units:
        # 单元标题与目标代表整课的主题词。用户问「怎么传到远程服务器」时，信号在
        # 单元名「远程发布」上，而不在任何一道题的题干里 —— 不带上就会漏召回。
        # 区域名（如「文件工坊」）**不**参与索引：它带来的是「文件」这类高频泛词，
        # 会把同区域内所有关卡一起抬高，反而淹没真正相关的单元。
        unit_terms: Counter = Counter()
        for weight, text in ((3, unit.title), (1, unit.goal)):
            for token in tokenize(text or ""):
                unit_terms[token] += weight

        for quest in unit.quests:
            # 权重：标题与题干最能代表「用户会怎么问」，场景描述次之。
            terms: Counter = Counter(unit_terms)
            for weight, text in ((3, quest.title), (2, quest.prompt), (2, quest.scenario)):
                for token in tokenize(text or ""):
                    terms[token] += weight
            phrasings.append(
                QuestPhrasing(
                    unit_id=unit.id,
                    unit_order=unit.order,
                    zone=unit.zone,
                    unit_title=unit.title,
                    quest_id=quest.id,
                    quest_order=quest.order,
                    quest_title=quest.title,
                    quest_kind=quest.kind,
                    scenario=quest.scenario,
                    commands=[c.command_name for c in quest.commands],
                    terms=terms,
                )
            )
    return PhrasingIndex(phrasings)
