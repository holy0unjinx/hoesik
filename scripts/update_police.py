"""용산경찰서장 업무추진비 — 새로 올라온 게시글만 받아온다.

서울경찰청(`smpa.go.kr`) 사전정보공표 게시판은 매달 글 하나에 PDF 한 개를 붙인다.

1. 목록 `psDeclareBoardList.do` 가 글 번호(`boardNo`)를 최신순으로 보여 준다.
2. 본문 `psDeclareBoardView.do` 에 `attachfileDownload(..., '<attachNo>')` 가 있다.
3. `attachfileDownload.do?attachNo=...` 가 PDF 를 그대로 준다.

증분 갱신은 **목록 첫 장만 읽고**, CSV 의 `게시글` 열에 없는 글만 PDF 를 내려받는다.
이미 받아 둔 131개 글을 다시 긁지 않는다.
"""

import re

import sources

BASE = "https://www.smpa.go.kr"
LIST_URL = f"{BASE}/user/action/psDeclareBoardList.do?ps_opendata_id=113&menuCode=ys"
VIEW_URL = f"{BASE}/user/action/psDeclareBoardView.do"
FILE_URL = f"{BASE}/common/attachfile/attachfileDownload.do"
BOARD_INFO_NO = "1810"

_BOARD_NO = re.compile(r"goDeclareBoardView\('(\d+)',\s*'View',\s*'(\d+)'\)")
_ATTACH_NO = re.compile(r"attachfileDownload\('[^']*',\s*'(\d+)'\)")
# `26년 9월 ...` / `2026년 09월 ...`
_TITLE_MONTH = re.compile(r"(\d{2,4})\s*년\s*(\d{1,2})\s*월")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_AMOUNT = re.compile(r"^[0-9][0-9,]*$")


def recent_posts(pages=1):
    """목록에서 `(게시글번호, 제목, 대상월)` 을 최신순으로 읽는다."""
    posts = []
    for page in range(1, pages + 1):
        url = LIST_URL if page == 1 else f"{LIST_URL}&pageIndex={page}"
        markup = sources.fetch_text(url)
        rows = sources.rows_of(markup, which=0)
        links = sources.links_of(markup, which=0)
        if not rows:
            break
        for cells, hrefs in zip(rows, links):
            match = next((_BOARD_NO.search(h) for h in hrefs if _BOARD_NO.search(h)), None)
            if not match:
                continue
            title = cells[1] if len(cells) > 1 else ""
            posts.append({"board_no": match.group(2), "title": title, "month": month_of(title)})
    return posts


def month_of(title):
    """제목에서 대상월을 `YYYY-MM` 으로. 두 자리 연도는 2000년대로 본다."""
    m = _TITLE_MONTH.search(title or "")
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    if year < 100:
        year += 2000
    if not 1 <= month <= 12:
        return None
    return f"{year:04d}-{month:02d}"


def attach_no(board_no):
    """본문에서 첨부 PDF 의 attachNo 를 찾는다. 첨부가 없으면 None."""
    markup = sources.fetch_text(
        VIEW_URL,
        data={
            "boardNo": board_no,
            "boardInfoNo": BOARD_INFO_NO,
            "menuCode": "ys",
            "ps_opendata_id": "113",
        },
        referer=LIST_URL,
    )
    found = _ATTACH_NO.search(markup)
    return found.group(1) if found else None


def download_pdf(no):
    raw = sources.fetch(f"{FILE_URL}?attachNo={no}", referer=VIEW_URL)
    if not raw.startswith(b"%PDF-"):
        raise sources.FetchError(f"attachNo={no}: PDF 가 아님")
    return raw


def parse_pdf(raw, month, board_no):
    """PDF 표에서 집행 내역을 뽑는다.

    표는 `구분 / 일자 / 내역(건수) / 사용처(상호) / 금액 / 대상인원 / 집행방법` 꼴이고,
    `합 계`·`소 계`·분류 머리행이 섞여 있다. 일자 칸이 날짜인 행만 내역으로 본다.

    `(행 목록, PDF 에 적힌 합계, 파싱 합계)` 를 돌려준다. 호출한 쪽에서 합계를 대조한다.
    """
    import io

    import pdfplumber

    rows, stated_total = [], None
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for cells in table:
                    cells = [(c or "").strip() for c in cells]
                    if len(cells) < 7:
                        continue
                    label, date, detail, venue, amount, headcount, method = cells[:7]
                    flat = label.replace(" ", "").replace("\n", "")
                    if flat in ("합계",) and stated_total is None:
                        stated_total = _to_int(amount)
                        continue
                    if not _DATE.match(date):
                        continue
                    value = _to_int(amount)
                    if value is None:
                        continue
                    rows.append(
                        {
                            "대상월": month,
                            "일자": date,
                            "내역": re.sub(r"\s*\n\s*", " ", detail).strip(),
                            "사용처": re.sub(r"\s*\n\s*", " ", venue).strip(),
                            "금액": str(value),
                            "인원": re.sub(r"[^0-9]", "", headcount),
                            "집행방법": method.replace("\n", "").strip(),
                            "게시글": board_no,
                        }
                    )
    parsed_total = sum(int(r["금액"]) for r in rows)
    return rows, stated_total, parsed_total


def _to_int(text):
    cleaned = (text or "").replace(",", "").replace(" ", "").strip()
    if not _AMOUNT.match(cleaned):
        return None
    return int(cleaned)
