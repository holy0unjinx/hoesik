#!/usr/bin/env python3
"""새로 공시된 달만 받아 CSV 에 붙인다.

cron 이 매달 부르는 진입점이다. 하는 일은 넷뿐이다.

1. 목록 첫 장을 읽어 CSV 에 없는 기준월·게시글만 고른다.
2. 그 달만 상세(또는 PDF)로 받아온다.
3. 개인 이름을 가린다(`anonymize.py`).
4. `data/`·`site/data/` CSV 를 다시 쓴다.

과거 전체를 다시 긁지 않는다. 받아올 게 없으면 파일을 건드리지 않고 끝낸다.
git 커밋·push 는 `cron_update.sh` 가 한다.

    python3 scripts/update.py              # 학교 + 경찰서
    python3 scripts/update.py --school     # 학교만
    python3 scripts/update.py --police     # 경찰서만
    python3 scripts/update.py --dry-run    # 받아만 보고 파일은 그대로
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import anonymize
import sources
import update_police
import update_school

ROOT = Path(__file__).resolve().parent.parent
SITE_DATA = ROOT / "site" / "data"
RAW_DATA = ROOT / "data"

# site/data 이름 -> (data/ 이름, 중복 판정 키)
# site/data 쪽은 id 열이 있고, data/ 쪽은 같은 행에서 id 를 뺀 원본 꼴이다.
SCHOOL_FILES = {
    "expense": ("business_expense.csv", "id"),
    "contracts": ("contracts.csv", "id"),
    "execution": ("execution.csv", "id"),
}


def read_csv(path):
    if not path.exists():
        return [], []
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        return rows, list(reader.fieldnames or [])


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def update_school_table(table, recheck, dry_run, log):
    """학교회계 표 하나를 갱신한다. 새로 붙은 행 수를 돌려준다."""
    site_path = SITE_DATA / f"{table}.csv"
    raw_name, key = SCHOOL_FILES[table]
    existing, fieldnames = read_csv(site_path)
    if not fieldnames:
        log(f"  {table}: {site_path} 가 없다. 건너뛴다")
        return 0

    known_ids = {r[key] for r in existing}
    known_periods = {r["기준월"] for r in existing}
    periods = update_school.periods_to_fetch(table, known_periods, recheck=recheck)
    if not periods:
        log(f"  {table}: 목록에서 새 기준월을 찾지 못했다")
        return 0
    log(f"  {table}: 확인할 기준월 {', '.join(periods)}")

    fresh = []
    for period in periods:
        rows = update_school.fetch_period(table, period)
        new = [r for r in rows if r[key] not in known_ids]
        known_ids.update(r[key] for r in new)
        fresh += new
        log(f"    {period}: 공시 {len(rows)}행, 새 행 {len(new)}")

    if not fresh:
        return 0
    merged = existing + fresh
    # 기준월·번호 순으로 정렬해 diff 가 읽히게 둔다.
    merged.sort(key=lambda r: (r["기준월"], int(r["번호"])))
    merged, _ = anonymize.mask_table(table, merged)

    if dry_run:
        log(f"    (dry-run) {table} 에 {len(fresh)}행 추가하지 않음")
        return len(fresh)

    write_csv(site_path, fieldnames, merged)
    raw_fields = [c for c in fieldnames if c != "id"]
    write_csv(RAW_DATA / raw_name, raw_fields, merged)
    return len(fresh)


def update_police_table(dry_run, log):
    """용산경찰서 업무추진비를 갱신한다. 새로 붙은 행 수를 돌려준다."""
    site_path = SITE_DATA / "ys_expense.csv"
    existing, fieldnames = read_csv(site_path)
    if not fieldnames:
        log(f"  ys_expense: {site_path} 가 없다. 건너뛴다")
        return 0

    known_posts = {r["게시글"] for r in existing}
    known_months = {r["대상월"] for r in existing}
    posts = update_police.recent_posts()
    todo = [p for p in posts if p["board_no"] not in known_posts and p["month"]]
    if not todo:
        log(f"  ys_expense: 새 게시글 없음 (최근 {len(posts)}건 모두 보유)")
        return 0
    log(f"  ys_expense: 새 게시글 {len(todo)}건")

    fresh = []
    for post in todo:
        if post["month"] in known_months:
            log(f"    {post['month']}: 이미 있는 달이라 건너뜀 (글 {post['board_no']})")
            continue
        no = update_police.attach_no(post["board_no"])
        if not no:
            log(f"    {post['month']}: 첨부가 없다 — {post['title']}")
            continue
        rows, stated, parsed = update_police.parse_pdf(
            update_police.download_pdf(no), post["month"], post["board_no"]
        )
        if not rows:
            log(f"    {post['month']}: PDF 에서 행을 못 찾았다 (스캔 이미지일 수 있다)")
            continue
        if stated is not None and stated != parsed:
            # 합계가 어긋나도 버리지 않는다. 기존 데이터와 같은 방침.
            log(f"    {post['month']}: 합계 불일치 — PDF {stated:,} / 파싱 {parsed:,}")
        else:
            log(f"    {post['month']}: {len(rows)}행, 합계 {parsed:,} 확인")
        fresh += rows

    if not fresh:
        return 0
    merged = existing + fresh
    merged.sort(key=lambda r: (r["대상월"], r["일자"]))
    if dry_run:
        log(f"    (dry-run) ys_expense 에 {len(fresh)}행 추가하지 않음")
        return len(fresh)
    write_csv(site_path, fieldnames, merged)
    write_csv(RAW_DATA / "ys_expense.csv", fieldnames, merged)
    return len(fresh)


def remask(dry_run, log):
    """받아오지 않고, 이미 있는 CSV 에 마스킹 규칙만 다시 적용한다.

    `anonymize.py` 의 규칙을 고친 뒤 과거 자료까지 맞추는 데 쓴다.
    """
    changed = 0
    for table, (raw_name, _) in SCHOOL_FILES.items():
        site_path = SITE_DATA / f"{table}.csv"
        rows, fieldnames = read_csv(site_path)
        if not fieldnames:
            log(f"  {table}: {site_path} 가 없다. 건너뛴다")
            continue
        masked, _ = anonymize.mask_table(table, rows)
        diff = sum(1 for a, b in zip(rows, masked) if a != b)
        log(f"  {table}: {diff}행 변경")
        changed += diff
        if diff and not dry_run:
            write_csv(site_path, fieldnames, masked)
            write_csv(RAW_DATA / raw_name, [c for c in fieldnames if c != "id"], masked)
    return changed


def main(argv=None):
    parser = argparse.ArgumentParser(description="새로 공시된 달만 받아 CSV 에 붙인다")
    parser.add_argument("--school", action="store_true", help="학교회계만")
    parser.add_argument("--police", action="store_true", help="용산경찰서만")
    parser.add_argument("--dry-run", action="store_true", help="받아만 보고 파일은 그대로")
    parser.add_argument(
        "--remask",
        action="store_true",
        help="받아오지 않고 기존 CSV 에 마스킹 규칙만 다시 적용",
    )
    parser.add_argument(
        "--recheck",
        type=int,
        default=2,
        help="이미 받아 둔 최근 기준월을 몇 개 다시 볼지 (기본 2)",
    )
    args = parser.parse_args(argv)
    both = not (args.school or args.police)

    def log(message):
        print(message, flush=True)

    if args.remask:
        log("마스킹 규칙 재적용")
        changed = remask(args.dry_run, log)
        log("")
        log(f"{changed}행 변경" + (" (dry-run)" if args.dry_run else ""))
        return 0 if changed else 2

    added = 0
    failures = []

    if args.school or both:
        log("학교회계 (open.sen.go.kr)")
        for table in SCHOOL_FILES:
            try:
                added += update_school_table(table, args.recheck, args.dry_run, log)
            except (sources.FetchError, OSError) as exc:
                failures.append(f"{table}: {exc}")
                log(f"  {table}: 실패 — {exc}")

    if args.police or both:
        log("용산경찰서 (smpa.go.kr)")
        try:
            added += update_police_table(args.dry_run, log)
        except (sources.FetchError, OSError, ImportError) as exc:
            failures.append(f"ys_expense: {exc}")
            log(f"  ys_expense: 실패 — {exc}")

    log("")
    log(f"새 행 {added}개" + (" (dry-run)" if args.dry_run else ""))
    if failures:
        log(f"실패 {len(failures)}건:")
        for item in failures:
            log(f"  - {item}")
        return 1
    # 바뀐 게 없으면 2. cron 스크립트가 커밋을 건너뛰는 데 쓴다.
    return 0 if added else 2


if __name__ == "__main__":
    sys.exit(main())
