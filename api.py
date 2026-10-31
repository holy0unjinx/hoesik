#!/usr/bin/env python3
"""선린인터넷고·용산경찰서 재정공개 데이터 REST API.

수집해 둔 CSV 를 그대로 읽어 JSON 으로 돌려준다. 시작할 때 전부
메모리에 올리므로(약 3MB) 요청마다 파일을 다시 읽지 않는다.

실행:
    uvicorn api:app --host 127.0.0.1 --port 8000
문서:
    /docs            Swagger UI
    /openapi.json    OpenAPI 스키마
nginx 뒤에서 /api 로 붙이면 --root-path /api 를 켠다.
"""
from __future__ import annotations

import csv
import os
import re
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("DATA_DIR", os.path.join(ROOT, "site", "data"))

# 회식·협의회성 집행을 가려내는 기준 (선린 업무추진비)
MEAL = re.compile(r"협의회|회식|간담|만찬|식사|급량|오찬|석식|다과회")
SHOP = re.compile(
    r"마트|쿠팡|네이버파이낸셜|이베이|에스에스지|SSG|지마켓|옥션|프린팅|문고|"
    r"파리바게뜨|베이커리|11번가|인터파크|다이소|편의점|GS25|세븐일레븐"
)

FILES = {
    "settlement": "settlement.csv",
    "revenue": "revenue.csv",
    "spending": "spending.csv",
    "budget_rounds": "budget_rounds.csv",
    "budget2026": "budget2026.csv",
    "fund": "fund.csv",
    "expense": "expense.csv",
    "contracts": "contracts.csv",
    "execution": "execution.csv",
    "police_expense": "ys_expense.csv",
}

INT_COLS = {
    "예산액", "세입결산액", "세출결산액", "세계잉여금", "결산액", "예산액_천원",
    "누계_천원", "이월액", "이자수입", "접수액", "지출", "잔액", "집행금액",
    "계약금액", "지출액", "금액", "인원", "회차",
}
FLOAT_COLS = {"구성비"}

TABLES: dict[str, list[dict[str, Any]]] = {}


def _coerce(col: str, raw: str) -> Any:
    v = raw.strip()
    if col in INT_COLS:
        digits = re.sub(r"[^0-9-]", "", v)
        return int(digits) if digits not in ("", "-") else None
    if col in FLOAT_COLS:
        try:
            return float(v)
        except ValueError:
            return None
    return v


def load() -> None:
    for name, fn in FILES.items():
        path = os.path.join(DATA, fn)
        if not os.path.exists(path):
            TABLES[name] = []
            continue
        with open(path, encoding="utf-8") as fh:
            TABLES[name] = [
                {k: _coerce(k, v or "") for k, v in row.items() if k}
                for row in csv.DictReader(fh)
            ]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    load()
    yield


app = FastAPI(
    title="선린인터넷고·용산경찰서 재정공개 API",
    version="1.1.0",
    lifespan=lifespan,
    description=(
        "서울특별시교육청 열린 서울교육(선린인터넷고 학교회계)과 "
        "서울경찰청 용산경찰서(서장 업무추진비) 공개 자료를 읽기 전용으로 제공합니다. "
        "원본은 각 기관 공시이며 이 API 는 그 사본입니다."
    ),
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"]
)


# ---------- 공통 헬퍼 ----------

def page(rows: list[dict], limit: int, offset: int, amount_key: str | None = None) -> dict:
    out: dict[str, Any] = {"total": len(rows)}
    if amount_key:
        out["sum"] = sum(r.get(amount_key) or 0 for r in rows)
    out["limit"] = limit
    out["offset"] = offset
    out["items"] = rows[offset: offset + limit]
    return out


def in_months(rows: list[dict], col: str, frm: str | None, to: str | None) -> list[dict]:
    if frm:
        rows = [r for r in rows if str(r.get(col, ""))[:7] >= frm]
    if to:
        rows = [r for r in rows if str(r.get(col, ""))[:7] <= to]
    return rows


def search(rows: list[dict], q: str | None, cols: tuple[str, ...]) -> list[dict]:
    if not q:
        return rows
    needle = q.lower()
    return [r for r in rows if needle in " ".join(str(r.get(c, "")) for c in cols).lower()]


def rank(rows: list[dict], key: str, amount: str, merge: bool = False) -> list[dict]:
    by: dict[str, dict[str, Any]] = {}
    for r in rows:
        name = str(r.get(key, "")).strip()
        if not name:
            continue
        if merge:
            name = re.sub(r"(한정식|숙대입구점|\(.*?\)|점)$", "", name).strip() or name
        cur = by.setdefault(name, {"name": name, "count": 0, "amount": 0})
        cur["count"] += 1
        cur["amount"] += r.get(amount) or 0
    return sorted(by.values(), key=lambda d: (-d["count"], -d["amount"]))


# ---------- 메타 ----------

@app.get("/", tags=["meta"], summary="API 안내")
def root() -> dict:
    return {
        "name": "선린인터넷고·용산경찰서 재정공개 API",
        "version": app.version,
        "docs": "docs",
        "health": "health",
        "datasets": "datasets",
    }


@app.get("/health", tags=["meta"], summary="살아 있는지")
def health() -> dict:
    return {
        "status": "ok",
        "today": date.today().isoformat(),
        "data_dir": DATA,
        "tables": {k: len(v) for k, v in TABLES.items()},
    }


@app.get("/datasets", tags=["meta"], summary="데이터셋 목록과 출처")
def datasets() -> dict:
    return {
        "school": {
            "source": "서울특별시교육청 열린 서울교육 재정공개",
            "url": "https://open.sen.go.kr/iframeList4.jsp?oraCode=000&schoolCode=7010536",
            "school_code": "7010536",
            "neis_code": "B100000658",
            "tables": {
                "settlement": {"rows": len(TABLES["settlement"]), "note": "2024·2025 회계연도 결산 총괄"},
                "revenue": {"rows": len(TABLES["revenue"]), "note": "세입 결산 관별"},
                "spending": {"rows": len(TABLES["spending"]), "note": "세출 결산 정책사업별"},
                "budget_rounds": {"rows": len(TABLES["budget_rounds"]), "note": "본예산·추경 회차별, 단위 천원"},
                "budget2026": {"rows": len(TABLES["budget2026"]), "note": "2026 본예산 세입·세출 구성, 단위 천원"},
                "expense": {"rows": len(TABLES["expense"]), "note": "업무추진비 전건 2012-12~2026-08"},
                "contracts": {"rows": len(TABLES["contracts"]), "note": "수의계약 전건 2021-12~2026-09"},
                "execution": {"rows": len(TABLES["execution"]), "note": "세부사업 월별 집행실적"},
                "fund": {"rows": len(TABLES["fund"]), "note": "학교발전기금 결산"},
            },
        },
        "police": {
            "source": "서울경찰청 용산경찰서 서장업무추진비공개",
            "url": "https://www.smpa.go.kr/user/action/psDeclareBoardList.do?ps_opendata_id=113&menuCode=ys",
            "tables": {
                "expense": {"rows": len(TABLES["police_expense"]), "note": "서장 업무추진비 1,203건 2016-01~2026-09"},
            },
            "gaps": [
                "2015-12 이전 게시글 38건은 내역 자체가 공개되지 않음",
                "2016-02 는 첨부가 스캔 이미지라 추출 불가",
                "2016-12, 2017-03, 2017-04, 2023-04, 2024-10 은 월 합계가 PDF 명시 합계와 어긋남",
            ],
        },
    }


# ---------- 학교: 예산·결산 ----------

@app.get("/school/settlement", tags=["school"], summary="학교회계 결산 총괄")
def school_settlement(year: int | None = None) -> dict:
    rows = TABLES["settlement"]
    if year:
        rows = [r for r in rows if str(r["회계연도"]) == str(year)]
    return {"total": len(rows), "items": rows}


@app.get("/school/revenue", tags=["school"], summary="세입 결산 관별")
def school_revenue(year: int | None = None) -> dict:
    rows = TABLES["revenue"]
    if year:
        rows = [r for r in rows if str(r["회계연도"]) == str(year)]
    return page(rows, 200, 0, "결산액")


@app.get("/school/spending", tags=["school"], summary="세출 결산 정책사업별")
def school_spending(year: int | None = None) -> dict:
    rows = TABLES["spending"]
    if year:
        rows = [r for r in rows if str(r["회계연도"]) == str(year)]
    return page(rows, 200, 0, "결산액")


@app.get("/school/budget-rounds", tags=["school"], summary="본예산·추경 회차별 (천원)")
def school_budget_rounds(year: int | None = None) -> dict:
    rows = TABLES["budget_rounds"]
    if year:
        rows = [r for r in rows if str(r["회계연도"]) == str(year)]
    return {"total": len(rows), "unit": "천원", "items": rows}


@app.get("/school/budget2026", tags=["school"], summary="2026 본예산 세입·세출 구성 (천원)")
def school_budget2026() -> dict:
    return {"total": len(TABLES["budget2026"]), "unit": "천원", "items": TABLES["budget2026"]}


@app.get("/school/fund", tags=["school"], summary="학교발전기금 결산")
def school_fund(year: int | None = None) -> dict:
    rows = TABLES["fund"]
    if year:
        rows = [r for r in rows if str(r["회계연도"]) == str(year)]
    return page(rows, 200, 0, "지출")


# ---------- 학교: 업무추진비 ----------

@app.get("/school/expense", tags=["school"], summary="업무추진비 전건")
def school_expense(
    frm: str | None = Query(None, alias="from", pattern=r"^\d{6}$", description="기준월 YYYYMM"),
    to: str | None = Query(None, pattern=r"^\d{6}$", description="기준월 YYYYMM"),
    q: str | None = Query(None, description="장소·목적 검색"),
    kind: Literal["all", "meal", "other"] = "all",
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> dict:
    rows = TABLES["expense"]
    if frm:
        rows = [r for r in rows if str(r["기준월"]) >= frm]
    if to:
        rows = [r for r in rows if str(r["기준월"]) <= to]
    if kind != "all":
        def is_meal(r: dict) -> bool:
            return bool(MEAL.search(str(r["집행목적"]))) and not SHOP.search(str(r["집행장소"]))
        want = kind == "meal"
        rows = [r for r in rows if is_meal(r) is want]
    rows = search(rows, q, ("집행장소", "집행목적"))
    return page(rows, limit, offset, "집행금액")


@app.get("/school/expense/venues", tags=["school"], summary="업무추진비 장소 순위")
def school_venues(
    frm: str | None = Query(None, alias="from", pattern=r"^\d{6}$"),
    to: str | None = Query(None, pattern=r"^\d{6}$"),
    kind: Literal["meal", "all"] = "meal",
    merge: bool = Query(False, description="비슷한 상호를 묶는다"),
    limit: int = Query(20, ge=1, le=1000),
) -> dict:
    rows = TABLES["expense"]
    if frm:
        rows = [r for r in rows if str(r["기준월"]) >= frm]
    if to:
        rows = [r for r in rows if str(r["기준월"]) <= to]
    if kind == "meal":
        rows = [r for r in rows if MEAL.search(str(r["집행목적"])) and not SHOP.search(str(r["집행장소"]))]
    ranked = rank(rows, "집행장소", "집행금액", merge)
    return {
        "basis": kind, "merged": merge, "rows_counted": len(rows),
        "amount": sum(r.get("집행금액") or 0 for r in rows),
        "venues": len(ranked), "items": ranked[:limit],
    }


# ---------- 학교: 수의계약 ----------

@app.get("/school/contracts", tags=["school"], summary="수의계약 전건")
def school_contracts(
    frm: str | None = Query(None, alias="from", pattern=r"^\d{6}$"),
    to: str | None = Query(None, pattern=r"^\d{6}$"),
    q: str | None = Query(None, description="계약명·업체 검색"),
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> dict:
    rows = TABLES["contracts"]
    if frm:
        rows = [r for r in rows if str(r["기준월"]) >= frm]
    if to:
        rows = [r for r in rows if str(r["기준월"]) <= to]
    rows = search(rows, q, ("계약명", "계약업체명"))
    return page(rows, limit, offset, "계약금액")


@app.get("/school/contracts/vendors", tags=["school"], summary="수의계약 업체 순위")
def school_vendors(
    frm: str | None = Query(None, alias="from", pattern=r"^\d{6}$"),
    to: str | None = Query(None, pattern=r"^\d{6}$"),
    by: Literal["amount", "count"] = "amount",
    limit: int = Query(20, ge=1, le=1000),
) -> dict:
    rows = TABLES["contracts"]
    if frm:
        rows = [r for r in rows if str(r["기준월"]) >= frm]
    if to:
        rows = [r for r in rows if str(r["기준월"]) <= to]
    ranked = rank(rows, "계약업체명", "계약금액")
    if by == "amount":
        ranked.sort(key=lambda d: -d["amount"])
    return {"by": by, "rows_counted": len(rows),
            "amount": sum(r.get("계약금액") or 0 for r in rows),
            "vendors": len(ranked), "items": ranked[:limit]}


# ---------- 학교: 집행실적 ----------

@app.get("/school/execution/periods", tags=["school"], summary="집행실적 기준월 목록")
def school_periods() -> dict:
    periods = sorted({str(r["기준월"]) for r in TABLES["execution"]}, reverse=True)
    return {"total": len(periods), "items": periods}


@app.get("/school/execution", tags=["school"], summary="세부사업 집행실적")
def school_execution(
    period: str | None = Query(None, pattern=r"^\d{6}$", description="기준월 YYYYMM"),
    q: str | None = Query(None, description="세부사업·목 검색"),
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> dict:
    rows = TABLES["execution"]
    if period:
        rows = [r for r in rows if str(r["기준월"]) == period]
    rows = search(rows, q, ("세부사업", "목"))
    out = page(rows, limit, offset, "지출액")
    out["budget_sum"] = sum(r.get("예산액") or 0 for r in rows)
    return out


# ---------- 경찰서 ----------

@app.get("/police/expense", tags=["police"], summary="용산경찰서장 업무추진비 전건")
def police_expense(
    frm: str | None = Query(None, alias="from", pattern=r"^\d{4}-\d{2}$", description="대상월 YYYY-MM"),
    to: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    q: str | None = Query(None, description="사용처·내역 검색"),
    method: str | None = Query(None, description="집행방법 (카드사용 등)"),
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> dict:
    rows = in_months(TABLES["police_expense"], "대상월", frm, to)
    if method:
        rows = [r for r in rows if str(r.get("집행방법", "")) == method]
    rows = search(rows, q, ("사용처", "내역"))
    return page(rows, limit, offset, "금액")


@app.get("/police/expense/venues", tags=["police"], summary="사용처 순위")
def police_venues(
    frm: str | None = Query(None, alias="from", pattern=r"^\d{4}-\d{2}$"),
    to: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    by: Literal["count", "amount"] = "count",
    limit: int = Query(20, ge=1, le=1000),
) -> dict:
    rows = in_months(TABLES["police_expense"], "대상월", frm, to)
    ranked = rank(rows, "사용처", "금액")
    if by == "amount":
        ranked.sort(key=lambda d: -d["amount"])
    return {"by": by, "rows_counted": len(rows),
            "amount": sum(r.get("금액") or 0 for r in rows),
            "venues": len(ranked), "items": ranked[:limit]}


@app.get("/police/expense/months", tags=["police"], summary="월별 집행 합계")
def police_months() -> dict:
    agg: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "amount": 0})
    for r in TABLES["police_expense"]:
        cur = agg[str(r["대상월"])]
        cur["count"] += 1
        cur["amount"] += r.get("금액") or 0
    items = [{"month": k, **v} for k, v in sorted(agg.items())]
    return {"total": len(items),
            "amount": sum(i["amount"] for i in items),
            "items": items}


# ---------- 공통 조회 ----------

@app.get("/tables/{name}", tags=["meta"], summary="원본 표 그대로")
def raw_table(name: str, limit: int = Query(100, ge=1, le=20000), offset: int = Query(0, ge=0)) -> dict:
    if name not in TABLES:
        raise HTTPException(404, f"unknown table: {name}. see /datasets")
    return page(TABLES[name], limit, offset)
