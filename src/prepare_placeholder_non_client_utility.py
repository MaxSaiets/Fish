from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


ROOT = Path(r"D:\FISH\fish-sync")
DEFAULT_PLACEHOLDER_ROOT = ROOT / "public" / "horoshop-image-utility-all-placeholders-clean"
DEFAULT_REAL_UPLOAD_REPORT = ROOT / "data" / "real_client_photo_upload_report_20260608.json"
DEFAULT_REAL_UTILITY_REPORT = ROOT / "data" / "real_client_photo_utility_report_20260608_filtered.json"
DEFAULT_OUTPUT_ROOT = ROOT / "public" / "placeholder-non-client-utility"
DEFAULT_REPORT = ROOT / "data" / "placeholder_non_client_utility_report_20260608.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--placeholder-root", type=Path, default=DEFAULT_PLACEHOLDER_ROOT)
    parser.add_argument("--real-upload-report", type=Path, default=DEFAULT_REAL_UPLOAD_REPORT)
    parser.add_argument("--real-utility-report", type=Path, default=DEFAULT_REAL_UTILITY_REPORT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--clear", action="store_true")
    parser.add_argument("--copy", action="store_true", help="Copy files instead of hardlinking.")
    return parser.parse_args()


def article_from_gallery_file(path: Path) -> str:
    return path.stem.split("@")[0].strip()


def load_real_articles(upload_report: Path, utility_report: Path) -> tuple[set[str], set[str]]:
    real_articles: set[str] = set()
    blocked_articles: set[str] = set()
    if upload_report.exists():
        report = json.loads(upload_report.read_text(encoding="utf-8"))
        for item in report.get("uploaded_articles", []):
            article = str(item.get("article") or "").strip()
            if article:
                real_articles.add(article)
    if utility_report.exists():
        report = json.loads(utility_report.read_text(encoding="utf-8"))
        for article in report.get("excluded_articles", []):
            article = str(article or "").strip()
            if article:
                blocked_articles.add(article)
    return real_articles, blocked_articles


def safe_clear_output_root(path: Path) -> None:
    resolved = path.resolve()
    public_root = (ROOT / "public").resolve()
    if public_root not in resolved.parents:
        raise RuntimeError(f"Refusing to clear outside project public directory: {resolved}")
    if resolved.name != "placeholder-non-client-utility":
        raise RuntimeError(f"Refusing to clear unexpected output directory: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)


def link_or_copy(source: Path, target: Path, force_copy: bool) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if force_copy:
        shutil.copy2(source, target)
        return "copied"
    try:
        os.link(source, target)
        return "hardlinked"
    except OSError:
        shutil.copy2(source, target)
        return "copied"


def build_subset(args: argparse.Namespace) -> dict:
    placeholder_root = args.placeholder_root.resolve()
    output_root = args.output_root.resolve()
    if not placeholder_root.exists():
        raise FileNotFoundError(f"Placeholder root not found: {placeholder_root}")

    real_articles, blocked_articles = load_real_articles(
        args.real_upload_report,
        args.real_utility_report,
    )
    excluded_articles = real_articles | blocked_articles

    if args.clear:
        safe_clear_output_root(output_root)
    else:
        output_root.mkdir(parents=True, exist_ok=True)

    prepared = []
    skipped_real = []
    skipped_blocked = []
    link_mode_counts = {"hardlinked": 0, "copied": 0}

    for source in sorted(placeholder_root.rglob("*")):
        if not source.is_file():
            continue
        article = article_from_gallery_file(source)
        if not article:
            continue
        if article in real_articles:
            skipped_real.append(article)
            continue
        if article in blocked_articles:
            skipped_blocked.append(article)
            continue
        target = output_root / source.name
        mode = link_or_copy(source, target, args.copy)
        link_mode_counts[mode] = link_mode_counts.get(mode, 0) + 1
        prepared.append(
            {
                "article": article,
                "source": str(source),
                "target": str(target),
            }
        )

    report = {
        "status": "complete",
        "placeholder_root": str(placeholder_root),
        "output_root": str(output_root),
        "real_upload_report": str(args.real_upload_report),
        "real_utility_report": str(args.real_utility_report),
        "real_client_articles_excluded": len(real_articles),
        "blocked_articles_excluded": sorted(blocked_articles),
        "excluded_articles_total": len(excluded_articles),
        "prepared_placeholder_articles": len(prepared),
        "prepared_placeholder_files": len(prepared),
        "skipped_real_entries": len(skipped_real),
        "skipped_blocked_entries": len(skipped_blocked),
        "link_mode_counts": link_mode_counts,
        "policy": (
            "This package restores generated placeholder images for every product that does not have a confirmed local client photo. "
            "Confirmed real-client-photo articles are excluded so they keep their uploaded client images."
        ),
        "prepared_sample": prepared[:30],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    args = parse_args()
    report = build_subset(args)
    print(
        json.dumps(
            {
                "status": report["status"],
                "prepared_placeholder_articles": report["prepared_placeholder_articles"],
                "real_client_articles_excluded": report["real_client_articles_excluded"],
                "blocked_articles_excluded": report["blocked_articles_excluded"],
                "output_root": report["output_root"],
                "report": str(args.report),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
