#!/usr/bin/env python3
"""ASGI 를 소켓 없이 호출해 엔드포인트와 행 수를 확인한다."""
from __future__ import annotations

from fastapi.testclient import TestClient

from api import FILES, app


def test_all() -> None:
    with TestClient(app) as c:
        health = c.get("/health")
        assert health.status_code == 200, health.text
        body = health.json()
        assert body["status"] == "ok"
        tables = body["tables"]
        assert tables["settlement"] == 2
        assert tables["expense"] == 2533
        assert tables["contracts"] == 3037
        assert tables["execution"] == 12908
        assert tables["police_expense"] == 1203
        assert tables["budget2026"] == 14

        root = c.get("/").json()
        assert "docs" in root

        ds = c.get("/datasets")
        assert ds.status_code == 200
        gaps = ds.json()["police"]["gaps"]
        assert any("2016-02" in g for g in gaps)

        st = c.get("/school/settlement", params={"year": 2025}).json()
        assert st["total"] == 1
        assert st["items"][0]["세출결산액"] == 3331100016

        exp = c.get("/school/expense", params={"limit": 1}).json()
        assert exp["total"] == 2533
        assert exp["sum"] > 0
        assert len(exp["items"]) == 1

        venues = c.get("/school/expense/venues", params={"limit": 5}).json()
        assert venues["venues"] >= 5
        assert venues["items"][0]["count"] >= venues["items"][1]["count"]

        vendors = c.get("/school/contracts/vendors", params={"by": "amount", "limit": 3}).json()
        assert vendors["items"][0]["amount"] >= vendors["items"][1]["amount"]

        periods = c.get("/school/execution/periods").json()
        assert periods["total"] > 40
        first = periods["items"][0]
        exe = c.get("/school/execution", params={"period": first, "limit": 20}).json()
        assert exe["total"] > 0
        assert "budget_sum" in exe

        b26 = c.get("/school/budget2026").json()
        assert b26["unit"] == "천원"
        assert b26["total"] == 14

        police = c.get("/police/expense", params={"from": "2024-01", "to": "2024-12", "limit": 10}).json()
        assert police["total"] > 0
        assert police["sum"] > 0

        months = c.get("/police/expense/months").json()
        assert months["total"] >= 120
        assert "2016-02" not in {i["month"] for i in months["items"]}

        raw = c.get("/tables/expense", params={"limit": 5, "offset": 10}).json()
        assert raw["total"] == 2533
        assert len(raw["items"]) == 5

        missing = c.get("/tables/nope")
        assert missing.status_code == 404

        for name in FILES:
            r = c.get(f"/tables/{name}", params={"limit": 1})
            assert r.status_code == 200, name
            assert r.json()["total"] == tables[name], name


if __name__ == "__main__":
    test_all()
    print("ok")
