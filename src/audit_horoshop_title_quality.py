from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from horoshop_catalog import build_canonical_products, normalize_spaces


ROOT = Path(r"D:\FISH\fish-sync")
OUT = ROOT / "data" / "horoshop_title_quality_report.json"

TEST_WORD_RE = re.compile(r"\b(?:тест|test)\b", re.IGNORECASE)
EMPTY_PARENS_RE = re.compile(r"\(\s*\)")
BROKEN_FISHING_SLASH_RE = re.compile(r"\bFishing\s*/\d", re.IGNORECASE)
REPEATED_WORD_RE = re.compile(r"\b([А-Яа-яA-Za-zІіЇїЄєҐґ0-9]{4,})\s+\1\b", re.IGNORECASE)
BROKEN_TITLE_RE = re.compile(
    r"(?:\bкомлект\b|\bдудочок\b|\bвуд\.\d|\bшвидкоз\.|\b1уп\s*=|\(\s*\)|\(\s*\d+\s*\))",
    re.IGNORECASE,
)

BAD_FRAGMENTS = {
    "long_dash": ("—", "–"),
    "technical_fragment": ("шт.", "штек.", "с/к", "б/к", "м.544"),
    "double_space_marker": ("  ",),
}

RUSSIAN_WORD_RE = re.compile(
    r"\b(?:спиннинг|набор|крюч(?:ки|ок|ків)?|леск[аиуы]?|удилище|удочка|телескопическое|маховое|кольцами)\b",
    re.IGNORECASE,
)


def title_issues(title: str) -> list[str]:
    clean = normalize_spaces(title)
    lower = clean.lower()
    issues: list[str] = []
    if len(clean) < 8:
        issues.append("too_short")
    if TEST_WORD_RE.search(clean):
        issues.append("test_word")
    if EMPTY_PARENS_RE.search(clean):
        issues.append("empty_parentheses")
    if BROKEN_FISHING_SLASH_RE.search(clean):
        issues.append("broken_fishing_slash")
    if REPEATED_WORD_RE.search(clean):
        issues.append("repeated_word")
    if BROKEN_TITLE_RE.search(clean):
        issues.append("broken_fragment")
    if re.search(r"\s[,.;:]", clean):
        issues.append("space_before_punctuation")
    if re.search(r"[A-Za-zА-Яа-яІіЇїЄєҐґ]\s*/\s*\d", clean):
        issues.append("slash_before_digit")
    if RUSSIAN_WORD_RE.search(clean):
        issues.append("russian_word")
    for issue, fragments in BAD_FRAGMENTS.items():
        if any(fragment.lower() in lower for fragment in fragments):
            issues.append(issue)
    return sorted(set(issues))


def main() -> int:
    products = build_canonical_products()
    bad: list[dict[str, Any]] = []
    by_issue: Counter[str] = Counter()
    by_family: dict[str, Counter[str]] = {}

    for product in products:
        title = normalize_spaces(product.get("title", ""))
        issues = title_issues(title)
        if not issues:
            continue
        family = normalize_spaces(product.get("family", "")) or "unknown"
        for issue in issues:
            by_issue[issue] += 1
            by_family.setdefault(family, Counter())[issue] += 1
        bad.append(
            {
                "article": product.get("article"),
                "family": family,
                "parent": product.get("parent"),
                "title": title,
                "source_name": product.get("source_name"),
                "issues": issues,
            }
        )

    report = {
        "total_products": len(products),
        "bad_count": len(bad),
        "by_issue": dict(by_issue.most_common()),
        "by_family": {family: dict(counter.most_common()) for family, counter in sorted(by_family.items())},
        "bad_sample": bad[:200],
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("total_products", "bad_count", "by_issue")}, ensure_ascii=False, indent=2))
    print(f"Report: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
