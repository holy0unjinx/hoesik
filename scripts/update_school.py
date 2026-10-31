"""선린인터넷고 학교회계 — 새로 공시된 달만 받아온다.

열린 서울교육(`open.sen.go.kr`)은 표마다 목록 화면과 상세 화면이 있다.

1. 목록 `list0010v.do` 은 기준월을 최신순으로 10개씩 보여 준다.
2. 상세 `list0010d.do` 는 `stdr_month` 로 한 달을 걸러, `detPageIndex` 로 10행씩 넘긴다.

증분 갱신은 **목록 첫 장만 읽고**, CSV 에 아직 없는 기준월만 상세로 내려간다.
전체 재수집(166개월 × 여러 장)은 하지 않는다.
"""

import datetime as dt

import sources

BASE = "https://open.sen.go.kr"
SCHOOL_CODE = "7010536"
NEIS_CODE = "B100000658"
SCHOOL_NAME = "선린인터넷고등학교"

# 표 이름 -> (엔드포인트 경로 조각, 상세 표의 번호 뒤 칸 이름)
TABLES = {
    "expense": (
        "MI000000000000000514/finance",
        ["집행일자", "집행장소", "집행금액", "집행목적", "참석자", "집행시간", "승인자"],
    ),
    "contracts": (
        "1/contractOpen",
        ["구분", "계약명", "계약일자", "계약금액", "계약업체명", "승인자"],
    ),
    "execution": (
        "MI000000000000000519/estimate",
        ["세부사업", "목", "예산액", "지출액", "잔액", "승인자"],
    ),
}

PAGE_SIZE = 10


def _list_url(table):
    return f"{BASE}/fus/{TABLES[table][0]}/list0010v.do"


def _detail_url(table):
    return f"{BASE}/fus/{TABLES[table][0]}/list0010d.do"


def recent_periods(table, pages=1):
    """목록 앞쪽 몇 장에서 기준월을 최신순으로 읽는다. `2026-09` -> `202609`."""
    periods = []
    for page in range(1, pages + 1):
        markup = sources.fetch_text(
            _list_url(table),
            data={
                "pageIndex": str(page),
                "searchOraCode": "000",
                "searchSchoolCode": SCHOOL_CODE,
            },
            referer=f"{BASE}/iframeList4.jsp",
        )
        rows = sources.rows_of(markup, which=0)
        if not rows:
            break
        for cells in rows:
            # [번호, 기준월, 기관명, 등록일자, 비고]
            if len(cells) < 2:
                continue
            token = cells[1].replace("-", "").strip()
            if token.isdigit() and len(token) == 6:
                periods.append(token)
    # 목록이 최신순이라 그대로 두되, 중복은 걷어낸다.
    return list(dict.fromkeys(periods))


def fetch_period(table, period):
    """한 기준월의 모든 행을 상세 화면에서 긁어온다."""
    fields = TABLES[table][1]
    collected = []
    page = 1
    while True:
        markup = sources.fetch_text(
            _detail_url(table),
            data={
                "school_code": SCHOOL_CODE,
                "neis_cd": NEIS_CODE,
                "school_name": SCHOOL_NAME,
                "stdr_month": period,
                "detPageIndex": str(page),
                "pageIndex": "1",
                "searchOraCode": "000",
                "searchSchoolCode": SCHOOL_CODE,
            },
            referer=_list_url(table),
        )
        rows = sources.rows_of(markup)
        for cells in rows:
            # [번호, *fields]
            if len(cells) < len(fields) + 1:
                continue
            no = cells[0].strip()
            if not no.isdigit():
                continue
            row = {"id": f"{period}-{no}", "기준월": period, "번호": no}
            row.update(dict(zip(fields, (c.strip() for c in cells[1:]))))
            collected.append(row)
        if len(rows) < PAGE_SIZE:
            break
        page += 1
        if page > 500:  # 무한 루프 방지
            raise sources.FetchError(f"{table} {period}: 페이지가 끝나지 않음")
    return collected


def periods_to_fetch(table, known_periods, recheck=2, pages=1):
    """받아올 기준월. CSV 에 없는 달 + 가장 최근 몇 달(뒤늦게 행이 붙는 경우)."""
    available = recent_periods(table, pages=pages)
    if not available:
        return []
    newest_known = max(known_periods) if known_periods else ""
    wanted = [p for p in available if p > newest_known]
    # 이미 받아 둔 최근 달도 다시 확인한다. 공시가 나중에 보강되는 경우가 있다.
    settled = sorted((p for p in available if p <= newest_known), reverse=True)
    wanted += settled[:recheck]
    # 아직 한 달도 없으면 목록에 있는 최신 달만.
    return sorted(dict.fromkeys(wanted))


def this_month():
    today = dt.date.today()
    return f"{today.year:04d}{today.month:02d}"
