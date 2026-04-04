#!/usr/bin/env python3
"""
Data models for Turkish Government Tenders (İhale) MCP Server
Contains all Pydantic models and static data for the EKAP v2 integration
"""

from typing import List, Optional
from pydantic import BaseModel, Field

# Data models for the API
class OkasCode(BaseModel):
    """OKAS (public procurement classification) code model"""
    code: str = Field(description="OKAS code")
    description: str = Field(description="Description of the OKAS code")
    category: str = Field(description="Category type (goods, services, etc.)")

class TenderType(BaseModel):
    """Tender type model"""
    id: int = Field(description="Tender type ID")
    code: str = Field(description="Tender type code")
    description: str = Field(description="Tender type description")

class TenderStatus(BaseModel):
    """Tender status model"""
    id: int = Field(description="Status ID")
    code: str = Field(description="Status code")
    description: str = Field(description="Status description")

class TenderMethod(BaseModel):
    """Tender method model"""
    code: str = Field(description="Method code")
    description: str = Field(description="Method description")

class Province(BaseModel):
    """Turkish province model"""
    name: str = Field(description="Province name")

class ProposalType(BaseModel):
    """Proposal/bid type model"""
    code: str = Field(description="Proposal type code")
    description: str = Field(description="Proposal type description")

class AnnouncementType(BaseModel):
    """Announcement type model"""
    code: str = Field(description="Announcement type code")  
    description: str = Field(description="Announcement type description")

class TenderDocument(BaseModel):
    """Tender document information"""
    id: int
    tender_id: str = Field(alias="ihaleId")
    date: str = Field(alias="tarih")

class TenderInfo(BaseModel):
    """Basic tender information from search results"""
    id: int
    name: str = Field(alias="ihaleAdi")
    type_code: str = Field(alias="ihaleTip")
    type_description: str = Field(alias="ihaleTipAciklama")
    ikn: str
    method_description: str = Field(alias="ihaleUsulAciklama")
    status_code: str = Field(alias="ihaleDurum")
    status_description: str = Field(alias="ihaleDurumAciklama")
    authority_name: str = Field(alias="idareAdi")
    province: str = Field(alias="ihaleIlAdi")
    tender_datetime: str = Field(alias="ihaleTarihSaat")
    is_followed: bool = Field(alias="takipEdiliyorMu")
    document_count: int = Field(alias="dokumanSayisi")
    documents: List[TenderDocument] = Field(alias="dokumanListe")
    has_announcement: bool = Field(alias="ilanVarMi")

class TenderSearchResponse(BaseModel):
    """Response from tender search API"""
    tenders: List[TenderInfo] = Field(alias="list")
    total_count: int = Field(alias="totalCount")

# Note: OKAS codes are now fetched dynamically from the live API via search_okas_codes tool
# The static list below is kept for reference but not used in the implementation

TENDER_TYPES = [
    TenderType(id=1, code="1", description="Mal (Goods/Equipment procurement)"),
    TenderType(id=2, code="2", description="Yapım (Construction/Infrastructure projects)"),
    TenderType(id=3, code="3", description="Hizmet (Services procurement)"),
    TenderType(id=4, code="4", description="Danışmanlık (Consultancy services)")
]

TENDER_STATUSES = [
    TenderStatus(id=1, code="1", description="İptal Edilmiş (Cancelled)"),
    TenderStatus(id=2, code="2", description="Teklifler Değerlendiriliyor (Bids under evaluation)"),
    TenderStatus(id=3, code="3", description="Teklif Vermeye Açık (Open for bidding)"),
    TenderStatus(id=4, code="4", description="Teklif Değerlendirme Tamamlanmış (Bid evaluation completed)"),
    TenderStatus(id=5, code="5", description="Sözleşme İmzalanmış (Contract signed)")
]

TENDER_METHODS = [
    TenderMethod(code="Açık", description="Açık İhale Usulü (Open tender method)"),
    TenderMethod(code="Belli İstekliler Arasında", description="Belli İstekliler Arasında İhale (Restricted tender)"),
    TenderMethod(code="Pazarlık", description="Pazarlık Usulü (Negotiated procedure)"),
    TenderMethod(code="Tasarım Yarışması", description="Tasarım Yarışması (Design competition)")
]

# Province plate number to API ID mapping
# Users provide standard Turkish plate numbers (1-81), we convert to API IDs (245-325)
PLATE_TO_API_ID = {
    1: 245,  # ADANA
    2: 246,  # ADIYAMAN
    3: 247,  # AFYONKARAHİSAR
    4: 248,  # AĞRI
    5: 250,  # AMASYA
    6: 251,  # ANKARA
    7: 252,  # ANTALYA
    8: 254,  # ARTVİN
    9: 255,  # AYDIN
    10: 256,  # BALIKESİR
    11: 260,  # BİLECİK
    12: 261,  # BİNGÖL
    13: 262,  # BİTLİS
    14: 263,  # BOLU
    15: 264,  # BURDUR
    16: 265,  # BURSA
    17: 266,  # ÇANAKKALE
    18: 267,  # ÇANKIRI
    19: 268,  # ÇORUM
    20: 269,  # DENİZLİ
    21: 270,  # DİYARBAKIR
    22: 272,  # EDİRNE
    23: 273,  # ELAZIĞ
    24: 274,  # ERZİNCAN
    25: 275,  # ERZURUM
    26: 276,  # ESKİŞEHİR
    27: 277,  # GAZİANTEP
    28: 278,  # GİRESUN
    29: 279,  # GÜMÜŞHANE
    30: 280,  # HAKKARİ
    31: 281,  # HATAY
    32: 283,  # ISPARTA
    33: 302,  # MERSİN
    34: 284,  # İSTANBUL
    35: 285,  # İZMİR
    36: 289,  # KARS
    37: 290,  # KASTAMONU
    38: 291,  # KAYSERİ
    39: 293,  # KIRKLARELİ
    40: 294,  # KIRŞEHİR
    41: 296,  # KOCAELİ
    42: 297,  # KONYA
    43: 298,  # KÜTAHYA
    44: 299,  # MALATYA
    45: 300,  # MANİSA
    46: 286,  # KAHRAMANMARAŞ
    47: 301,  # MARDİN
    48: 303,  # MUĞLA
    49: 304,  # MUŞ
    50: 305,  # NEVŞEHİR
    51: 306,  # NİĞDE
    52: 307,  # ORDU
    53: 309,  # RİZE
    54: 310,  # SAKARYA
    55: 311,  # SAMSUN
    56: 312,  # SİİRT
    57: 313,  # SİNOP
    58: 314,  # SİVAS
    59: 317,  # TEKİRDAĞ
    60: 318,  # TOKAT
    61: 319,  # TRABZON
    62: 320,  # TUNCELİ
    63: 315,  # ŞANLIURFA
    64: 321,  # UŞAK
    65: 322,  # VAN
    66: 324,  # YOZGAT
    67: 325,  # ZONGULDAK
    68: 249,  # AKSARAY
    69: 259,  # BAYBURT
    70: 288,  # KARAMAN
    71: 292,  # KIRIKKALE
    72: 258,  # BATMAN
    73: 316,  # ŞIRNAK
    74: 257,  # BARTIN
    75: 253,  # ARDAHAN
    76: 282,  # IĞDIR
    77: 323,  # YALOVA
    78: 287,  # KARABÜK
    79: 295,  # KİLİS
    80: 308,  # OSMANİYE
    81: 271,  # DÜZCE
}

# Province list with EKAP API-specific IDs (245-325 range)
# These are the actual API IDs used internally
PROVINCES = {
    245: Province(name="ADANA"),
    246: Province(name="ADIYAMAN"),
    247: Province(name="AFYONKARAHİSAR"),
    248: Province(name="AĞRI"),
    249: Province(name="AKSARAY"),
    250: Province(name="AMASYA"),
    251: Province(name="ANKARA"),
    252: Province(name="ANTALYA"),
    253: Province(name="ARDAHAN"),
    254: Province(name="ARTVİN"),
    255: Province(name="AYDIN"),
    256: Province(name="BALIKESİR"),
    257: Province(name="BARTIN"),
    258: Province(name="BATMAN"),
    259: Province(name="BAYBURT"),
    260: Province(name="BİLECİK"),
    261: Province(name="BİNGÖL"),
    262: Province(name="BİTLİS"),
    263: Province(name="BOLU"),
    264: Province(name="BURDUR"),
    265: Province(name="BURSA"),
    266: Province(name="ÇANAKKALE"),
    267: Province(name="ÇANKIRI"),
    268: Province(name="ÇORUM"),
    269: Province(name="DENİZLİ"),
    270: Province(name="DİYARBAKIR"),
    271: Province(name="DÜZCE"),
    272: Province(name="EDİRNE"),
    273: Province(name="ELAZIĞ"),
    274: Province(name="ERZİNCAN"),
    275: Province(name="ERZURUM"),
    276: Province(name="ESKİŞEHİR"),
    277: Province(name="GAZİANTEP"),
    278: Province(name="GİRESUN"),
    279: Province(name="GÜMÜŞHANE"),
    280: Province(name="HAKKARİ"),
    281: Province(name="HATAY"),
    282: Province(name="IĞDIR"),
    283: Province(name="ISPARTA"),
    284: Province(name="İSTANBUL"),
    285: Province(name="İZMİR"),
    286: Province(name="KAHRAMANMARAŞ"),
    287: Province(name="KARABÜK"),
    288: Province(name="KARAMAN"),
    289: Province(name="KARS"),
    290: Province(name="KASTAMONU"),
    291: Province(name="KAYSERİ"),
    292: Province(name="KIRIKKALE"),
    293: Province(name="KIRKLARELİ"),
    294: Province(name="KIRŞEHİR"),
    295: Province(name="KİLİS"),
    296: Province(name="KOCAELİ"),
    297: Province(name="KONYA"),
    298: Province(name="KÜTAHYA"),
    299: Province(name="MALATYA"),
    300: Province(name="MANİSA"),
    301: Province(name="MARDİN"),
    302: Province(name="MERSİN"),
    303: Province(name="MUĞLA"),
    304: Province(name="MUŞ"),
    305: Province(name="NEVŞEHİR"),
    306: Province(name="NİĞDE"),
    307: Province(name="ORDU"),
    308: Province(name="OSMANİYE"),
    309: Province(name="RİZE"),
    310: Province(name="SAKARYA"),
    311: Province(name="SAMSUN"),
    312: Province(name="SİİRT"),
    313: Province(name="SİNOP"),
    314: Province(name="SİVAS"),
    315: Province(name="ŞANLIURFA"),
    316: Province(name="ŞIRNAK"),
    317: Province(name="TEKİRDAĞ"),
    318: Province(name="TOKAT"),
    319: Province(name="TRABZON"),
    320: Province(name="TUNCELİ"),
    321: Province(name="UŞAK"),
    322: Province(name="VAN"),
    323: Province(name="YALOVA"),
    324: Province(name="YOZGAT"),
    325: Province(name="ZONGULDAK")
}

# Proposal Types - API expects numeric IDs
PROPOSAL_TYPES = {
    1: "Götürü-Anahtar Teslimi Götürü",
    2: "Birim Fiyat", 
    3: "Karma"
}

# Announcement Types - API expects numeric IDs
ANNOUNCEMENT_TYPES = {
    1: "Ön İlan",
    2: "İhale İlanı",
    3: "Sonuç İlanı",
    4: "İptal İlanı",
    5: "Ön Yeterlik İlanı",
    6: "Düzeltme İlanı"
}

# Direct Procurement (Doğrudan Temin) Types
DIRECT_PROCUREMENT_TYPES = {
    1: "Mal",
    2: "Yapım",
    3: "Hizmet",
    4: "Danışmanlık",
}

# Direct Procurement Statuses (best-known mapping)
DIRECT_PROCUREMENT_STATUSES = {
    202: "Doğrudan Temin Duyurusu Yayımlanmış",
    3: "Teklifler Değerlendiriliyor",
    4: "Doğrudan Temin Sonuçlandırıldı",
    5: "Sonuç Bilgileri Gönderildi",
    15: "Sonuç Duyurusu Yayımlanmış",
}

# Optional: additional text aliases → status id (lowercase keys)
DIRECT_PROCUREMENT_STATUS_ALIASES = {
    "doğrudan temin duyurusu": 202,
    "doğrudan temin duyurusu yayımlanmış": 202,
    "teklifler değerlendiriliyor": 3,
    "doğrudan temin sonuçlandırıldı": 4,
    "sonuç bilgileri gönderildi": 5,
    "sonuç duyurusu": 15,
    "sonuç duyurusu yayımlanmış": 15,
}

# Direct Procurement Scopes (best-known mapping)
DIRECT_PROCUREMENT_SCOPES = {
    101: "4734 Kapsamında",
    102: "İstisna",
    103: "Kapsam Dışı",
}

# Optional text aliases → scope id (lowercase keys)
DIRECT_PROCUREMENT_SCOPE_ALIASES = {
    "4734 kapsaminda": 101,
    "4734 kapsamında": 101,
    "istisna": 102,
    "kapsam dışı": 103,
    "kapsam disi": 103,
}

# Province name -> plate helper map (computed from PLATE_TO_API_ID + PROVINCES)
NAME_TO_PLATE = {}
for _plate, _api_id in PLATE_TO_API_ID.items():
    _prov = PROVINCES.get(_api_id)
    if _prov and getattr(_prov, 'name', None):
        NAME_TO_PLATE[_prov.name.upper()] = _plate

# İlan.gov.tr data models
class IlanAdFilter(BaseModel):
    """Filter object for ilan.gov.tr API"""
    key: str = Field(description="Filter key")
    value: str = Field(description="Filter value")

class IlanAd(BaseModel):
    """İlan.gov.tr advertisement model"""
    id: str = Field(description="Advertisement ID")
    ad_no: str = Field(alias="adNo", description="Advertisement number")
    advertiser_name: str = Field(alias="advertiserName", description="Advertiser name")
    title: str = Field(description="Advertisement title")
    city_name: str = Field(alias="addressCityName", description="City name")
    county_name: str = Field(alias="addressCountyName", description="County name")
    publish_date: str = Field(alias="publishStartDate", description="Publish start date")
    url: str = Field(alias="urlStr", description="Advertisement URL")
    ad_source_name: str = Field(alias="adSourceName", description="Advertisement source name")
    ad_type_filters: List[IlanAdFilter] = Field(alias="adTypeFilters", description="Advertisement type filters")

class IlanCategory(BaseModel):
    """İlan.gov.tr category model"""
    tax_id: int = Field(alias="taxId", description="Tax ID")
    name: str = Field(description="Category name")
    slug: str = Field(description="Category slug")
    count: int = Field(description="Advertisement count in this category")

class IlanCityCount(BaseModel):
    """İlan.gov.tr city count model"""
    id: int = Field(description="City ID")
    key: str = Field(description="City key/name")
    count: int = Field(description="Advertisement count in this city")

class IlanSearchResponse(BaseModel):
    """Response from ilan.gov.tr search API"""
    ads: List[IlanAd] = Field(description="List of advertisements")
    categories: List[IlanCategory] = Field(description="Available categories")
    city_counts: List[IlanCityCount] = Field(alias="cityCounts", description="City counts")
    num_found: int = Field(alias="numFound", description="Total number of results found")

class IlanAdCategory(BaseModel):
    """Category information for an advertisement"""
    tax_id: int = Field(alias="taxId", description="Tax ID")
    name: str = Field(description="Category name")
    slug: str = Field(description="Category slug")

class IlanAdDetail(BaseModel):
    """Detailed advertisement information from ilan.gov.tr"""
    id: str = Field(description="Advertisement ID")
    ad_no: str = Field(alias="adNo", description="Advertisement number")
    title: str = Field(description="Advertisement title")
    content: str = Field(description="HTML content of the advertisement")
    markdown_content: Optional[str] = Field(None, description="Markdown converted content")
    city_name: str = Field(alias="addressCityName", description="City name")
    county_name: Optional[str] = Field(alias="addressCountyName", description="County name")
    advertiser_name: str = Field(alias="advertiserName", description="Advertiser name")
    advertiser_logo: Optional[str] = Field(alias="advertiserLogo", description="Advertiser logo path")
    ad_source_name: str = Field(alias="adSourceName", description="Ad source name")
    ad_source_code: str = Field(alias="adSourceCode", description="Ad source code")
    url_str: str = Field(alias="urlStr", description="URL string")
    categories: List[IlanAdCategory] = Field(description="Category list")
    ad_type_filters: List[IlanAdFilter] = Field(alias="adTypeFilters", description="Ad type filters")
    hit_count: int = Field(alias="hitCount", description="View count")
    is_archived: bool = Field(alias="isArchived", description="Is archived")
    is_bik_ad: bool = Field(alias="isBikAd", description="Is BİK ad")

# İlan.gov.tr City ID mapping (from API responses)
ILAN_CITY_IDS = {
    "ADANA": 10,
    "ADIYAMAN": 11,
    "AFYONKARAHİSAR": 12,
    "AĞRI": 13,
    "AKSARAY": 14,
    "AMASYA": 15,
    "ANKARA": 16,
    "ANTALYA": 17,
    "ARDAHAN": 18,
    "ARTVİN": 19,
    "AYDIN": 20,
    "BALIKESİR": 21,
    "BARTIN": 22,
    "BATMAN": 23,
    "BAYBURT": 24,
    "BİLECİK": 25,
    "BİNGÖL": 26,
    "BİTLİS": 27,
    "BOLU": 28,
    "BURDUR": 29,
    "BURSA": 30,
    "ÇANAKKALE": 31,
    "ÇANKIRI": 32,
    "ÇORUM": 33,
    "DENİZLİ": 34,
    "DİYARBAKIR": 35,
    "DÜZCE": 36,
    "EDİRNE": 37,
    "ELAZIĞ": 38,
    "ERZİNCAN": 39,
    "ERZURUM": 40,
    "ESKİŞEHİR": 41,
    "GAZİANTEP": 42,
    "GİRESUN": 43,
    "GÜMÜŞHANE": 44,
    "HAKKARİ": 45,
    "HATAY": 46,
    "IĞDIR": 47,
    "ISPARTA": 48,
    "İSTANBUL": 49,
    "İZMİR": 50,
    "KAHRAMANMARAŞ": 51,
    "KARABÜK": 52,
    "KARAMAN": 53,
    "KARS": 54,
    "KASTAMONU": 55,
    "KAYSERİ": 56,
    "KİLİS": 57,
    "KIRIKKALE": 58,
    "KIRKLARELİ": 59,
    "KIRŞEHİR": 60,
    "KOCAELİ": 61,
    "KONYA": 62,
    "KÜTAHYA": 63,
    "MALATYA": 64,
    "MANİSA": 65,
    "MARDİN": 66,
    "MERSİN": 67,
    "MUĞLA": 68,
    "MUŞ": 69,
    "NEVŞEHİR": 70,
    "NİĞDE": 71,
    "ORDU": 72,
    "OSMANİYE": 73,
    "RİZE": 74,
    "SAKARYA": 75,
    "SAMSUN": 76,
    "ŞANLIURFA": 77,
    "SİİRT": 78,
    "SİNOP": 79,
    "ŞIRNAK": 80,
    "SİVAS": 81,
    "TEKİRDAĞ": 82,
    "TOKAT": 83,
    "TRABZON": 84,
    "TUNCELİ": 85,
    "UŞAK": 86,
    "VAN": 87,
    "YALOVA": 88,
    "YOZGAT": 89,
    "ZONGULDAK": 90
}

# İlan.gov.tr Ad Type (ats) mapping
ILAN_AD_TYPES = {
    "İCRA": 2,
    "İHALE": 3,
    "TEBLİGAT": 4,
    "PERSONEL": 5
}

# İlan.gov.tr Ad Source (as) mapping
ILAN_AD_SOURCES = {
    "UYAP": "UYAP",  # UYAP E-SATIŞ (İcra, mahkeme satışları)
    "BIK": "BIK",    # Basın İlan Kurumu
}

# Plate number to ilan.gov.tr city ID mapping
PLATE_TO_ILAN_CITY_ID = {
    1: 10,   # ADANA
    2: 11,   # ADIYAMAN
    3: 12,   # AFYONKARAHİSAR
    4: 13,   # AĞRI
    68: 14,  # AKSARAY
    5: 15,   # AMASYA
    6: 16,   # ANKARA
    7: 17,   # ANTALYA
    75: 18,  # ARDAHAN
    8: 19,   # ARTVİN
    9: 20,   # AYDIN
    10: 21,  # BALIKESİR
    74: 22,  # BARTIN
    72: 23,  # BATMAN
    69: 24,  # BAYBURT
    11: 25,  # BİLECİK
    12: 26,  # BİNGÖL
    13: 27,  # BİTLİS
    14: 28,  # BOLU
    15: 29,  # BURDUR
    16: 30,  # BURSA
    17: 31,  # ÇANAKKALE
    18: 32,  # ÇANKIRI
    19: 33,  # ÇORUM
    20: 34,  # DENİZLİ
    21: 35,  # DİYARBAKIR
    81: 36,  # DÜZCE
    22: 37,  # EDİRNE
    23: 38,  # ELAZIĞ
    24: 39,  # ERZİNCAN
    25: 40,  # ERZURUM
    26: 41,  # ESKİŞEHİR
    27: 42,  # GAZİANTEP
    28: 43,  # GİRESUN
    29: 44,  # GÜMÜŞHANE
    30: 45,  # HAKKARİ
    31: 46,  # HATAY
    76: 47,  # IĞDIR
    32: 48,  # ISPARTA
    34: 49,  # İSTANBUL
    35: 50,  # İZMİR
    46: 51,  # KAHRAMANMARAŞ
    78: 52,  # KARABÜK
    70: 53,  # KARAMAN
    36: 54,  # KARS
    37: 55,  # KASTAMONU
    38: 56,  # KAYSERİ
    79: 57,  # KİLİS
    71: 58,  # KIRIKKALE
    39: 59,  # KIRKLARELİ
    40: 60,  # KIRŞEHİR
    41: 61,  # KOCAELİ
    42: 62,  # KONYA
    43: 63,  # KÜTAHYA
    44: 64,  # MALATYA
    45: 65,  # MANİSA
    47: 66,  # MARDİN
    33: 67,  # MERSİN
    48: 68,  # MUĞLA
    49: 69,  # MUŞ
    50: 70,  # NEVŞEHİR
    51: 71,  # NİĞDE
    52: 72,  # ORDU
    80: 73,  # OSMANİYE
    53: 74,  # RİZE
    54: 75,  # SAKARYA
    55: 76,  # SAMSUN
    63: 77,  # ŞANLIURFA
    56: 78,  # SİİRT
    57: 79,  # SİNOP
    73: 80,  # ŞIRNAK
    58: 81,  # SİVAS
    59: 82,  # TEKİRDAĞ
    60: 83,  # TOKAT
    61: 84,  # TRABZON
    62: 85,  # TUNCELİ
    64: 86,  # UŞAK
    65: 87,  # VAN
    77: 88,  # YALOVA
    66: 89,  # YOZGAT
    67: 90   # ZONGULDAK
}
