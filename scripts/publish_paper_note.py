#!/usr/bin/env python3
"""Create a public paper-reading note for the Jekyll wiki."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WIKI_DIR = ROOT / "wiki"


def yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def slugify(title: str) -> str:
    slug = re.sub(r"[\\/:*?\"<>|#\[\]{}]", "", title).strip()
    slug = re.sub(r"\s+", " ", slug)
    return slug[:96] or "paper-reading-note"


def build_note(args: argparse.Namespace) -> str:
    today = dt.date.today().isoformat()
    date = args.date or today
    description = args.description or "Paper reading note."
    paper_title = args.paper_title or args.title

    frontmatter = [
        "---",
        f"title: {yaml_quote(args.title)}",
        "public: true",
        f"description: {yaml_quote(description)}",
        "type: paper-reading",
        f"date: {date}",
        f"paper_title: {yaml_quote(paper_title)}",
    ]

    optional_fields = {
        "authors": args.authors,
        "venue": args.venue,
        "year": args.year,
        "status": args.status,
        "source_url": args.source_url,
        "pdf_path": args.pdf_path,
    }
    for key, value in optional_fields.items():
        if value:
            frontmatter.append(f"{key}: {yaml_quote(str(value))}")

    frontmatter.append("---")

    body = args.body.strip() if args.body else ""
    if not body:
        body = "\n".join(
            [
                f"# {args.title}",
                "",
                "## 一句话判断",
                "",
                "TODO",
                "",
                "## 核心内容",
                "",
                "- 问题：",
                "- 贡献：",
                "- 方法：",
                "- 证据：",
                "",
                "## 关键图",
                "",
                "- Figure / Table：",
                "- 它在说明什么：",
                "- 为什么值得先看：",
                "",
                "## 最大疑点",
                "",
                "TODO",
                "",
                "## 建议动作",
                "",
                "TODO",
            ]
        )

    return "\n".join(frontmatter) + "\n\n" + body + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a wiki note that is automatically listed on /paper-reading/."
    )
    parser.add_argument("--title", required=True, help="Site note title.")
    parser.add_argument("--paper-title", help="Original paper title if different.")
    parser.add_argument("--description", help="Short list-page description.")
    parser.add_argument("--authors", help="Paper authors.")
    parser.add_argument("--venue", help="Venue or source.")
    parser.add_argument("--year", help="Publication year.")
    parser.add_argument("--status", default="reading", help="reading/read/reproduce/skip.")
    parser.add_argument("--source-url", help="Official paper URL.")
    parser.add_argument("--pdf-path", help="Local PDF path if applicable.")
    parser.add_argument("--date", help="YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--body-file", help="Markdown body file to use after front matter.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing note.")
    args = parser.parse_args()

    if args.body_file:
        args.body = Path(args.body_file).read_text(encoding="utf-8")
    else:
        args.body = ""

    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    path = WIKI_DIR / f"{slugify(args.title)}.md"
    if path.exists() and not args.force:
        print(f"Refusing to overwrite existing note: {path}", file=sys.stderr)
        return 1

    path.write_text(build_note(args), encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
