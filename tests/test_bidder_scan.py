"""Yüklenici bazlı sonuç tarama orkestrasyonu testleri.

search_tenders / get_tender_announcements sahte (stub) ile değiştirilir;
bu testler ağ erişimi gerektirmez.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ihale_client import EKAPClient

FIXTURES = Path(__file__).parent / "fixtures"


def make_client(tenders, announcements_by_id, total_count=None):
    """Ağ katmanı sahteyle değiştirilmiş bir istemci döndürür."""
    client = EKAPClient()

    async def fake_search(**kwargs):
        limit = kwargs.get("limit", 10)
        skip = kwargs.get("skip", 0)
        return {
            "tenders": tenders[skip:skip + limit],
            "total_count": total_count if total_count is not None else len(tenders),
        }

    async def fake_announcements(tender_id):
        return {"announcements": announcements_by_id.get(tender_id, [])}

    client.search_tenders = fake_search
    client.get_tender_announcements = fake_announcements
    return client


def result_announcement(fixture_name):
    return {
        "type": {"code": "4", "description": "Sonuç İlanı"},
        "markdown_content": (FIXTURES / fixture_name).read_text(encoding="utf-8"),
    }


TENDER = {
    "id": "abc123",
    "ikn": "2026/1359939",
    "name": "TEST İHALESİ",
    "authority": "TEST İDARESİ",
    "province": "ANKARA",
    "tender_datetime": "01.07.2026 10:00",
}


@pytest.mark.asyncio
async def test_rejects_call_without_any_scope_filter():
    client = make_client([TENDER], {})
    result = await client.search_tender_results_by_bidder(bidder_name="ALMET")

    assert result.get("error")
    assert "kapsam" in result["message"].lower()


@pytest.mark.asyncio
async def test_rejects_empty_bidder_name():
    client = make_client([TENDER], {})
    result = await client.search_tender_results_by_bidder(
        bidder_name="   ", provinces=[6]
    )

    assert result.get("error")


@pytest.mark.asyncio
async def test_rejects_scope_larger_than_budget_instead_of_truncating():
    client = make_client([TENDER], {}, total_count=4200)
    result = await client.search_tender_results_by_bidder(
        bidder_name="ALMET", provinces=[6], max_tenders=500
    )

    assert result.get("error")
    # Kullanıcı gerçek büyüklüğü görmeli, sessizce kesilmemeli.
    assert "4200" in result["message"]
    assert "500" in result["message"]


@pytest.mark.asyncio
async def test_finds_winner_with_normalized_partial_name():
    client = make_client(
        [TENDER], {"abc123": [result_announcement("mal_2026-1359939_0.md")]}
    )
    result = await client.search_tender_results_by_bidder(
        bidder_name="almet tedarik", provinces=[6]
    )

    assert result["match_count"] == 1
    assert result["scanned_tenders"] == 1
    match = result["matches"][0]
    assert match["winner"] == "ALMET TEDARİK ORGANİZASYON TİCARET LİMİTED ŞİRKETİ"
    assert match["contract_amount"] == 8500000.00
    assert match["ikn"] == "2026/1359939"


@pytest.mark.asyncio
async def test_non_matching_bidder_returns_no_matches_but_reports_scan_size():
    client = make_client(
        [TENDER], {"abc123": [result_announcement("mal_2026-1359939_0.md")]}
    )
    result = await client.search_tender_results_by_bidder(
        bidder_name="BASKA FIRMA", provinces=[6]
    )

    assert result["match_count"] == 0
    assert result["scanned_tenders"] == 1
    assert result["matches"] == []


@pytest.mark.asyncio
async def test_partial_lots_produce_one_match_per_announcement():
    tender = {**TENDER, "id": "lot1", "ikn": "2026/729693"}
    client = make_client(
        [tender],
        {
            "lot1": [
                result_announcement("kismi_2026-729693_0.md"),
                result_announcement("kismi_2026-729693_1.md"),
                result_announcement("kismi_2026-729693_2.md"),
            ]
        },
    )
    result = await client.search_tender_results_by_bidder(
        bidder_name="İKRAMTUR", provinces=[34]
    )

    assert result["match_count"] == 3
    assert result["scanned_tenders"] == 1
    assert [m["announcement_index"] for m in result["matches"]] == [0, 1, 2]
    amounts = sorted(m["contract_amount"] for m in result["matches"])
    assert amounts == [8313805.64, 8713601.52, 10034893.28]


@pytest.mark.asyncio
async def test_ignores_non_result_announcements():
    tender = {**TENDER, "id": "mixed"}
    client = make_client(
        [tender],
        {
            "mixed": [
                {"type": {"code": "2", "description": "İhale İlanı"},
                 "markdown_content": "İHALE İLANI ALMET TEDARİK"},
                result_announcement("mal_2026-1359939_0.md"),
            ]
        },
    )
    result = await client.search_tender_results_by_bidder(
        bidder_name="ALMET", provinces=[6]
    )

    # İhale ilanında ad geçse bile yalnızca sonuç ilanı sayılmalı.
    assert result["match_count"] == 1
    assert result["matches"][0]["announcement_index"] == 0


@pytest.mark.asyncio
async def test_result_states_it_is_a_scan_not_an_index():
    client = make_client(
        [TENDER], {"abc123": [result_announcement("mal_2026-1359939_0.md")]}
    )
    result = await client.search_tender_results_by_bidder(
        bidder_name="ALMET", provinces=[6]
    )

    assert "tarama" in result["note"].lower()
    assert result["scope"]["provinces"] == [6]


@pytest.mark.asyncio
async def test_mcp_tool_converts_plate_numbers_to_ekap_province_ids(monkeypatch):
    """MCP katmanı plaka kodunu EKAP il ID'sine çevirmeli.

    EKAP il ID'leri 245-325 aralığında (ADANA=245, alfabetik); plaka kodu
    doğrudan gönderilirse sorgu sessizce 0 sonuç döner.
    """
    import ihale_mcp

    captured = {}

    async def spy(**kwargs):
        captured.update(kwargs)
        return {"matches": [], "match_count": 0, "scanned_tenders": 0}

    monkeypatch.setattr(
        ihale_mcp.ekap_client, "search_tender_results_by_bidder", spy
    )

    await ihale_mcp.search_tender_results_by_bidder.fn(
        bidder_name="ACME", provinces=[31]  # Hatay
    )

    assert captured["provinces"] == [281], "plaka 31 (HATAY) -> EKAP ID 281 bekleniyordu"
