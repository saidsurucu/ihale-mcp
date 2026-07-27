"""Sonuç ilanı ayrıştırıcısı ve firma adı normalizasyonu testleri.

Fixture'lar EKAP'tan 2026-07-27'de indirilen gerçek sonuç ilanlarıdır.
Bu testler ağ erişimi gerektirmez.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ihale_client import normalize_company_name, parse_result_announcement

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


# --- normalize_company_name ---------------------------------------------


def test_normalize_folds_turkish_characters():
    assert normalize_company_name("İNŞAAT ÇĞÖŞÜ") == "INSAAT CGOSU"


def test_normalize_strips_legal_suffixes():
    full = "DURAK GRUP YAPI İNŞAAT EMLAK TEKSTİL SANAYİ VE TİCARET LİMİTED ŞİRKETİ"
    assert normalize_company_name(full) == "DURAK GRUP YAPI INSAAT EMLAK TEKSTIL"


def test_normalize_handles_abbreviated_suffixes():
    assert normalize_company_name("ACME LTD. ŞTİ.") == "ACME"
    assert normalize_company_name("ACME A.Ş.") == "ACME"
    assert normalize_company_name("ACME SAN. TİC. A.Ş.") == "ACME"


def test_normalize_collapses_whitespace_and_punctuation():
    assert normalize_company_name("  ACME   GRUP,  ") == "ACME GRUP"


def test_normalize_is_idempotent():
    once = normalize_company_name("ACME SANAYİ VE TİCARET LİMİTED ŞİRKETİ")
    assert normalize_company_name(once) == once


def test_normalize_handles_empty_and_none():
    assert normalize_company_name("") == ""
    assert normalize_company_name(None) == ""


def test_normalize_does_not_strip_suffix_words_inside_name():
    # "TİCARET" burada firmanin ayirt edici adinin parcasi degil, ekidir; ama
    # "SANAYICILER" gibi ekle baslayan kelimeler korunmali.
    assert "SANAYICILER" in normalize_company_name("SANAYICILER BIRLIGI LTD ŞTİ")


# --- parse_result_announcement: temel alanlar ----------------------------


def test_parses_winner_with_yuklenici_label():
    result = parse_result_announcement(load("yapim_2026-1309463_0.md"))
    assert result["winner"] == "MEHMET NURİ ÇELİKYAY"


def test_parses_winner_with_yuklenicisi_label():
    # Yapim ihalelerinde etiket "Yüklenicisi" olarak geciyor.
    result = parse_result_announcement(load("yapim_2026-1300262_0.md"))
    assert result["winner"] == "MEHMET ÇAKIR HAFRİYAT NAKLİYE İNŞAAT VE TİCARET LİMİTED ŞİRKETİ"


def test_parses_amounts_as_floats():
    result = parse_result_announcement(load("mal_2026-1359939_0.md"))
    assert result["contract_amount"] == 8500000.00
    assert result["estimated_cost"] == 9798166.67
    assert result["currency"] == "TRY"


def test_parses_bid_counts_as_ints():
    result = parse_result_announcement(load("yapim_2026-1300262_0.md"))
    assert result["bid_count"] == 1
    assert result["valid_bid_count"] == 1


def test_parses_ikn_and_dates():
    result = parse_result_announcement(load("hizmet_2026-1373608_0.md"))
    assert result["ikn"] == "2026/1373608"
    assert result["contract_date"] == "23.07.2026"


def test_parses_winner_address_and_nationality():
    result = parse_result_announcement(load("yapim_2026-1300262_0.md"))
    assert result["winner_nationality"] == "Türkiye"
    assert "YAYLADAĞI" in result["winner_address"]


# --- parse_result_announcement: kenar durumlar ---------------------------


def test_strips_trailing_html_comment_artifact():
    # Bu fixture'da yaklasik maliyet degeri "5.169.417,32 TRY -->" seklinde geliyor.
    result = parse_result_announcement(load("yapim_2026-1300262_0.md"))
    assert result["estimated_cost"] == 5169417.32


def test_takes_first_estimated_cost_when_repeated():
    # Kismi teklifli ilanda "Yaklasik Maliyeti" iki kez geciyor
    # (ikincisi "Sozlesmeye Esas Kisimlarinin Yaklasik Maliyeti").
    result = parse_result_announcement(load("kismi_2026-729693_0.md"))
    assert result["estimated_cost"] == 27172470.53


def test_partial_lot_announcements_share_winner_but_differ_in_amount():
    lot0 = parse_result_announcement(load("kismi_2026-729693_0.md"))
    lot1 = parse_result_announcement(load("kismi_2026-729693_1.md"))
    lot2 = parse_result_announcement(load("kismi_2026-729693_2.md"))

    assert lot0["winner"] == lot1["winner"] == lot2["winner"]
    assert lot0["contract_amount"] == 8313805.64
    assert lot1["contract_amount"] == 10034893.28
    assert lot2["contract_amount"] == 8713601.52


def test_missing_fields_return_none_not_guesses():
    minimal = "**SONUÇ İLANI**\n\nKamuoyuna saygıyla duyurulur."
    result = parse_result_announcement(minimal)
    assert result["winner"] is None
    assert result["contract_amount"] is None
    assert result["bid_count"] is None


def test_empty_input_returns_all_none():
    result = parse_result_announcement("")
    assert result["winner"] is None
    assert all(v is None for k, v in result.items() if k != "currency")


def test_none_input_does_not_raise():
    result = parse_result_announcement(None)
    assert result["winner"] is None


@pytest.mark.parametrize(
    "fixture",
    [
        "hizmet_2026-1343415_0.md",
        "hizmet_2026-1373608_0.md",
        "kismi_2026-729693_0.md",
        "mal_2026-1351626_0.md",
        "mal_2026-1359939_0.md",
        "yapim_2026-1300262_0.md",
        "yapim_2026-1309463_0.md",
    ],
)
def test_every_real_fixture_yields_winner_and_amount(fixture):
    """Gercek ilanlarin tamaminda kazanan ve sozlesme bedeli cikarilabilmeli."""
    result = parse_result_announcement(load(fixture))
    assert result["winner"], f"{fixture}: kazanan cikarilamadi"
    assert result["contract_amount"] is not None, f"{fixture}: bedel cikarilamadi"
    assert result["contract_amount"] > 0
