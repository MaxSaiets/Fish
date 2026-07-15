from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path


ROOT = Path(r"D:\FISH\fish-sync")
SOURCE_ROOT = ROOT / "public" / "generated-product-images"
OUTPUT_ROOT = ROOT / "public" / "horoshop-image-utility-placeholders"
REPORT_PATH = ROOT / "data" / "horoshop_placeholder_utility_report.json"
MAX_FILES_PER_BATCH = 500
MAX_BYTES_PER_BATCH = 240 * 1024 * 1024


@dataclass
class BatchStats:
    name: str
    file_count: int = 0
    total_bytes: int = 0


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        for child in path.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    path.mkdir(parents=True, exist_ok=True)


def next_gallery_name(article: str, ext: str) -> str:
    return f"{article}@gallery_common{ext}"


def ensure_batch(current_batch: Path, stats: BatchStats, next_size: int) -> tuple[Path, BatchStats]:
    if stats.file_count < MAX_FILES_PER_BATCH and stats.total_bytes + next_size <= MAX_BYTES_PER_BATCH:
        return current_batch, stats

    batch_index = int(current_batch.name.split("-")[-1]) + 1
    next_batch = OUTPUT_ROOT / f"batch-{batch_index:03d}"
    next_batch.mkdir(parents=True, exist_ok=True)
    return next_batch, BatchStats(name=next_batch.name)


def main() -> None:
    ensure_clean_dir(OUTPUT_ROOT)
    batch = OUTPUT_ROOT / "batch-001"
    batch.mkdir(parents=True, exist_ok=True)
    stats = BatchStats(name=batch.name)
    batches: list[BatchStats] = []
    prepared: list[dict] = []

    for article_dir in sorted(p for p in SOURCE_ROOT.iterdir() if p.is_dir()):
        article = article_dir.name.strip()
        source = article_dir / "1.jpg"
        if not source.exists():
            continue
        batch, stats = ensure_batch(batch, stats, source.stat().st_size)
        target = batch / next_gallery_name(article, source.suffix.lower())
        shutil.copy2(source, target)
        stats.file_count += 1
        stats.total_bytes += target.stat().st_size
        prepared.append({"article": article, "source": str(source), "target": str(target)})

    batches.append(stats)
    report = {
        "source_root": str(SOURCE_ROOT),
        "output_root": str(OUTPUT_ROOT),
        "articles_prepared": len(prepared),
        "files_prepared": len(prepared),
        "batches": [asdict(item) for item in batches],
        "prepared_sample": prepared[:20],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
