from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from generate_missing_product_images import build_placeholder, load_variants


ROOT = Path(r"D:\FISH\fish-sync")
OUTPUT_ROOT = ROOT / "public" / "horoshop-image-utility-all-placeholders"
REPORT_PATH = ROOT / "data" / "horoshop_all_product_placeholder_utility_report.json"
MAX_FILES_PER_BATCH = 500
MAX_BYTES_PER_BATCH = 240 * 1024 * 1024
WINDOWS_FORBIDDEN = re.compile(r'[<>:"/\\|?*]')


@dataclass
class BatchStats:
    name: str
    file_count: int = 0
    total_bytes: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--clear", action="store_true")
    return parser.parse_args()


def ensure_output_root(path: Path, clear: bool) -> None:
    if clear and path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def ensure_batch(output_root: Path, current_batch: Path, stats: BatchStats, next_size: int) -> tuple[Path, BatchStats]:
    if stats.file_count < MAX_FILES_PER_BATCH and stats.total_bytes + next_size <= MAX_BYTES_PER_BATCH:
        return current_batch, stats
    batch_index = int(current_batch.name.split("-")[-1]) + 1
    next_batch = output_root / f"batch-{batch_index:03d}"
    next_batch.mkdir(parents=True, exist_ok=True)
    return next_batch, BatchStats(name=next_batch.name)


def filename_for_article(article: str) -> str:
    return f"{article}@gallery_common.jpg"


def is_filename_safe(article: str) -> bool:
    return not WINDOWS_FORBIDDEN.search(article) and article.strip(". ")


def main() -> int:
    args = parse_args()
    ensure_output_root(args.output_root, args.clear)

    variants = load_variants()
    items = sorted(variants.values(), key=lambda item: item.article.casefold())
    if args.offset:
        items = items[args.offset :]
    if args.limit:
        items = items[: args.limit]

    batch = args.output_root / "batch-001"
    batch.mkdir(parents=True, exist_ok=True)
    tmp_dir = args.output_root / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    stats = BatchStats(name=batch.name)
    batches: list[BatchStats] = []
    prepared: list[dict] = []
    skipped: list[dict] = []

    for index, info in enumerate(items, start=1):
        article = info.article.strip()
        if not is_filename_safe(article):
            skipped.append(
                {
                    "article": article,
                    "name": info.name,
                    "reason": "article_contains_windows_forbidden_filename_character",
                }
            )
            continue

        target_name = filename_for_article(article)
        tmp_target = tmp_dir / target_name
        build_placeholder(info, tmp_target)
        next_batch, next_stats = ensure_batch(args.output_root, batch, stats, tmp_target.stat().st_size)
        if next_batch != batch:
            batches.append(stats)
            batch, stats = next_batch, next_stats
        target = batch / target_name
        shutil.move(str(tmp_target), str(target))

        stats.file_count += 1
        stats.total_bytes += target.stat().st_size
        prepared.append(
            {
                "article": article,
                "name": info.name,
                "family": info.family,
                "path": str(target),
            }
        )
        if index % 250 == 0:
            args.report.write_text(
                json.dumps(
                    {
                        "status": "running",
                        "processed": index,
                        "prepared_count": len(prepared),
                        "skipped_count": len(skipped),
                        "current_batch": asdict(stats),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    batches.append(stats)
    report = {
        "status": "complete",
        "source": "generated_unique_demo_product_cards_from_local_product_metadata",
        "policy": "Generated illustrations are unique per article and are intended as temporary demo placeholders until exact client/vendor product photos are supplied. No copyrighted product photos are scraped or masked.",
        "output_root": str(args.output_root),
        "articles_seen": len(items),
        "prepared_count": len(prepared),
        "skipped_count": len(skipped),
        "batch_limit_files": MAX_FILES_PER_BATCH,
        "batch_limit_bytes": MAX_BYTES_PER_BATCH,
        "batches": [asdict(batch_item) for batch_item in batches],
        "prepared_sample": prepared[:20],
        "skipped": skipped,
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
