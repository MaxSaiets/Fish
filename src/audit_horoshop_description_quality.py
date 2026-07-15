from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(r"D:\FISH\fish-sync")
XML_PATH = ROOT / "public" / "horoshop.xml"
OUT = ROOT / "data" / "horoshop_description_quality_report.json"

TAG_RE = re.compile(r"<[^>]+>")
BAD_TOKENS = ("wterterwer", "qwerty", "asdf", "tetg", "тестовий товар")
AI_CLICHES = (
    "ідеальний вибір",
    "ідеальним вибором",
    "ідеально підходить",
    "ідеально підходяще",
    "ідеально підход",
    "ідеальним рішенням",
    "найкращих результатів",
    "високоякісного матеріалу",
    "незамінний інструмент",
    "незамінний елемент",
    "незамінним інструментом",
)
TEST_WORD_RE = re.compile(r"\b(?:тест|test)\b", re.IGNORECASE)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", value or ""))).strip()


def main() -> int:
    root = ET.parse(XML_PATH).getroot()
    items: list[dict] = []
    for offer in root.findall(".//offer"):
        article = str(offer.attrib.get("id") or "").strip()
        title = (offer.findtext("name") or "").strip()
        description = offer.findtext("description") or offer.findtext("description_ua") or ""
        text = clean_text(description)
        lower = text.lower()
        issues: list[str] = []
        if len(text) < 350:
            issues.append("short_description")
        if "—" in description or "–" in description:
            issues.append("long_dash")
        if any(token in lower for token in BAD_TOKENS):
            issues.append("bad_token")
        if text.lower().count("ідеальний") >= 2:
            issues.append("repetitive_ai_word")
        if any(phrase in lower for phrase in AI_CLICHES):
            issues.append("ai_cliche")
        if TEST_WORD_RE.search(lower):
            issues.append("test_word")
        if text.count(".") < 3:
            issues.append("too_few_sentences")
        if issues:
            items.append(
                {
                    "article": article,
                    "title": title,
                    "text_chars": len(text),
                    "issues": issues,
                    "sample": text[:500],
                }
            )

    by_issue: dict[str, int] = {}
    for item in items:
        for issue in item["issues"]:
            by_issue[issue] = by_issue.get(issue, 0) + 1

    payload = {
        "total_products": len(root.findall(".//offer")),
        "bad_count": len(items),
        "by_issue": dict(sorted(by_issue.items())),
        "bad_sample": items[:80],
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("total_products", "bad_count", "by_issue")}, ensure_ascii=False, indent=2))
    print(f"Report: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
