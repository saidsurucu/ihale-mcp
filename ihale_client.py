#!/usr/bin/env python3
"""
EKAP v2 API client for Turkish government tender/procurement data - FIXED VERSION
"""

import asyncio
import httpx
import re
import ssl
import os
import uuid
import base64
import time
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as crypto_padding
from typing import Dict, Any, Optional, List, Literal
from datetime import datetime
from io import BytesIO
from markitdown import MarkItDown
from ihale_models import (
    DIRECT_PROCUREMENT_TYPES,
    DIRECT_PROCUREMENT_STATUSES,
    DIRECT_PROCUREMENT_SCOPES,
    NAME_TO_PLATE,
    DIRECT_PROCUREMENT_STATUS_ALIASES,
    DIRECT_PROCUREMENT_SCOPE_ALIASES,
)

# Sonuç ilanı ayrıştırma yardımcıları
#
# EKAP'ın arama indeksi sonuç ilanlarını kapsamadığı ve ilan listesindeki
# "istekliAdi" alanı her zaman boş geldiği için kazanan/bedel bilgisi yalnızca
# sonuç ilanı metninden çıkarılabiliyor.

_TR_FOLD = str.maketrans({
    "Ç": "C", "Ğ": "G", "İ": "I", "I": "I", "Ö": "O", "Ş": "S", "Ü": "U",
    "ç": "C", "ğ": "G", "ı": "I", "i": "I", "ö": "O", "ş": "S", "ü": "U",
})

# Ticaret ünvanı ekleri. Firmanın ayırt edici adına katkı vermedikleri için
# eşleştirmeden önce atılır.
_LEGAL_SUFFIX_TOKENS = {
    "LIMITED", "LTD", "SIRKETI", "SIRKET", "STI", "ANONIM", "AS", "A", "S",
    "SANAYI", "SAN", "TICARET", "TIC", "VE", "KOLLEKTIF", "KOMANDIT",
}


def normalize_company_name(name: Optional[str]) -> str:
    """Firma adını karşılaştırılabilir tek biçime indirger.

    Büyük harfe çevirir, Türkçe karakterleri katlar, noktalamayı temizler ve
    ticaret ünvanı eklerini atar. Aynı firmanın "LTD. ŞTİ." / "LİMİTED ŞİRKETİ"
    gibi farklı yazımlarının eşleşmesini sağlar.
    """
    if not name:
        return ""

    folded = name.translate(_TR_FOLD).upper()
    # Noktalamayı boşluğa çevir; harf ve rakamları koru.
    cleaned = re.sub(r"[^0-9A-Z]+", " ", folded)

    kept = [tok for tok in cleaned.split() if tok not in _LEGAL_SUFFIX_TOKENS]
    return " ".join(kept)


def _clean_cell(value: Optional[str]) -> Optional[str]:
    """Markdown tablo hücresini temizler.

    EKAP'ın HTML'inde kalan yorum artıkları ("--> ") ve kalın işaretleri
    ayıklar. Değer boşsa None döner.
    """
    if value is None:
        return None
    text = value.replace("-->", " ").replace("**", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _find_field(markdown: str, label_pattern: str) -> Optional[str]:
    """Sonuç ilanı tablosundan bir alanın değerini döndürür.

    Satırlar `| **a)** Etiket | : | Değer |` biçiminde; ayırıcı bazı satırlarda
    `**:**` olarak kalın geliyor. Birden çok eşleşme varsa ilki döner (kısmi
    teklifli ilanlarda "Yaklaşık Maliyeti" iki kez geçiyor; ilki ihalenin
    tamamına ait olan).
    """
    if not markdown:
        return None
    match = re.search(
        rf"{label_pattern}\s*\**\s*\|\s*\**:\**\s*\|([^|\n]*)",
        markdown,
        re.IGNORECASE,
    )
    return _clean_cell(match.group(1)) if match else None


def _parse_amount(value: Optional[str]) -> Optional[float]:
    """Türkçe biçimli parasal değeri float'a çevirir ("8.500.000,00 TRY")."""
    if not value:
        return None
    match = re.search(r"([\d.]+,\d+|\d+)", value)
    if not match:
        return None
    number = match.group(1).replace(".", "").replace(",", ".")
    try:
        return float(number)
    except ValueError:
        return None


def _parse_int(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else None


def parse_result_announcement(markdown: Optional[str]) -> Dict[str, Any]:
    """Sonuç İlanı markdown'ından yapılandırılmış alanlar çıkarır.

    Bulunamayan alanlar None döner; tahmin yapılmaz.
    """
    md = markdown or ""

    amount_raw = _find_field(md, r"Bedeli")
    currency = None
    if amount_raw:
        currency_match = re.search(r"\b([A-Z]{3})\b", amount_raw)
        currency = currency_match.group(1) if currency_match else None

    return {
        "ikn": _find_field(md, r"İhale kayıt numarası"),
        # Yapım ihalelerinde etiket "Yüklenicisi", diğerlerinde "Yüklenici".
        "winner": _find_field(md, r"Yüklenici(?:si)?"),
        "winner_nationality": _find_field(md, r"Yüklenicinin uyruğu"),
        "winner_address": _find_field(md, r"Yüklenicinin adresi"),
        "contract_amount": _parse_amount(amount_raw),
        "currency": currency,
        "contract_date": _find_field(md, r"4- Sözleşmenin[\s\S]{0,200}?Tarihi"),
        "contract_duration": _find_field(md, r"4- Sözleşmenin[\s\S]{0,400}?Süresi"),
        "estimated_cost": _parse_amount(_find_field(md, r"(?<!Kısımlarının )Yaklaşık Maliyeti")),
        "bid_count": _parse_int(_find_field(md, r"Toplam Teklif Sayısı")),
        "valid_bid_count": _parse_int(_find_field(md, r"Toplam Geçerli Teklif Sayısı")),
    }


class EKAPClient:
    """Client for EKAP v2 API"""
    
    def __init__(self):
        self.base_url = "https://ekapv2.kik.gov.tr"
        self.tender_endpoint = "/b_ihalearama/api/Ihale/GetListByParameters"
        self.okas_endpoint = "/b_ihalearama/api/IhtiyacKalemleri/GetAll"
        self.authority_endpoint = "/b_idare/api/DetsisKurumBirim/DetsisAgaci"
        self.announcements_endpoint = "/b_ihalearama/api/Ilan/GetList"
        self.tender_details_endpoint = "/b_ihalearama/api/IhaleDetay/GetByIhaleIdIhaleDetay"
        self.document_url_endpoint = "/b_ihalearama/api/EkapDokumanYonlendirme/GetDokumanUrl"
        # Direct Procurement (Doğrudan Temin) legacy endpoint (GET)
        self.direct_procurement_url = "https://ekap.kik.gov.tr/EKAP/Ortak/YeniIhaleAramaData.ashx"
        
        # AES key for request signing (from EKAP frontend environment config).
        # EKAP bu anahtarı ve başlık adlarını düzenli olarak değiştiriyor
        # (Ağustos 2025'te iki kez değişti). Yeni anahtarı bulmak için:
        # ekapv2.kik.gov.tr/ekap/search sayfası konsolunda
        #   window.webpackChunkshell.push([[Symbol('p')],{},(r)=>{
        #     for(const k in (r.c||{})){const e=r.c[k]?.exports;
        #       if(e?.environment?.r8fact) console.log(e.environment.r8fact);}}]);
        # Güncel anahtar (26 Ağustos 2025): 32 bayt → AES-256 (öncesi 24 bayt/AES-192)
        self._r8fact_key = b'pfS7Xdn3YVkOzs3V79XUc91SD47mQD0g'

        # Common headers for all requests
        self.headers = {
            'Accept': 'application/json',
            'Accept-Language': 'tr',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Origin': 'https://ekapv2.kik.gov.tr',
            'Referer': 'https://ekapv2.kik.gov.tr/ekap/search',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
            'api-version': 'v1',
            'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"'
        }
        
    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context that supports older protocols"""
        ssl_context = ssl.create_default_context()
        ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context

    def _aes_cbc_encrypt(self, plaintext: str, key: bytes, iv: bytes) -> bytes:
        """Encrypt plaintext with AES-CBC and PKCS7 padding."""
        padder = crypto_padding.PKCS7(128).padder()
        padded = padder.update(plaintext.encode()) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        enc = cipher.encryptor()
        return enc.update(padded) + enc.finalize()

    def _generate_security_headers(self) -> Dict[str, str]:
        """Generate AES-signed security headers required by EKAP v2 API."""
        guid = str(uuid.uuid4())
        iv = os.urandom(16)
        ts_ms = str(int(time.time() * 1000))

        r8id = base64.b64encode(self._aes_cbc_encrypt(guid, self._r8fact_key, iv)).decode()
        ts_enc = base64.b64encode(self._aes_cbc_encrypt(ts_ms, self._r8fact_key, iv)).decode()
        siv = base64.b64encode(iv).decode()

        # Başlık adları da anahtarla birlikte değişiyor; güncel şema
        # (26 Ağustos 2025): X-Ekap-Sec-1..4. Tarayıcı 5 ve 6'yı da gönderiyor
        # ama ilk dört olmadan 401, yalnız ilk dörtle 200 dönüyor.
        # Başlık adlarını doğrulamak için: DevTools → Network →
        # GetListByParameters → Request Headers.
        return {
            'X-Ekap-Sec-1': r8id,    # AES(guid)
            'X-Ekap-Sec-2': siv,     # IV (base64)
            'X-Ekap-Sec-3': guid,    # düz guid
            'X-Ekap-Sec-4': ts_enc,  # AES(ts_ms)
        }

    async def _make_request(self, endpoint: str, params: dict) -> dict:
        """Make an API request to EKAP v2"""
        ssl_context = self._create_ssl_context()
        request_headers = {**self.headers, **self._generate_security_headers()}

        async with httpx.AsyncClient(
            timeout=30.0,
            verify=ssl_context,
            http2=False,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        ) as client:
            response = await client.post(
                f"{self.base_url}{endpoint}",
                json=params,
                headers=request_headers
            )
            response.raise_for_status()
            return response.json()
    
    def _format_date_for_api(self, date_str: Optional[str]) -> Optional[str]:
        """Validate and return date in YYYY-MM-DD format expected by API"""
        if not date_str:
            return None
        try:
            # Validate the date format
            datetime.strptime(date_str, "%Y-%m-%d")
            return date_str  # API expects YYYY-MM-DD format
        except ValueError:
            return None

    async def _make_get_request_full_url(
        self,
        url: str,
        params: dict,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Any] = None,
    ) -> dict:
        """Make a GET request to a full URL (used for legacy EKAP endpoints).

        cookies: can be a cookie header string or a dict suitable for httpx.
        """
        ssl_context = self._create_ssl_context()
        req_headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Encoding': 'identity',
            'Connection': 'keep-alive',
            'Referer': 'https://ekap.kik.gov.tr/EKAP/YeniIhaleArama.aspx',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"'
        }
        if headers:
            req_headers.update(headers)
        async with httpx.AsyncClient(
            timeout=30.0,
            verify=ssl_context,
            http2=False,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        ) as client:
            # If cookies is a string, set Cookie header; if dict, pass to client
            request_headers = dict(req_headers)
            httpx_cookies = None
            if isinstance(cookies, str) and cookies.strip():
                request_headers['Cookie'] = cookies
            elif isinstance(cookies, dict):
                httpx_cookies = cookies
            # First attempt
            response = await client.get(url, params=params, headers=request_headers, cookies=httpx_cookies, follow_redirects=False)
            # If redirected to error page, try warming up to obtain cookies and retry once
            if response.status_code == 302 and '/EKAP/error_page.html' in response.headers.get('location', '') and not cookies:
                await self._warmup_legacy_ekap(client)
                response = await client.get(url, params=params, headers=req_headers, follow_redirects=False)
            response.raise_for_status()
            return response.json()

    async def _warmup_legacy_ekap(self, client: httpx.AsyncClient) -> None:
        """Warm-up request to EKAP legacy page to obtain session cookies."""
        try:
            await client.get(
                'https://ekap.kik.gov.tr/EKAP/YeniIhaleArama.aspx',
                headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
                    'Connection': 'keep-alive',
                },
                follow_redirects=True,
            )
        except Exception:
            pass
        
        # Try authority search page as alternative warm-up
        try:
            await client.get(
                'https://ekap.kik.gov.tr/EKAP/Ortak/YeniIhaleAramaData.ashx',
                params={"metot": "idareAra", "aranan": "a"},
                headers={
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'tr-TR,tr;q=0.9',
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
                    'Connection': 'keep-alive',
                },
                follow_redirects=True,
            )
        except Exception:
            pass

    async def search_direct_procurement_authorities(
        self,
        search_term: str,
        cookies: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Search authorities for Direct Procurement filter (legacy idareAra).

        Returns list of { token, name } where token is the encrypted idareId (A) and name is D.
        """
        params = {
            "metot": "idareAra",
            "aranan": search_term or "",
            "ES": "",
            "ihaleidListesi": "",
        }
        try:
            data = await self._make_get_request_full_url(
                self.direct_procurement_url,
                params=params,
                cookies=cookies,
            )
            items = data.get("idareAramaResultList", [])
            results = []
            for it in items:
                results.append({
                    "token": it.get("A"),
                    "name": it.get("D"),
                })
            return {
                "authorities": results,
                "returned_count": len(results),
                "search_term": search_term,
            }
        except httpx.HTTPStatusError as e:
            return {
                "error": f"Authority search failed with status {e.response.status_code}",
                "message": str(e)
            }
        except Exception as e:
            return {
                "error": "Authority search failed",
                "message": str(e)
            }

    async def search_direct_procurement_parent_authorities(
        self,
        search_term: str,
        cookies: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Search parent authorities (üst idare) for Direct Procurement (ustIdareAra).

        Returns list of { token, name } where token is the code used as 'ustIdareKod' (e.g., '44|07').
        """
        params = {
            "metot": "ustIdareAra",
            "aranan": search_term or "",
            "ES": "",
            "ihaleidListesi": "",
        }
        try:
            data = await self._make_get_request_full_url(
                self.direct_procurement_url,
                params=params,
                cookies=cookies,
            )
            items = data.get("ustIdareAramaResultList", [])
            results = []
            for it in items:
                results.append({
                    "token": it.get("A"),
                    "name": it.get("D"),
                })
            return {
                "parent_authorities": results,
                "returned_count": len(results),
                "search_term": search_term,
            }
        except httpx.HTTPStatusError as e:
            return {
                "error": f"Parent authority search failed with status {e.response.status_code}",
                "message": str(e)
            }
        except Exception as e:
            return {
                "error": "Parent authority search failed",
                "message": str(e)
            }
    
    async def search_tenders(
        self,
        search_text: str = "",
        ikn_year: Optional[int] = None,
        ikn_number: Optional[int] = None,
        tender_types: List[int] = None,
        tender_date_start: Optional[str] = None,
        tender_date_end: Optional[str] = None,
        announcement_date_start: Optional[str] = None,
        announcement_date_end: Optional[str] = None,
        search_type: Literal["GirdigimGibi", "TumKelimeler"] = "GirdigimGibi",
        order_by: Literal["ihaleTarihi", "ihaleAdi", "idareAdi"] = "ihaleTarihi",
        sort_order: Literal["asc", "desc"] = "desc",
        # Boolean filters
        e_ihale: Optional[bool] = None,
        e_eksiltme_yapilacak_mi: Optional[bool] = None,
        ortak_alim_mi: Optional[bool] = None,
        kismi_teklif_mi: Optional[bool] = None,
        fiyat_disi_unsur_varmi: Optional[bool] = None,
        ekonomik_mali_yeterlilik_belgeleri_isteniyor_mu: Optional[bool] = None,
        mesleki_teknik_yeterlilik_belgeleri_isteniyor_mu: Optional[bool] = None,
        is_deneyimi_gosteren_belgeler_isteniyor_mu: Optional[bool] = None,
        yerli_istekliye_fiyat_avantaji_uygulaniyor_mu: Optional[bool] = None,
        yabanci_isteklilere_izin_veriliyor_mu: Optional[bool] = None,
        alternatif_teklif_verilebilir_mi: Optional[bool] = None,
        konsorsiyum_katilabilir_mi: Optional[bool] = None,
        alt_yuklenici_calistirilabilir_mi: Optional[bool] = None,
        fiyat_farki_verilecek_mi: Optional[bool] = None,
        avans_verilecek_mi: Optional[bool] = None,
        cerceve_anlasmasi_mi: Optional[bool] = None,
        personel_calistirilmasina_dayali_mi: Optional[bool] = None,
        # List filters
        provinces: List[int] = None,
        tender_statuses: List[int] = None,
        tender_methods: List[int] = None,
        tender_sub_methods: List[int] = None,
        okas_codes: List[str] = None,
        okas_names: List[str] = None,
        authority_ids: List[int] = None,
        proposal_types: List[int] = None,
        announcement_types: List[int] = None,
        # Search scope parameters
        search_in_ikn: bool = True,
        search_in_title: bool = True,
        search_in_announcement: bool = True,
        search_in_tech_spec: bool = True,
        search_in_admin_spec: bool = True,
        search_in_similar_work: bool = True,
        search_in_location: bool = True,
        search_in_nature_quantity: bool = True,
        search_in_tender_info: bool = True,
        search_in_contract_draft: bool = True,
        search_in_bid_form: bool = True,
        skip: int = 0,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Search for Turkish government tenders"""
        
        
        # Province filtering is now handled by the API directly
        
        # Build API request payload
        api_params = {
            "searchText": search_text,
            "filterType": None,
            "ikNdeAra": search_in_ikn,
            "ihaleAdindaAra": search_in_title,
            "ihaleIlanindaAra": search_in_announcement,
            "teknikSartnamedeAra": search_in_tech_spec,
            "idariSartnamedeAra": search_in_admin_spec,
            "benzerIsMaddesindeAra": search_in_similar_work,
            "isinYapilacagiYerMaddesindeAra": search_in_location,
            "nitelikTurMiktarMaddesindeAra": search_in_nature_quantity,
            "ihaleBilgilerindeAra": search_in_tender_info,
            "sozlesmeTasarisindaAra": search_in_contract_draft,
            "teklifCetvelindeAra": search_in_bid_form,
            "searchType": search_type,
            "iknYili": ikn_year,
            "iknSayi": ikn_number,
            "ihaleTarihSaatBaslangic": self._format_date_for_api(tender_date_start),
            "ihaleTarihSaatBitis": self._format_date_for_api(tender_date_end),
            "ilanTarihSaatBaslangic": self._format_date_for_api(announcement_date_start),
            "ilanTarihSaatBitis": self._format_date_for_api(announcement_date_end),
            "yasaKapsami4734List": [],
            "ihaleTuruIdList": tender_types or [],
            "ihaleUsulIdList": tender_methods or [],
            "ihaleUsulAltIdList": tender_sub_methods or [],
            "ihaleIlIdList": provinces or [],
            "ihaleDurumIdList": tender_statuses or [],
            "idareIdList": authority_ids or [],
            "ihaleIlanTuruIdList": announcement_types or [],
            "teklifTuruIdList": proposal_types or [],
            "asiriDusukTeklifIdList": [],
            "istisnaMaddeIdList": [],
            "okasBransKodList": okas_codes or [],
            "okasBransAdiList": okas_names or [],
            "titubbKodList": [],
            "gmdnKodList": [],
            # Boolean filters
            "eIhale": e_ihale,
            "eEksiltmeYapilacakMi": e_eksiltme_yapilacak_mi,
            "ortakAlimMi": ortak_alim_mi,
            "kismiTeklifMi": kismi_teklif_mi,
            "fiyatDisiUnsurVarmi": fiyat_disi_unsur_varmi,
            "ekonomikVeMaliYeterlilikBelgeleriIsteniyorMu": ekonomik_mali_yeterlilik_belgeleri_isteniyor_mu,
            "meslekiTeknikYeterlilikBelgeleriIsteniyorMu": mesleki_teknik_yeterlilik_belgeleri_isteniyor_mu,
            "isDeneyimiGosterenBelgelerIsteniyorMu": is_deneyimi_gosteren_belgeler_isteniyor_mu,
            "yerliIstekliyeFiyatAvantajiUgulaniyorMu": yerli_istekliye_fiyat_avantaji_uygulaniyor_mu,
            "yabanciIsteklilereIzinVeriliyorMu": yabanci_isteklilere_izin_veriliyor_mu,
            "alternatifTeklifVerilebilirMi": alternatif_teklif_verilebilir_mi,
            "konsorsiyumKatilabilirMi": konsorsiyum_katilabilir_mi,
            "altYukleniciCalistirilabilirMi": alt_yuklenici_calistirilabilir_mi,
            "fiyatFarkiVerilecekMi": fiyat_farki_verilecek_mi,
            "avansVerilecekMi": avans_verilecek_mi,
            "cerceveAnlasmaMi": cerceve_anlasmasi_mi,
            "personelCalistirilmasinaDayaliMi": personel_calistirilmasina_dayali_mi,
            "orderBy": order_by,
            "siralamaTipi": sort_order,
            "paginationSkip": skip,
            "paginationTake": limit
        }
        
        try:
            # Make API request
            response_data = await self._make_request(self.tender_endpoint, api_params)
            
            
            # Parse and format the response
            tenders = response_data.get("list", [])
            total_count = response_data.get("totalCount", 0)
            
            # Province filtering is now handled by the API directly
            
            # Format each tender for better readability  
            formatted_tenders = []
            for tender in tenders:
                tender_id = tender.get("id")
                
                # Get document URL for this tender
                document_url = None
                if tender_id and tender.get("dokumanSayisi", 0) > 0:
                    try:
                        doc_result = await self.get_tender_document_url(tender_id)
                        if doc_result.get("success"):
                            document_url = doc_result.get("document_url")
                    except Exception:
                        # If document URL fails, continue without it
                        pass
                
                formatted_tender = {
                    "id": tender_id,
                    "name": tender.get("ihaleAdi"),
                    "ikn": tender.get("ikn"),
                    "type": {
                        "code": tender.get("ihaleTip"),
                        "description": tender.get("ihaleTipAciklama")
                    },
                    "method": tender.get("ihaleUsulAciklama"),
                    "status": {
                        "code": tender.get("ihaleDurum"),
                        "description": tender.get("ihaleDurumAciklama")
                    },
                    "authority": tender.get("idareAdi"),
                    "province": tender.get("ihaleIlAdi"),
                    "tender_datetime": tender.get("ihaleTarihSaat"),
                    "document_count": tender.get("dokumanSayisi", 0),
                    "has_announcement": tender.get("ilanVarMi", False),
                    "document_url": document_url
                }
                formatted_tenders.append(formatted_tender)
            
            result = {
                "tenders": formatted_tenders,
                "total_count": total_count,
                "returned_count": len(formatted_tenders)
            }
            
            # Province filtering is now handled by the API directly
            return result
            
        except httpx.HTTPStatusError as e:
            return {
                "error": f"API request failed with status {e.response.status_code}",
                "message": str(e)
            }
        except Exception as e:
            return {
                "error": "Request failed",
                "message": str(e)
            }
    
    async def search_okas_codes(
        self,
        search_term: str = "",
        kalem_turu: Optional[Literal[1, 2, 3]] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Search OKAS (public procurement classification) codes"""
        
        # Validate limit
        if limit > 500:
            limit = 500
        elif limit < 1:
            limit = 1
        
        # Build API request payload for OKAS search
        okas_params = {
            "loadOptions": {
                "filter": {
                    "sort": [],
                    "group": [],
                    "filter": [],
                    "totalSummary": [],
                    "groupSummary": [],
                    "select": [],
                    "preSelect": [],
                    "primaryKey": []
                }
            }
        }
        
        # Add search filters if provided
        filters = []
        
        if search_term:
            # Search in both Turkish and English descriptions
            filters.extend([
                ["kalemAdi", "contains", search_term],
                "or",
                ["kalemAdiEng", "contains", search_term]
            ])
        
        # Note: kalem_turu filtering causes 500 errors on the API
        # We'll filter client-side after getting results
        
        if filters:
            okas_params["loadOptions"]["filter"]["filter"] = filters
        
        # Set take limit for API
        okas_params["loadOptions"]["take"] = limit
        
        try:
            # Make API request to OKAS endpoint
            response_data = await self._make_request(self.okas_endpoint, okas_params)
            
            # Parse and format the response
            okas_items = response_data.get("loadResult", {}).get("data", [])
            
            # Format each OKAS code for better readability
            results = []
            for item in okas_items:
                kalem_turu_desc = {
                    1: "Mal (Goods)",
                    2: "Hizmet (Service)", 
                    3: "Yapım (Construction)"
                }.get(item.get("kalemTuru"), "Unknown")
                
                # Client-side filtering by kalem_turu since API filtering causes 500 errors
                if kalem_turu is not None and item.get("kalemTuru") != kalem_turu:
                    continue
                
                results.append({
                    "id": item.get("id"),
                    "code": item.get("kod"),
                    "description_tr": item.get("kalemAdi"),
                    "description_en": item.get("kalemAdiEng"),
                    "item_type": {
                        "code": item.get("kalemTuru"),
                        "description": kalem_turu_desc
                    },
                    "code_level": item.get("kodLevel"),
                    "parent_id": item.get("parentId"),
                    "has_items": item.get("hasItem", False),
                    "child_count": item.get("childCount", 0)
                })
            
            # Apply limit after client-side filtering
            if len(results) > limit:
                results = results[:limit]
            
            return {
                "okas_codes": results,
                "total_found": len(results),
                "search_params": {
                    "search_term": search_term,
                    "kalem_turu": kalem_turu,
                    "limit": limit
                },
                "item_type_legend": {
                    "1": "Mal (Goods)",
                    "2": "Hizmet (Service)",
                    "3": "Yapım (Construction)"
                }
            }
            
        except httpx.HTTPStatusError as e:
            return {
                "error": f"API request failed with status {e.response.status_code}",
                "message": str(e)
            }
        except Exception as e:
            return {
                "error": "Request failed",
                "message": str(e)
            }
    
    async def resolve_okas_names(self, okas_codes: List[str]) -> List[str]:
        """Resolve OKAS code values to their Turkish names by querying the API."""
        if not okas_codes:
            return []

        # Build filter: ["kod", "=", code1] or ["kod", "=", code2] or ...
        filters = []
        for i, code in enumerate(okas_codes):
            if i > 0:
                filters.append("or")
            filters.append(["kod", "=", code])

        okas_params = {
            "loadOptions": {
                "filter": {
                    "sort": [],
                    "group": [],
                    "filter": filters,
                    "totalSummary": [],
                    "groupSummary": [],
                    "select": [],
                    "preSelect": [],
                    "primaryKey": []
                },
                "take": len(okas_codes)
            }
        }

        try:
            response_data = await self._make_request(self.okas_endpoint, okas_params)
            okas_items = response_data.get("loadResult", {}).get("data", [])

            # Build code->name lookup
            code_to_name = {}
            for item in okas_items:
                kod = item.get("kod")
                if kod:
                    code_to_name[kod] = item.get("kalemAdi", "")

            # Return names in same order as input codes
            return [code_to_name.get(code, "") for code in okas_codes]
        except Exception:
            return ["" for _ in okas_codes]

    async def search_authorities(
        self,
        search_term: str = "",
        limit: int = 50
    ) -> Dict[str, Any]:
        """Search Turkish government authorities/institutions"""
        
        # Validate limit
        if limit > 500:
            limit = 500
        elif limit < 1:
            limit = 1
        
        # Build API request payload for authority search
        authority_params = {
            "loadOptions": {
                "filter": {
                    "sort": [],
                    "group": [],
                    "filter": [],
                    "totalSummary": [],
                    "groupSummary": [],
                    "select": [],
                    "preSelect": [],
                    "primaryKey": []
                }
            }
        }
        
        # Add search filters if provided
        filters = []
        
        if search_term:
            # Search in authority names (correct field name is 'ad')
            filters.append(["ad", "contains", search_term])
        
        if filters:
            authority_params["loadOptions"]["filter"]["filter"] = filters
        
        # Set take limit for API
        authority_params["loadOptions"]["take"] = limit
        
        try:
            # Make API request to authority endpoint
            response_data = await self._make_request(self.authority_endpoint, authority_params)
            
            # Parse and format the response
            authority_items = response_data.get("loadResult", {}).get("data", [])
            
            # Format each authority for better readability
            results = []
            for item in authority_items:
                results.append({
                    "id": item.get("id"),
                    "name": item.get("ad"),
                    "parent_id": item.get("parentIdareKimlikKodu"),
                    "level": item.get("seviye"),
                    "has_children": item.get("hasItems", False),
                    "child_count": 0,  # Not available in response
                    "detsis_no": item.get("detsisNo"),
                    "idare_id": item.get("idareId")
                })
            
            return {
                "authorities": results,
                "total_found": len(results),
                "search_params": {
                    "search_term": search_term,
                    "limit": limit
                }
            }
            
        except httpx.HTTPStatusError as e:
            return {
                "error": f"API request failed with status {e.response.status_code}",
                "message": str(e)
            }
        except Exception as e:
            return {
                "error": "Request failed - authority search",
                "message": str(e)
            }
    
    async def get_tender_announcements(
        self,
        tender_id: str
    ) -> Dict[str, Any]:
        """Get all announcements for a specific tender"""
        
        # Build API request payload for announcements
        announcement_params = {
            "ihaleId": tender_id
        }
        
        try:
            # Make API request to announcements endpoint
            response_data = await self._make_request(self.announcements_endpoint, announcement_params)
            
            # Parse and format the response
            announcements = response_data.get("list", [])
            
            # Initialize markdown converter (always convert)
            markitdown = MarkItDown()
            
            # Format each announcement for better readability
            results = []
            for announcement in announcements:
                # Map announcement types
                announcement_type_map = {
                    "1": "Ön İlan",
                    "2": "İhale İlanı",
                    "3": "İptal İlanı",
                    "4": "Sonuç İlanı",
                    "5": "Ön Yeterlik İlanı",
                    "6": "Düzeltme İlanı"
                }
                
                announcement_type = announcement.get("ilanTip", "")
                announcement_type_desc = announcement_type_map.get(announcement_type, f"Type {announcement_type}")
                
                html_content = announcement.get("veriHtml", "")
                
                # Always convert HTML to markdown
                markdown_content = None
                if html_content:
                    try:
                        # Create BytesIO from HTML content
                        html_bytes = BytesIO(html_content.encode('utf-8'))
                        result = markitdown.convert_stream(html_bytes, file_extension=".html")
                        markdown_content = result.text_content if result else None
                    except Exception as e:
                        print(f"Warning: Failed to convert HTML to markdown: {e}")
                        markdown_content = None
                
                # EKAP'ın "istekliAdi" alanı sonuç ilanlarında dahi boş geliyor.
                # Kazanan ve sözleşme bilgileri yalnızca ilan metninde bulunduğu
                # için sonuç ilanları (tip 4) ayrıca ayrıştırılır.
                result_info = None
                bidder_name = announcement.get("istekliAdi")
                if announcement_type == "4" and markdown_content:
                    result_info = parse_result_announcement(markdown_content)
                    bidder_name = bidder_name or result_info.get("winner")

                results.append({
                    "id": announcement.get("id"),
                    "type": {
                        "code": announcement_type,
                        "description": announcement_type_desc
                    },
                    "title": announcement.get("baslik"),
                    "date": announcement.get("ilanTarihi"),
                    "status": announcement.get("status"),
                    "tender_id": announcement.get("ihaleId"),
                    "contract_id": announcement.get("sozlesmeId"),
                    "bidder_name": bidder_name,
                    "result_info": result_info,
                    "markdown_content": markdown_content,
                    "content_preview": self._extract_text_preview(html_content)
                })
            
            return {
                "announcements": results,
                "total_count": len(results),
                "tender_id": tender_id
            }
            
        except httpx.HTTPStatusError as e:
            return {
                "error": f"API request failed with status {e.response.status_code}",
                "message": str(e)
            }
        except Exception as e:
            return {
                "error": "Request failed - tender announcements",
                "message": str(e)
            }
    
    async def search_tender_results_by_bidder(
        self,
        bidder_name: str,
        authority_ids: List[int] = None,
        provinces: List[int] = None,
        okas_codes: List[str] = None,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
        tender_types: List[int] = None,
        max_tenders: int = 500,
        concurrency: int = 8,
    ) -> Dict[str, Any]:
        """Belirtilen kapsamdaki sonuç ilanlarını tarayıp yükleniciye göre eşleştirir.

        EKAP'ın arama indeksi sonuç ilanlarını kapsamadığı için firma adından
        ihaleye giden doğrudan bir sorgu yok. Bu metot, daraltılmış bir kapsamdaki
        sonuçlanmış ihalelerin sonuç ilanlarını çekip yüklenici alanında eşleştirir.
        Tam bir ters indeks değildir.
        """
        if not bidder_name or not bidder_name.strip():
            return {
                "error": "Geçersiz parametre",
                "message": "bidder_name (yüklenici adı) zorunludur.",
            }

        if not (authority_ids or provinces or okas_codes):
            return {
                "error": "Kapsam filtresi gerekli",
                "message": (
                    "Bu araç bir taramadır ve kapsam daraltılmadan çalışmaz. "
                    "authority_ids, provinces veya okas_codes parametrelerinden "
                    "en az birini verin. Tarih aralığı (date_start/date_end) ile "
                    "daha da daraltabilirsiniz."
                ),
            }

        scope = {
            "authority_ids": authority_ids,
            "provinces": provinces,
            "okas_codes": okas_codes,
            "date_start": date_start,
            "date_end": date_end,
            "tender_types": tender_types,
            "max_tenders": max_tenders,
        }

        search_kwargs = {
            "search_text": None,
            "tender_statuses": [15],  # Sonuç İlanı Yayımlanmış
            "authority_ids": authority_ids,
            "provinces": provinces,
            "okas_codes": okas_codes,
            "tender_types": tender_types,
            "tender_date_start": date_start,
            "tender_date_end": date_end,
        }

        # Önce kapsamın büyüklüğünü öğren; tavanı aşıyorsa sessizce kesme.
        probe = await self.search_tenders(limit=1, skip=0, **search_kwargs)
        if probe.get("error"):
            return probe

        total = probe.get("total_count", 0)
        if total > max_tenders:
            return {
                "error": "Kapsam çok geniş",
                "message": (
                    f"Belirtilen kapsam {total} sonuçlanmış ihale içeriyor, "
                    f"tavan {max_tenders}. Kapsamı daraltın (idare, il, OKAS veya "
                    f"tarih aralığı) ya da max_tenders değerini yükseltin."
                ),
                "scope_size": total,
                "scope": scope,
            }

        # Kapsamdaki ihaleleri sayfalayarak topla.
        tenders = []
        page_size = 100
        while len(tenders) < total:
            page = await self.search_tenders(
                limit=page_size, skip=len(tenders), **search_kwargs
            )
            if page.get("error"):
                return page
            batch = page.get("tenders") or []
            if not batch:
                break
            tenders.extend(batch)

        target = normalize_company_name(bidder_name)
        semaphore = asyncio.Semaphore(concurrency)

        async def scan(tender):
            async with semaphore:
                data = await self.get_tender_announcements(tender["id"])

            if data.get("error"):
                return []

            found = []
            result_announcements = [
                a for a in (data.get("announcements") or [])
                if a.get("type", {}).get("code") == "4"
            ]
            for index, announcement in enumerate(result_announcements):
                parsed = parse_result_announcement(
                    announcement.get("markdown_content")
                )
                winner = parsed.get("winner")
                if not winner:
                    continue
                if target not in normalize_company_name(winner):
                    continue

                found.append({
                    "ikn": tender.get("ikn"),
                    "tender_id": tender.get("id"),
                    "title": tender.get("name"),
                    "authority": tender.get("authority"),
                    "province": tender.get("province"),
                    "tender_date": tender.get("tender_datetime"),
                    "announcement_index": index,
                    "winner": winner,
                    "contract_amount": parsed.get("contract_amount"),
                    "currency": parsed.get("currency"),
                    "estimated_cost": parsed.get("estimated_cost"),
                    "bid_count": parsed.get("bid_count"),
                    "valid_bid_count": parsed.get("valid_bid_count"),
                    "contract_date": parsed.get("contract_date"),
                })
            return found

        scanned = await asyncio.gather(*[scan(t) for t in tenders])
        matches = [m for group in scanned for m in group]

        return {
            "matches": matches,
            "match_count": len(matches),
            "scanned_tenders": len(tenders),
            "scope": scope,
            "note": (
                "Bu bir taramadır, tam indeks değildir. Yalnızca belirtilen "
                "kapsamdaki sonuç ilanları tarandı; kapsam dışındaki işler "
                "bu sonuçta görünmez. Kısmi teklifli ihalelerde her kısım ayrı "
                "kayıt olarak döner (announcement_index)."
            ),
        }

    def _extract_text_preview(self, html_content: str, max_length: int = 200) -> str:
        """Extract plain text preview from HTML content"""
        if not html_content:
            return ""
        
        import re
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html_content)
        
        # Clean up whitespace and newlines
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Truncate if too long
        if len(text) > max_length:
            text = text[:max_length] + "..."
        
        return text
    
    async def get_tender_details(
        self,
        tender_id: str
    ) -> Dict[str, Any]:
        """Get comprehensive details for a specific tender"""
        
        # Build API request payload for tender details
        details_params = {
            "ihaleId": tender_id
        }
        
        try:
            # Make API request to tender details endpoint
            response_data = await self._make_request(self.tender_details_endpoint, details_params)
            
            # Parse and format the response
            item = response_data.get("item", {})
            
            if not item:
                return {
                    "error": "Tender details not found",
                    "tender_id": tender_id
                }
            
            # Format tender characteristics
            characteristics = []
            for char in item.get("ihaleOzellikList", []):
                char_text = char.get("ihaleOzellik", "")
                # Clean up the characteristic text
                if "TENDER_DETAIL." in char_text:
                    char_text = char_text.replace("TENDER_DETAIL.", "").replace("_", " ").title()
                characteristics.append(char_text)
            
            # Format basic tender info
            basic_info = item.get("ihaleBilgi", {})
            
            # Format OKAS codes
            okas_codes = []
            for okas in item.get("ihtiyacKalemiOkasList", []):
                okas_codes.append({
                    "code": okas.get("kodu"),
                    "name": okas.get("adi"),
                    "full_description": okas.get("koduAdi")
                })
            
            # Format authority info
            authority = item.get("idare", {})
            authority_info = {
                "id": authority.get("id"),
                "name": authority.get("adi"),
                "code1": authority.get("kod1"),
                "code2": authority.get("kod2"),
                "phone": authority.get("telefon"),
                "fax": authority.get("fax"),
                "parent_authority": authority.get("ustIdare"),
                "top_authority_code": authority.get("enUstIdareKod"),
                "top_authority_name": authority.get("enUstIdareAdi"),
                "province": authority.get("il", {}).get("adi"),
                "district": authority.get("ilce", {}).get("ilceAdi")
            }
            
            # Format process rules
            rules = item.get("islemlerKuralSeti", {})
            process_rules = {
                "can_download_documents": rules.get("dokumanIndirmisMi", False),
                "has_submitted_bid": rules.get("teklifteBulunmusMu", False),
                "can_submit_bid": rules.get("teklifVerilebilirMi", False),
                "has_non_price_factors": rules.get("fiyatDisiUnsurVarMi", False),
                "contract_signed": rules.get("sozlesmeImzaliMi", False),
                "is_electronic": rules.get("eIhaleMi", False),
                "is_own_tender": rules.get("idareKendiIhaleMi", False),
                "electronic_auction": rules.get("eEksiltmeYapilacakMi", False)
            }
            
            # Initialize markdown converter for tender details HTML content
            markitdown = MarkItDown()
            
            # Format announcements list (basic info) with markdown conversion
            announcements = []
            for announcement in item.get("ilanList", []):
                # Map announcement types
                announcement_type_map = {
                    "1": "Ön İlan",
                    "2": "İhale İlanı", 
                    "3": "İptal İlanı",
                    "4": "Sonuç İlanı",
                    "5": "Ön Yeterlik İlanı",
                    "6": "Düzeltme İlanı"
                }
                
                announcement_type = announcement.get("ilanTip", "")
                announcement_type_desc = announcement_type_map.get(announcement_type, f"Type {announcement_type}")
                
                # Convert HTML content to markdown if available
                html_content = announcement.get("veriHtml", "")
                markdown_content = None
                if html_content:
                    try:
                        # Create BytesIO from HTML content
                        html_bytes = BytesIO(html_content.encode('utf-8'))
                        result = markitdown.convert_stream(html_bytes, file_extension=".html")
                        markdown_content = result.text_content if result else None
                    except Exception as e:
                        print(f"Warning: Failed to convert HTML to markdown in tender details: {e}")
                        markdown_content = None
                
                announcements.append({
                    "id": announcement.get("id"),
                    "type": {
                        "code": announcement_type,
                        "description": announcement_type_desc
                    },
                    "title": announcement.get("baslik"),
                    "date": announcement.get("ilanTarihi"),
                    "status": announcement.get("status"),
                    "markdown_content": markdown_content,
                    "content_preview": self._extract_text_preview(html_content)
                })
            
            # Build comprehensive response
            result = {
                "tender_id": item.get("id"),
                "ikn": item.get("ikn"),
                "name": item.get("ihaleAdi"),
                "status": {
                    "code": item.get("ihaleDurum"),
                    "description": basic_info.get("ihaleDurumAciklama")
                },
                "basic_info": {
                    "is_electronic": item.get("eIhale", False),
                    "method_code": item.get("ihaleUsul"),
                    "method_description": basic_info.get("ihaleUsulAciklama"),
                    "type_description": basic_info.get("ihaleTipiAciklama"),
                    "scope_description": item.get("ihaleKapsamAciklama"),
                    "tender_datetime": basic_info.get("ihaleTarihSaat"),
                    "location": basic_info.get("isinYapilacagiYer"),
                    "venue": basic_info.get("ihaleYeri"),
                    "complaint_fee": basic_info.get("itirazenSikayetBasvuruBedeli"),
                    "is_partial": item.get("kismiIhale", False)
                },
                "characteristics": characteristics,
                "okas_codes": okas_codes,
                "authority": authority_info,
                "process_rules": process_rules,
                "announcements_summary": {
                    "total_count": len(announcements),
                    "announcements": announcements,
                    "types_available": list(set(ann["type"]["description"] for ann in announcements))
                },
                "flags": {
                    "is_authority_tender": item.get("ihaleniIdaresiMi", False),
                    "is_without_announcement": item.get("ihaleIlansizMi", False),
                    "is_invitation_only": item.get("ihaleyeDavetEdilenMi", False),
                    "show_detail_documents": item.get("ihaleDetayDokumaniGorsunMu", False),
                    "show_document_downloaders": item.get("dokumanIndirenlerGosterilsinMi", False)
                },
                "document_count": item.get("dokumanSayisi", 0)
            }
            
            # Add cancellation info if tender is cancelled
            if basic_info.get("iptalTarihi"):
                result["cancellation_info"] = {
                    "cancelled_date": basic_info.get("iptalTarihi"),
                    "cancellation_reason": basic_info.get("iptalNedeni"),
                    "cancellation_article": basic_info.get("iptalMadde")
                }
            
            return result
            
        except httpx.HTTPStatusError as e:
            return {
                "error": f"API request failed with status {e.response.status_code}",
                "message": str(e)
            }
        except Exception as e:
            return {
                "error": "Request failed - tender details",
                "message": str(e)
            }
    
    async def get_tender_document_url(
        self,
        tender_id: str,
        islem_id: str = "1"
    ) -> Dict[str, Any]:
        """Get document URL for a specific tender"""
        
        # Build API request payload for document URL
        document_params = {
            "islemId": islem_id,
            "ihaleId": tender_id
        }
        
        try:
            # Make API request to document URL endpoint
            response_data = await self._make_request(self.document_url_endpoint, document_params)
            
            # Return the URL directly
            document_url = response_data.get("url")
            
            if document_url:
                return {
                    "document_url": document_url,
                    "tender_id": tender_id,
                    "islem_id": islem_id,
                    "success": True
                }
            else:
                return {
                    "error": "No document URL found",
                    "tender_id": tender_id,
                    "success": False
                }
            
        except httpx.HTTPStatusError as e:
            return {
                "error": f"API request failed with status {e.response.status_code}",
                "message": str(e),
                "success": False
            }
        except Exception as e:
            return {
                "error": "Request failed - tender document URL",
                "message": str(e),
                "success": False
            }

    async def search_direct_procurements(
        self,
        search_text: str = "",
        search_in_description: bool = True,
        search_in_name: bool = True,
        search_in_info: bool = True,
        page_index: int = 1,
        order_by: int = 10,
        year: Optional[int] = None,
        dt_no: Optional[str] = None,
        dt_number: Optional[int] = None,
        dt_type: Optional[Literal[1, 2, 3, 4]] = None,
        e_price_offer: Optional[bool] = None,
        status_id: Optional[int] = None,
        status_text: Optional[str] = None,
        date_start: Optional[str] = None,
        date_end: Optional[str] = None,
        province_plate: Optional[int] = None,
        province_name: Optional[str] = None,
        scope_id: Optional[int] = None,
        scope_text: Optional[str] = None,
        authority_id: Optional[int] = None,
        parent_authority_code: Optional[str] = None,
        top_authority_code: Optional[str] = None,
        cookies: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Search Direct Procurements (Doğrudan Temin) via EKAP legacy endpoint.

        Maps YeniIhaleAramaData.ashx (metot=dtAra) response to readable fields.
        Dates accept YYYY-MM-DD and are converted to DD.MM.YYYY.
        """
        if page_index < 1:
            page_index = 1
        params = {
            "metot": "dtAra",
            "arananIfade": search_text or "",
            "dtAciklama": 1 if search_in_description else 0,
            "dtAdi": 1 if search_in_name else 0,
            "dtBilgiSecim": 1 if search_in_info else 0,
            "orderBy": order_by,
            "pageIndex": page_index,
        }
        # Handle DT year: endpoint expects two-digit year (e.g., 25 for 2025)
        if year is not None:
            params["dtnYil"] = (year % 100) if year > 99 else year
        # Handle DT number (dtnSayi) explicitly or parse from dt_no like '25DT1493794'
        if dt_number is not None:
            params["dtnSayi"] = dt_number
        elif dt_no:
            import re
            m = re.match(r"^(\d{2})DT(\d+)$", dt_no.strip(), re.IGNORECASE)
            if m:
                if "dtnYil" not in params:
                    try:
                        params["dtnYil"] = int(m.group(1))
                    except Exception:
                        pass
                try:
                    params["dtnSayi"] = int(m.group(2))
                except Exception:
                    pass
            else:
                # Fallback: keep numeric content as dtnSayi if looks like number
                digits = re.sub(r"\D", "", dt_no)
                if digits:
                    try:
                        params["dtnSayi"] = int(digits)
                    except Exception:
                        pass
        if dt_type is not None:
            params["dtTuru"] = dt_type
        if e_price_offer is not None:
            # Use boolean query string to match legacy endpoint expectations
            params["eihale"] = "true" if e_price_offer else "false"
        # Map status text if provided and id not set
        if status_id is None and status_text:
            st_lower = status_text.strip().lower()
            # direct numeric string support
            if st_lower.isdigit():
                try:
                    status_id = int(st_lower)
                except Exception:
                    status_id = None
            if status_id is None:
                # build lowercase map
                _status_by_text = {v.lower(): k for k, v in DIRECT_PROCUREMENT_STATUSES.items()}
                status_id = _status_by_text.get(st_lower)
            if status_id is None:
                status_id = DIRECT_PROCUREMENT_STATUS_ALIASES.get(st_lower)
        if status_id is not None:
            params["dtDurum"] = status_id
        if date_start:
            params["dtTarihiBaslangic"] = self._format_date_for_api(date_start)
        if date_end:
            params["dtTarihiBitis"] = self._format_date_for_api(date_end)
        # Map province name to plate if provided
        if province_plate is None and province_name:
            plate = NAME_TO_PLATE.get(province_name.strip().upper())
            if plate is not None:
                province_plate = plate
        if province_plate is not None:
            params["ilID"] = province_plate
        # Map scope text if provided and id not set
        if scope_id is None and scope_text:
            sc_lower = scope_text.strip().lower()
            if sc_lower.isdigit():
                try:
                    scope_id = int(sc_lower)
                except Exception:
                    scope_id = None
            if scope_id is None:
                _scope_by_text = {v.lower(): k for k, v in DIRECT_PROCUREMENT_SCOPES.items()}
                scope_id = _scope_by_text.get(sc_lower)
            if scope_id is None:
                scope_id = DIRECT_PROCUREMENT_SCOPE_ALIASES.get(sc_lower)
        if scope_id is not None:
            params["dtKapsami"] = scope_id
        if authority_id is not None:
            params["idareId"] = authority_id
        if parent_authority_code is not None:
            params["ustIdareKod"] = parent_authority_code
        if top_authority_code is not None:
            params["enUstIdareKod"] = top_authority_code

        try:
            data = await self._make_get_request_full_url(self.direct_procurement_url, params=params, cookies=cookies)
            items = data.get("yeniDogrudanTeminAramaResultList", [])
            results: List[Dict[str, Any]] = []
            for it in items:
                tcode = self._safe_int(it.get("E4"))
                results.append({
                    "dt_no": it.get("E1"),
                    "title": it.get("E2"),
                    "authority": it.get("E3"),
                    "type": {
                        "code": tcode,
                        "description": DIRECT_PROCUREMENT_TYPES.get(tcode, "Bilinmiyor")
                    },
                    "due_datetime": it.get("E7"),
                    "announcement_date": it.get("E8"),
                    "detail_token": it.get("E10"),
                    "announcement_token": it.get("E11"),
                    "province_plate": self._safe_int(it.get("E12")),
                    "has_announcement": bool(it.get("E13")),
                    "has_document": bool(it.get("E14"))
                })
            return {
                "direct_procurements": results,
                "returned_count": len(results),
                "page_index": page_index,
                "search_params": {
                    "search_text": search_text,
                    "year": year,
                    "dt_no": dt_no,
                    "dt_type": dt_type,
                    "province_plate": province_plate
                }
            }
        except httpx.HTTPStatusError as e:
            return {
                "error": f"Direct procurement request failed with status {e.response.status_code}",
                "message": str(e)
            }
        except Exception as e:
            return {
                "error": "Direct procurement request failed",
                "message": str(e)
            }

    def _safe_int(self, value: Any) -> Optional[int]:
        try:
            return int(value) if value is not None and value != "" else None
        except Exception:
            return None

    async def get_direct_procurement_details(
        self,
        dogrudan_temin_id: str,
        idare_id: str,
        cookies: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Get details for a specific Direct Procurement (Doğrudan Temin).

        Calls YeniIhaleAramaData.ashx with metot=dtDetayGetir using the encrypted
        tokens returned by the list endpoint (E10=dogrudanTeminId, E11=idareId).
        """
        params = {
            "metot": "dtDetayGetir",
            "dogrudanTeminId": dogrudan_temin_id,
            "idareId": idare_id,
        }
        try:
            data = await self._make_get_request_full_url(self.direct_procurement_url, params=params, cookies=cookies)
            detail = data.get("dogrudanTeminDetayResult", {})
            if not detail:
                return {"error": "No details found", "success": False}

            dt_info = detail.get("DogrudanTeminBilgileri", {})
            authority_info = detail.get("IdareBilgileri", {})
            ilan_bilgileri = detail.get("IlanBilgileri", {})
            contract_info = detail.get("SozlesmeBilgileri", {})

            # Flatten announcement lists into a single list with categories
            announcements: List[Dict[str, Any]] = []
            def append_anns(items: Optional[List[Dict[str, Any]]], category: str):
                if not items:
                    return
                for it in items:
                    announcements.append({
                        "category": category,
                        "date": it.get("IlanTarihi"),
                        "type_code": it.get("IlanTipi"),
                        "enc_id": it.get("EncIlanId")
                    })

            append_anns(ilan_bilgileri.get("DogrudanTeminIlanBilgisiList"), "ilan")
            append_anns(ilan_bilgileri.get("DuzeltmeIlanBilgisiList"), "duzeltme")
            append_anns(ilan_bilgileri.get("IptalIlanBilgisiList"), "iptal")
            append_anns(ilan_bilgileri.get("SonucIlanBilgisiList"), "sonuc")

            result = {
                "basic": {
                    "dt_no": dt_info.get("Dtn"),
                    "name": dt_info.get("IsinAdi"),
                    "type": dt_info.get("Turu"),
                    "scope_article": dt_info.get("YasaKapsamiTeminMaddesi"),
                    "kismi_teklif": dt_info.get("KismiTeklif"),
                    "parts_count": dt_info.get("KisimSayisi"),
                    "okas_codes": dt_info.get("BransKodList", []),
                    "announcement_form": dt_info.get("IlaninSekli"),
                    "dt_datetime": dt_info.get("DtTarihSaati"),
                    "status": dt_info.get("DtDurumu"),
                    "cancel_reason": dt_info.get("IptalNedeni"),
                    "cancel_date": dt_info.get("IptalTarihi"),
                    "will_announce": dt_info.get("DogrudanTeminDuyurusuYapilacakMi"),
                    "is_electronic": dt_info.get("EIhale"),
                    "has_contract_draft": dt_info.get("DogrudanTeminSozlesmeTasarisiVarMi"),
                    "exception_basis": dt_info.get("IstisnaAliminDayanagi"),
                    "regulation_basis": dt_info.get("MevzuatDayanagi"),
                },
                "authority": {
                    "top_authority": authority_info.get("EnUstIdare"),
                    "parent_authority": authority_info.get("UstIdare"),
                    "name": authority_info.get("Idare"),
                    "province": authority_info.get("Ili"),
                },
                "announcements": announcements,
                "contracts": contract_info.get("SozlesmeBilgisiList", []),
                "tokens": {
                    "dogrudanTeminId": dogrudan_temin_id,
                    "idareId": idare_id
                },
                "success": True
            }
            return result
        except httpx.HTTPStatusError as e:
            return {
                "error": f"Direct procurement detail failed with status {e.response.status_code}",
                "message": str(e),
                "success": False
            }
        except Exception as e:
            return {
                "error": "Direct procurement detail request failed",
                "message": str(e),
                "success": False
            }
