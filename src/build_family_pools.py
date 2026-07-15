"""
build_family_pools.py

Pre-builds the family real-photo pools (clean, no-watermark photos of each
product TYPE) used as the guaranteed fallback in mass_photo_pipeline.py.

Run ONCE before the main pipeline. Robust: multiple query variants,
retries, delays, clean-source filtering, watermark rejection.

    python src/build_family_pools.py --per-family 10
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mass_photo_pipeline as m

# Extra query variants per family to maximise clean hits from big retailers
EXTRA_QUERIES = {
    "spinning": ["спінінг вудилище rozetka", "спінінгове вудилище", "spinning rod fishing"],
    "carp_rod": ["коропове вудилище", "carp rod", "вудилище коропове rozetka"],
    "bolognese_rod": ["болонське вудилище", "bolognese rod"],
    "float_rod": ["махове вудилище", "поплавкове вудилище", "pole rod fishing"],
    "feeder_rod": ["фідерне вудилище", "feeder rod"],
    "feeder": ["годівниця фідерна", "feeder cage fishing"],
    "hook": ["рибальські гачки", "fishing hooks", "гачки рибальські уп"],
    "ready_rig": ["короповий монтаж готовий", "carp rig", "оснастка коропова"],
    "swivel": ["вертлюги рибальські", "fishing swivel", "застібка вертлюг"],
    "weight": ["грузила рибальські", "fishing weights", "груз коропове"],
    "groundbait": ["прикормка рибальська", "прикормка короп пакет", "groundbait fishing", "fishing groundbait bag"],
    "pellets": ["пелетс рибальський", "fishing pellets", "пелетс короп"],
    "pop_up_bait": ["поп-ап бойли", "pop-up boilies", "pop up carp"],
    "boilie": ["бойли карпові", "carp boilies", "бойли короп"],
    "pva_material": ["pva пакети карп", "pva mesh carp", "пва система"],
    "tools": ["рибальський інструмент", "fishing tool carp"],
    "line": ["волосінь рибальська", "fishing line spool", "шнур плетений"],
    "fluorocarbon": ["флюорокарбон рибальський", "fluorocarbon line"],
    "reel": ["котушка рибальська", "fishing reel", "котушка короп"],
    "chair": ["крісло коропове", "carp chair fishing"],
    "landing_net": ["підсак рибальський", "landing net fishing"],
    "keepnet": ["садок рибальський", "keepnet fishing"],
    "silicone_lure": ["силіконова приманка", "soft lure fishing", "віброхвіст приманка"],
    "wobbler": ["воблер рибальський", "fishing wobbler", "воблер приманка"],
    "spinner": ["блешня вертушка", "fishing spinner spoon", "блешня рибальська"],
    "float": ["поплавок рибальський", "fishing float"],
    "tackle_box": ["рибальська коробка органайзер", "tackle box fishing"],
    "bag": ["рибальська сумка", "fishing bag carp"],
    "cover": ["чохол для вудилища", "rod cover tube"],
    "jig_winter": ["зимова мормишка", "winter jig fishing", "мормишка приманка"],
    "rod_rest_accessory": ["підставка для вудилища", "rod pod fishing", "род под"],
    "mandula": ["мандула приманка", "mandula lure fishing"],
    "other": ["рибальське спорядження", "fishing tackle"],
}


def build_one(family: str, per_family: int) -> int:
    pool_dir = m.FAMILY_POOL_DIR / family
    pool_dir.mkdir(parents=True, exist_ok=True)
    have = sorted(pool_dir.glob("*.jpg"))
    if len(have) >= per_family:
        print(f"  {family}: already {len(have)} (skip)")
        return len(have)

    queries = [m.FAMILY_POOL_QUERIES.get(family, family)] + EXTRA_QUERIES.get(family, [])
    paths = list(have)
    n = len(paths)
    for q in queries:
        if len(paths) >= per_family:
            break
        results = m.ddg_image_search(q)

        def ok(r):
            # POOL photos are generic TYPE photos. Safe to accept any source
            # that is NOT a known watermarker (prom/dilf/fishfish/olx) and NOT
            # Russian. fishfish etc. are now in WATERMARK_PRONE, so excluded.
            # Final red-watermark check happens after download.
            u = (r.get("image") or "").lower()
            if any(b in u for b in m.RU_BLOCKED): return False
            if any(w in u for w in m.WATERMARK_PRONE_SOURCES): return False
            return m.is_relevant_relaxed(r, family)

        # prefer top-tier/clean-allowlist first, then any other acceptable source
        top = [r for r in results if ok(r) and m.is_clean_source(r.get("image", ""))]
        rest = [r for r in results if ok(r) and r not in top]
        cands = top + rest
        cands.sort(key=m._score, reverse=True)
        for r in cands:
            if len(paths) >= per_family:
                break
            tmp = pool_dir / f"pool_{n}.jpg"
            if m.download_image(r["image"], tmp):
                if m.red_watermark_ratio(tmp) < m.WATERMARK_RED_THRESHOLD:
                    paths.append(tmp)
                    n += 1
                else:
                    tmp.unlink(missing_ok=True)
        time.sleep(random.uniform(5, 8))  # rate-limit friendly
    print(f"  {family}: {len(paths)} clean photos")
    return len(paths)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-family", type=int, default=10)
    ap.add_argument("--only", default="", help="comma-separated families to build")
    args = ap.parse_args()

    fams = list(m.FAMILY_POOL_QUERIES.keys())
    if args.only:
        want = set(args.only.split(","))
        fams = [f for f in fams if f in want]

    print(f"Building pools for {len(fams)} families, target {args.per_family} each")
    summary = {}
    for fam in fams:
        summary[fam] = build_one(fam, args.per_family)

    print("\n=== Pool summary ===")
    weak = [f for f, c in summary.items() if c < 3]
    for f, c in sorted(summary.items()):
        print(f"  {f}: {c}")
    if weak:
        print(f"\nWEAK pools (<3): {weak}")


if __name__ == "__main__":
    main()
