#!/usr/bin/env python3
"""Validate the Markdown-authored DeepSeek Harness wiki and its rendered page."""

from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PAGE = ROOT / "wiki" / "DSH" / "index.md"
LEGACY_HTML_PAGE = ROOT / "wiki" / "DSH" / "index.html"
AUTHORING_GUIDE = ROOT / "wiki" / "DSH" / "_AUTHORING.md"
LAYOUT_PATH = ROOT / "_layouts" / "dsh_runtime_wiki.html"
INCLUDE_PATH = ROOT / "_includes" / "dsh" / "diagram.html"
STYLE_PATH = ROOT / "assets" / "css" / "dsh-runtime-wiki.css"
SCRIPT_PATH = ROOT / "assets" / "js" / "dsh-runtime-wiki.js"
DIAGRAM_DIR = ROOT / "assets" / "wiki" / "deepseek-harness" / "diagrams"
BASEURL = "/Ryanhu2001/"
REVISION = "47f943859bef60e4160492346772ded9b24f765a"

REQUIRED_PART_IDS = (
    "part-introduction",
    "part-composition",
    "part-core-designs",
    "part-presets",
    "part-comparison",
)

REQUIRED_PART_TITLES = (
    "Part 1｜Overview：AgentLoop 之外还要管理什么",
    "Part 2｜Everything Is a Plugin：DSH 如何组织这些能力",
    "Part 3｜Core Designs：会话、模型输入、工具和长期任务",
    "Part 4｜Four Agent Presets：四种 Agent 分别改变了什么",
    "Part 5｜Conclusion：这套设计解决了什么，又付出了什么",
)

REQUIRED_TOPIC_NUMBERS = (
    "1.1", "1.2",
    *(f"{part}.{topic}" for part in range(2, 6) for topic in range(1, 6)),
)

REQUIRED_TOPIC_IDS = tuple(f"section-{number.replace('.', '-')}" for number in REQUIRED_TOPIC_NUMBERS)

REQUIRED_DIAGRAMS = (
    "13-session-composition-turn",
    "14-host-preset-agent",
    "15-history-to-model-surface",
    "16-native-vs-code",
    "17-session-activation",
)

REQUIRED_CONTENT = (
    "Session A 与 Session B 加入同一份 Standard Preset",
    "组件依赖满足以后",
    "注册进入 Preset 的作用范围",
    "当前 E2B 是 ephemeral POC",
    "不是 hard multi-tenant boundary",
    "可以包含零个、一个或多个 Step",
    "packages/core/agent-loop/src/agent.ts",
    "**源码批注版（中文注释为后加）：**",
    "作用范围和生命周期",
    "Cordis 不负责决定模型下一步做什么",
    "AgentLoop 的职责仍然明确",
    "一个 Session 从创建到 Turn 结束",
    "Host plane 与 Agent plane",
    "依赖倒置解决源码应该依赖谁",
    "Consumer 只依赖稳定的 Service Definition",
    "Composition 是选择并安装 Provider 的地方",
    "Filesystem 与 Subprocess 还必须共同描述同一个 Execution World",
    "这个注册动作改变了 Plugin 外部的状态，所以它是一项副作用",
    "持久 SessionEvent 不由 Effect 撤销",
    "Agent 负责当前执行，Session 记录持久事实",
    "SessionEvent",
    "压缩上下文不等于删除历史",
    "Model Surface",
    "Model-visible means logged",
    "Activation 不是另一种 Session",
    "Tool Execution Pipeline",
    "四个 Preset",
    "At what point does it become a Runtime?",
)

PROHIBITED_UNSOURCED_INFERENCES = (
    "如果模型第一次搜索文件",
    "模型 Adapter 可以改变而不重写 Turn 顺序",
    "Tool Runtime 可以增加审批或并发调度而不重写模型流",
    "Persistence 可以从 JSONL 切到 SQLite",
)

PROHIBITED_NARRATION = (
    "先说结论",
    "术语翻译",
    "实现层（第一次读可以跳过）",
    "怎么读这篇文章",
    "先记住",
    "一句人话",
    "配方",
    "公交司机",
    "办公楼",
    "账本",
    "遥控器",
    "脑子里的世界",
    "最漂亮的点",
    "README 对这个关系写得很直接",
    "这就是 Overview 需要的",
    ".plain-answer",
    ".implementation-note",
)

PROHIBITED_SHOWCASE_MARKERS = (
    "data-tool-lab",
    "data-preset-workbench",
    "data-projection-lab",
    "data-execution-lab",
    "class=\"atlas",
    "data-slide=",
    "simulator",
    "runtime-map",
)

PROHIBITED_STALE_TUTORIAL = (
    "├── Agent 选择：",
    "packages/core-agent-loop",
    "packages/core-session",
    "packages/shell-tool-bash",
    "@mod ",
    "Roll Log",
    "每个 Agent 建独立的 realm",
    "第一个说不停",
    "| bail |",
    "FSERB",
)

PROHIBITED_OVERVIEW_JARGON = (
    "effective view",
    "wire identity",
    "single-flight",
    "durable facts",
    "Deferred Discovery",
)

EVIDENCE_PROVENANCE_LABELS = (
    "**源码摘录：**",
    "**源码批注版（中文注释为后加）：**",
    "**配置摘录：**",
    "**流程图摘录：**",
    "**忠实伪代码（非仓库原文）：**",
    "**关系整理（非仓库原文）：**",
)

REQUIRED_OVERVIEW_GLOSSARY = (
    "Host",
    "Agent",
    "Inbox",
    "Session",
    "SessionEvent",
    "Child Session",
    "Activation",
    "Plugin",
    "Service",
    "Context",
    "Composition",
    "Agent Preset",
    "Preset generation",
    "Host / Agent plane",
    "Registration",
    "Scope",
    "Event",
    "Fiber",
    "Effect",
    "Disposer",
    "Waterfall",
    "Service Definition / Provider / Consumer",
    "Dependency Inversion",
    "Capability Seam",
    "Execution World",
    "Persistence",
    "Compaction",
    "Subagent",
    "AgentLoop",
    "Turn",
    "Step",
    "Projection",
    "Model Surface",
    "Tool Presentation",
    "Agent Runtime",
)

REQUIRED_OVERVIEW_DOCS = (
    "docs/architecture.md",
    "docs/cordis-primer.md",
    "docs/cordis-tutorial/03-services.md",
    "packages/preset/agent-presets/README.md",
    "docs/subsystems/session.md",
    "docs/subsystems/system-prompt.md",
    "docs/subsystems/tools.md",
    "docs/tool-execution-pipeline.md",
    "docs/capability-seams.md",
    "docs/cookbook/adding-a-package.md",
    "docs/cookbook/adding-a-tool.md",
    "docs/subsystems/subagent.md",
    "docs/subsystems/compaction.md",
)

PART_HEADING_RE = re.compile(
    r"^##\s+(.+?)\s+\{#(part-[a-z0-9-]+)\}\s*$",
    re.MULTILINE,
)
TOPIC_HEADING_RE = re.compile(
    r"^###\s+(\d+\.\d+)\s+(.+?)\s+\{#(section-\d+-\d+)\}\s*$",
    re.MULTILINE,
)


class PageParser(HTMLParser):
    """Collect structural and text-density facts from rendered HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.references: list[tuple[str, str, str]] = []
        self.diagram_sources: list[str] = []
        self.iframes: list[dict[str, str]] = []
        self.headings: list[tuple[str, str]] = []
        self.visible_text: list[str] = []
        self._heading_tag: str | None = None
        self._heading_text: list[str] = []
        self._excluded_depth = 0
        self._source_note_depth = 0
        self.dialogs = 0
        self.pagefind_bodies = 0
        self.theme_toggles = 0
        self.article_bodies = 0
        self.toc_containers = 0
        self.paragraphs = 0
        self.tables = 0
        self.pre_blocks = 0
        self.details = 0
        self.source_links = 0
        self.section_leads = 0
        self.evidence_summaries = 0
        self.source_note_pre_blocks = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        classes = set(values.get("class", "").split())

        if tag in {"style", "script"}:
            self._excluded_depth += 1
        if values.get("id"):
            self.ids.append(values["id"])
        if tag == "iframe":
            self.iframes.append(values)
        if tag == "dialog":
            self.dialogs += 1
        if tag == "p":
            self.paragraphs += 1
        if tag == "table":
            self.tables += 1
        if tag == "pre":
            self.pre_blocks += 1
            if self._source_note_depth:
                self.source_note_pre_blocks += 1
        if tag == "details":
            self.details += 1
            if "source-note" in classes:
                self._source_note_depth += 1
        if "section-lead" in classes:
            self.section_leads += 1
        if "evidence-summary" in classes:
            self.evidence_summaries += 1
        if tag in {"h2", "h3"}:
            self._heading_tag = tag
            self._heading_text = []
        if "data-pagefind-body" in values:
            self.pagefind_bodies += 1
        if "data-theme-toggle" in values:
            self.theme_toggles += 1
        if "data-dsh-article" in values:
            self.article_bodies += 1
        if "data-article-toc" in values:
            self.toc_containers += 1
        if "data-source-evidence" in values:
            self.source_links += 1
        if values.get("data-diagram-src"):
            self.diagram_sources.append(values["data-diagram-src"])

        for name in ("href", "src", "data-diagram-src"):
            value = values.get(name)
            if value:
                self.references.append((tag, name, value))

    def handle_endtag(self, tag: str) -> None:
        if tag == self._heading_tag:
            self.headings.append((tag, " ".join(self._heading_text).strip()))
            self._heading_tag = None
            self._heading_text = []
        if tag in {"style", "script"} and self._excluded_depth:
            self._excluded_depth -= 1
        if tag == "details" and self._source_note_depth:
            self._source_note_depth -= 1

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text or self._excluded_depth:
            return
        self.visible_text.append(text)
        if self._heading_tag:
            self._heading_text.append(text)


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def has_front_matter_value(source: str, key: str, value: str) -> bool:
    return re.search(rf"^{re.escape(key)}:\s*{re.escape(value)}\s*$", source, re.MULTILINE) is not None


def validate_front_matter(source: str, errors: list[str]) -> None:
    require(has_front_matter_value(source, "layout", "dsh_runtime_wiki"), "Markdown must use layout: dsh_runtime_wiki", errors)
    require(has_front_matter_value(source, "public", "true"), "Markdown page must be public", errors)
    require(has_front_matter_value(source, "type", "agent-harness"), "Markdown page must use type: agent-harness", errors)
    require(has_front_matter_value(source, "permalink", "/wiki/DSH/"), "Markdown page must publish at /wiki/DSH/", errors)
    require(has_front_matter_value(source, "source_revision", f'"{REVISION}"'), "Markdown must disclose the pinned DSH revision", errors)


def validate_topic_sections(source: str, errors: list[str]) -> None:
    matches = list(TOPIC_HEADING_RE.finditer(source))
    for index, match in enumerate(matches):
        number, title, topic_id = match.groups()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        section = source[match.end():end]
        prefix = f"section {number} ({title})"

        lead_at = section.find("{: .section-lead}")
        source_note_at = section.find('<details class="source-note"')

        require(topic_id == f"section-{number.replace('.', '-')}", f"{prefix} has mismatched explicit id {topic_id}", errors)
        require(
            re.match(r"\s*[^\n]+\n\{:\s*\.section-lead\}", section) is not None,
            f"{prefix} must open with one natural .section-lead paragraph",
            errors,
        )
        require(source_note_at >= 0, f"{prefix} needs a source-note block", errors)
        require(
            lead_at >= 0 and source_note_at > lead_at,
            f"{prefix} must present prose before its source evidence",
            errors,
        )

        details_match = re.search(
            r'<details class="source-note"[^>]*>(.*?)</details>',
            section,
            re.DOTALL,
        )
        if not details_match:
            continue
        details = details_match.group(1)
        require(details.lstrip().startswith("<summary>源码依据："), f"{prefix} source note needs a consistent 源码依据 summary", errors)
        require("{: .evidence-summary}" in details, f"{prefix} source note needs an evidence summary", errors)
        require("data-source-evidence" in details, f"{prefix} source note needs a pinned evidence link", errors)
        provenance_labels = [label for label in EVIDENCE_PROVENANCE_LABELS if label in details]
        require(
            len(provenance_labels) == 1,
            f"{prefix} source note must identify exactly one evidence provenance type",
            errors,
        )
        if provenance_labels:
            require(
                re.search(re.escape(provenance_labels[0]) + r"\s*```", details) is not None,
                f"{prefix} evidence provenance label must sit directly above its block",
                errors,
            )
        require(
            re.search(r"^```(?:[a-zA-Z0-9_-]+)?\s*$.*?^```\s*$", details, re.MULTILINE | re.DOTALL) is not None,
            f"{prefix} source note needs pseudocode, a short excerpt, or a structure sample",
            errors,
        )


def validate_markdown(source: str, errors: list[str]) -> None:
    validate_front_matter(source, errors)
    require("/Users/" not in source, "Markdown contains a local absolute path", errors)
    content = re.sub(r"<!--.*?-->", "", source, flags=re.DOTALL)

    part_matches = list(PART_HEADING_RE.finditer(content))
    topic_matches = list(TOPIC_HEADING_RE.finditer(content))
    part_ids = tuple(match.group(2) for match in part_matches)
    part_titles = tuple(match.group(1) for match in part_matches)
    topic_numbers = tuple(match.group(1) for match in topic_matches)
    topic_ids = tuple(match.group(3) for match in topic_matches)

    require(part_ids == REQUIRED_PART_IDS, "Markdown must contain the five Part headings in the expected order", errors)
    require(part_titles == REQUIRED_PART_TITLES, "Markdown must use the reviewed Part titles", errors)
    require(topic_numbers == REQUIRED_TOPIC_NUMBERS, "Markdown must contain the reviewed topic sequence", errors)
    require(topic_ids == REQUIRED_TOPIC_IDS, "Markdown topic ids must match the reviewed topic sequence", errors)

    for match in part_matches:
        require(re.search(r"[\u3400-\u9fff]", match.group(1)) is not None, f"Part heading must be Chinese-first: {match.group(1)}", errors)
    for match in topic_matches:
        require(re.search(r"[\u3400-\u9fff]", match.group(2)) is not None, f"Topic heading must be Chinese-first: {match.group(2)}", errors)

    topic_count = len(REQUIRED_TOPIC_IDS)
    require(content.count("{: .section-lead}") == topic_count, "every topic needs one natural .section-lead paragraph", errors)
    require(content.count('<details class="source-note"') == topic_count, "every topic needs an expandable source note", errors)
    require(content.count("{: .evidence-summary}") == topic_count, "every source note needs a reader-facing evidence summary", errors)
    require(content.count("data-source-evidence") >= topic_count, "Markdown needs at least one source evidence link per topic", errors)

    talk_routes = re.findall(r"<!--\s*talk-route:\s*(.*?)\s*-->", source)
    require(len(talk_routes) == 5, "Markdown needs one invisible talk-route comment before each Part", errors)
    for index, route in enumerate(talk_routes, start=1):
        require(f"Part {index}" in route, f"talk-route {index} must identify Part {index}", errors)
        require("full:" in route and "short:" in route, f"talk-route {index} needs full and short paths", errors)

    overview_match = re.search(
        r"^##\s+Part 1｜.*?^##\s+Part 2｜",
        content,
        re.MULTILINE | re.DOTALL,
    )
    if overview_match:
        overview_prose = re.sub(
            r'<details class="source-note"[^>]*>.*?</details>',
            "",
            overview_match.group(0),
            flags=re.DOTALL,
        )
        for marker in PROHIBITED_OVERVIEW_JARGON:
            require(marker not in overview_prose, f"Overview prose contains implementation-first jargon: {marker}", errors)
        for term in REQUIRED_OVERVIEW_GLOSSARY:
            require(f"| `{term}` |" in overview_prose, f"Overview glossary is missing: {term}", errors)
        for path in REQUIRED_OVERVIEW_DOCS:
            require(path in overview_match.group(0), f"Overview documentation index is missing: {path}", errors)

    diagram_includes = re.findall(r"\{%\s+include\s+dsh/diagram\.html\s+.*?%\}", content)
    require(len(diagram_includes) == len(REQUIRED_DIAGRAMS), "Markdown must include exactly five focused diagram components", errors)
    for slug in REQUIRED_DIAGRAMS:
        require(any(f"{slug}.html" in include for include in diagram_includes), f"Markdown does not open required diagram: {slug}", errors)

    for marker in REQUIRED_CONTENT:
        require(marker in content, f"Markdown is missing required explanation or boundary: {marker}", errors)
    for marker in PROHIBITED_SHOWCASE_MARKERS:
        require(marker not in content, f"old showcase/simulator structure remains in Markdown: {marker}", errors)
    for marker in PROHIBITED_STALE_TUTORIAL:
        require(marker not in content, f"stale tutorial claim or path remains in Markdown: {marker}", errors)
    for marker in PROHIBITED_NARRATION:
        require(marker not in content, f"prohibited narration/template remains in Markdown: {marker}", errors)
    for marker in PROHIBITED_UNSOURCED_INFERENCES:
        require(marker not in content, f"unsourced AgentLoop inference remains in Markdown: {marker}", errors)

    revisions = re.findall(
        r"https://github\.com/deepseek-ai/deepseek-harness/(?:blob|tree)/([^/\s)]+)",
        content,
    )
    require(bool(revisions), "Markdown needs fixed-version DSH source links", errors)
    require(all(revision == REVISION for revision in revisions), "all DSH source links must use the disclosed revision", errors)

    han_count = len(re.findall(r"[\u3400-\u9fff]", content))
    require(han_count >= 10_500, f"Chinese long-form body is too short ({han_count} Han characters; need 10500)", errors)
    validate_topic_sections(content, errors)


def validate_support_files(errors: list[str]) -> None:
    require(not LEGACY_HTML_PAGE.exists(), "legacy wiki/DSH/index.html must not coexist with the Markdown source", errors)
    require(AUTHORING_GUIDE.is_file(), f"missing Markdown authoring guide: {AUTHORING_GUIDE}", errors)
    require(LAYOUT_PATH.is_file(), f"missing page layout: {LAYOUT_PATH}", errors)
    require(INCLUDE_PATH.is_file(), f"missing diagram include: {INCLUDE_PATH}", errors)
    require(STYLE_PATH.is_file(), f"missing page stylesheet: {STYLE_PATH}", errors)
    require(SCRIPT_PATH.is_file(), f"missing interaction script: {SCRIPT_PATH}", errors)

    if AUTHORING_GUIDE.is_file():
        guide = AUTHORING_GUIDE.read_text(encoding="utf-8")
        for marker in PROHIBITED_NARRATION:
            require(marker not in guide, f"old narration/template remains in authoring guide: {marker}", errors)

    if LAYOUT_PATH.is_file():
        layout = LAYOUT_PATH.read_text(encoding="utf-8")
        for marker in (
            "{{ content }}",
            "data-dsh-article",
            "data-article-toc",
            "data-pagefind-body",
            "data-diagram-dialog",
            "'/assets/css/dsh-runtime-wiki.css' | relative_url",
            "'/assets/js/dsh-runtime-wiki.js' | relative_url",
        ):
            require(marker in layout, f"page layout is missing marker: {marker}", errors)

    if INCLUDE_PATH.is_file():
        include = INCLUDE_PATH.read_text(encoding="utf-8")
        require("include.src | relative_url" in include, "diagram include must make its source baseurl-safe", errors)
        require("data-diagram-open" in include, "diagram include must create a lazy-open trigger", errors)

    if STYLE_PATH.is_file():
        stylesheet = STYLE_PATH.read_text(encoding="utf-8")
        for marker in (
            'html[data-theme="light"]',
            "@media (max-width: 780px)",
            "prefers-reduced-motion",
            ".reading-column",
            ".dsh-article > h2",
            ".dsh-article > h3",
            ".section-lead",
            ".term-note",
            ".toc-part",
        ):
            require(marker in stylesheet, f"stylesheet is missing Markdown-page marker: {marker}", errors)

    if SCRIPT_PATH.is_file():
        script = SCRIPT_PATH.read_text(encoding="utf-8")
        for marker in (
            "[data-dsh-article]",
            "[data-article-toc]",
            "toc-part",
            "[data-diagram-open]",
            "[data-diagram-dialog]",
            "removeAttribute('src')",
            "dsh-runtime-theme",
        ):
            require(marker in script, f"interaction script is missing marker: {marker}", errors)


def validate_diagrams(errors: list[str]) -> None:
    spec_suffixes = ("architecture", "workflow", "sequence", "dataflow", "lifecycle")
    for slug in REQUIRED_DIAGRAMS:
        artifact = DIAGRAM_DIR / f"{slug}.html"
        require(artifact.is_file(), f"missing Archify HTML: {artifact}", errors)
        specifications = [
            DIAGRAM_DIR / f"{slug}.{suffix}.json"
            for suffix in spec_suffixes
            if (DIAGRAM_DIR / f"{slug}.{suffix}.json").is_file()
        ]
        require(bool(specifications), f"missing Archify specification: {slug}", errors)

        if artifact.is_file():
            artifact_html = artifact.read_text(encoding="utf-8")
            require(
                "<svg" in artifact_html,
                f"Archify HTML must contain an inline SVG: {artifact}",
                errors,
            )

        for specification in specifications:
            specification_text = specification.read_text(encoding="utf-8")
            require(
                '"quality_profile": "showcase"' in specification_text,
                f"Archify specification must use showcase quality: {specification}",
                errors,
            )


def validate_rendered_page(html: str, errors: list[str]) -> None:
    parser = PageParser()
    parser.feed(html)

    require("{{" not in html and "{%" not in html, "rendered page contains Liquid residue", errors)
    require("/Users/" not in html, "rendered page contains a local absolute path", errors)
    require(len(parser.ids) == len(set(parser.ids)), "rendered page contains duplicate id attributes", errors)
    require(set(REQUIRED_PART_IDS).issubset(parser.ids), "rendered page is missing one or more Part ids", errors)
    require(set(REQUIRED_TOPIC_IDS).issubset(parser.ids), "rendered page is missing one or more topic ids", errors)
    require(parser.article_bodies == 1, "rendered page must contain one Markdown article body", errors)
    require(parser.toc_containers == 1, "rendered page must contain one generated-TOC container", errors)
    require(parser.dialogs == 1, "rendered page must contain one optional diagram dialog", errors)
    require(len(parser.iframes) == 1, "only the lazy diagram-dialog iframe is allowed", errors)
    require(not any(frame.get("src") for frame in parser.iframes), "diagram iframe must not load before the reader opens it", errors)
    require(parser.pagefind_bodies == 1, "rendered page must expose exactly one Pagefind body", errors)
    require(parser.theme_toggles == 1, "rendered page must expose one theme control", errors)
    require(len(parser.diagram_sources) == len(REQUIRED_DIAGRAMS), "rendered page must expose exactly five focused diagram links", errors)
    require(parser.paragraphs >= 90, "rendered page needs at least ninety prose paragraphs", errors)
    require(parser.tables >= 7, "rendered page needs at least seven explanatory tables", errors)
    require(parser.pre_blocks >= len(REQUIRED_TOPIC_IDS), "rendered page needs concrete pseudocode or source excerpts", errors)
    topic_count = len(REQUIRED_TOPIC_IDS)
    require(parser.details == topic_count, "rendered page needs one source note per topic", errors)
    require(parser.source_links >= topic_count, "rendered page needs at least one source evidence link per topic", errors)
    require(parser.section_leads == topic_count, "rendered page needs one natural section lead per topic", errors)
    require(parser.evidence_summaries == topic_count, "rendered source notes need reader-facing evidence summaries", errors)
    require(parser.source_note_pre_blocks == topic_count, "each rendered source note needs pseudocode or a short source excerpt", errors)

    h2s = [text for tag, text in parser.headings if tag == "h2"]
    h3s = [text for tag, text in parser.headings if tag == "h3"]
    require(len(h2s) == 5, "rendered page must use exactly five Part-level h2 headings", errors)
    require(len(h3s) == len(REQUIRED_TOPIC_IDS), "rendered page must use the reviewed number of topic h3 headings", errors)
    for heading in h2s + h3s:
        require(re.search(r"[\u3400-\u9fff]", heading) is not None, f"rendered heading must be Chinese-first: {heading}", errors)

    visible = " ".join(parser.visible_text)
    han_count = len(re.findall(r"[\u3400-\u9fff]", visible))
    require(han_count >= 10_500, f"rendered Chinese body is too short ({han_count} Han characters; need 10500)", errors)

    for slug in REQUIRED_DIAGRAMS:
        require(any(f"{slug}.html" in source for source in parser.diagram_sources), f"rendered page does not open required diagram: {slug}", errors)

    for tag, name, value in parser.references:
        if value.startswith(("#", "https://", "http://", "mailto:", "data:")):
            continue
        require(value.startswith(BASEURL), f"rendered {tag}[{name}] is not baseurl-safe: {value}", errors)


def validate_source(errors: list[str]) -> None:
    require(SOURCE_PAGE.is_file(), f"missing Markdown source page: {SOURCE_PAGE}", errors)
    validate_support_files(errors)
    validate_diagrams(errors)
    if SOURCE_PAGE.is_file():
        validate_markdown(SOURCE_PAGE.read_text(encoding="utf-8"), errors)


def validate_rendered(rendered_root: Path, errors: list[str]) -> None:
    rendered_page = rendered_root / "wiki" / "DSH" / "index.html"
    require(rendered_page.is_file(), f"missing rendered page: {rendered_page}", errors)
    if rendered_page.is_file():
        validate_rendered_page(rendered_page.read_text(encoding="utf-8"), errors)

    for asset in (
        rendered_root / "assets" / "css" / STYLE_PATH.name,
        rendered_root / "assets" / "js" / SCRIPT_PATH.name,
    ):
        require(asset.is_file(), f"missing rendered asset: {asset}", errors)

    wiki_index = rendered_root / "wiki" / "index.html"
    require(wiki_index.is_file(), f"missing rendered Wiki index: {wiki_index}", errors)
    if wiki_index.is_file():
        index_html = wiki_index.read_text(encoding="utf-8")
        require('href="/Ryanhu2001/wiki/DSH/"' in index_html, "rendered Wiki index is missing the DSH page", errors)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rendered-root", type=Path, help="Also validate a completed Jekyll output directory.")
    args = parser.parse_args()

    errors: list[str] = []
    validate_source(errors)
    if args.rendered_root:
        validate_rendered(args.rendered_root.resolve(), errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    scope = "Markdown source and rendered HTML" if args.rendered_root else "Markdown source"
    print(f"DeepSeek Harness wiki check passed ({scope}; 5 Parts; {len(REQUIRED_TOPIC_IDS)} topics; {len(REQUIRED_DIAGRAMS)} focused diagrams).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
