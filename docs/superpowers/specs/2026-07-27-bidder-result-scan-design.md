# Yüklenici Bazlı Sonuç Tarama Aracı — Tasarım

Tarih: 2026-07-27

## Problem

Kullanıcılar rakip analizi için "X firması hangi ihaleleri kazandı?" sorusunu sormak istiyor.
Bu sorgu şu an MCP'de yok ve **EKAP'ta da yok**.

Kanıt (2026-07-27 tarihinde ölçüldü):

- Sonuç ilanında yüklenici olarak birebir `DURAK GRUP YAPI İNŞAAT...` yazan 2026/1287772 no'lu
  ihale, aynı ad ile 11 arama alanının tamamı açıkken arandığında dönmüyor.
  `MEHMET NURİ ÇELİKYAY` (2026/1309463) için de aynı sonuç.
- EKAP v2 frontend'inden çıkarılan 205 API ucunda firma/istekli/yüklenici bazlı sorgu ucu yok.
- `Ilan/GetList` ucu `istekliAdi`, `searchText`, `yukleniciAdi` parametrelerinin hepsine
  HTTP 500 döndürüyor; yalnızca `ihaleId` kabul ediyor.

Sonuç: EKAP'ın full-text indeksi sonuç ilanlarını kapsamıyor. Kazanan adı yalnızca sonuç
ilanında geçtiği için firma adından ihaleye giden yol yok.

## Kapsam kararı

Tam ters indeks (tüm sonuç ilanlarını tarayıp kazanan → ihale eşlemesi kurmak) bu MCP'nin
kapsamı dışında. Ölçülen maliyet: 0.81 sn/ihale (8 paralel), 1.681.170 sonuçlanmış ihale
→ ilk dolum ~380 saat. Bu, MCP'yi stateless proxy'den veritabanı + cron gerektiren bir veri
ürününe dönüştürür.

Bunun yerine **kapsamı daraltılmış tarama** yapılır: kullanıcı idare/il/OKAS/tarih ile bir
alt küme belirtir, araç o kümedeki sonuç ilanlarını çekip yüklenici alanında eşleştirir.

Bu bir tarama, tam indeks değildir. Araç bunu çıktısında açıkça belirtir.

## Bileşenler

### 1. `normalize_company_name(name: str) -> str`

Saf fonksiyon. Firma adı varyasyonlarını tek biçime indirir.

Adımlar:
1. Büyük harfe çevir (Türkçe kurallarına göre: `i` → `İ`)
2. Türkçe karakterleri katla (Ç→C, Ğ→G, İ/I→I, Ö→O, Ş→S, Ü→U)
3. Noktalama ve fazla boşlukları temizle
4. Ünvan eklerini at: `LIMITED SIRKETI`, `LTD STI`, `ANONIM SIRKETI`, `AS`,
   `SANAYI`, `TICARET`, `SAN`, `TIC`, `VE`

Örnek: `"durak grup"` ve `"DURAK GRUP YAPI İNŞAAT EMLAK TEKSTİL SANAYİ VE TİCARET LİMİTED ŞİRKETİ"`
→ ikincisi birincisini içerir.

### 2. `parse_result_announcement(markdown: str) -> dict`

Saf fonksiyon. Sonuç İlanı markdown'ından yapılandırılmış alanlar çıkarır.

Döndürdüğü alanlar (bulunamayan `None`):

| Alan | Kaynak etiketi |
|---|---|
| `winner` | `Yüklenici` veya `Yüklenicisi` |
| `winner_address` | `Yüklenicinin adresi` |
| `winner_nationality` | `Yüklenicinin uyruğu` |
| `contract_amount` | `Sözleşmenin ... Bedeli` |
| `contract_date` | `Sözleşmenin ... Tarihi` |
| `contract_duration` | `Sözleşmenin ... Süresi` |
| `estimated_cost` | `Yaklaşık Maliyeti` |
| `bid_count` | `Toplam Teklif Sayısı` |
| `valid_bid_count` | `Toplam Geçerli Teklif Sayısı` |

Tasarım notları:

- Parser markdown üzerinde çalışır, HTML üzerinde değil. Markdown dönüşümü zaten mevcut kod
  yolunda var ve tablo yapısı düzleşmiş durumda; regex'i kırılgan HTML'e bağlamaktan sağlam.
- Etiket varyasyonu gerçek: `Yüklenici` (Hizmet) ve `Yüklenicisi` (Yapım) ikisi de görüldü.
- Bazı değerlerde artık HTML yorumu kalıyor (`5.169.417,32 TRY -->`); temizlenir.
- Alan bulunamazsa `None` döner. Uydurma veya tahmin yok.

### 3. `EKAPClient.search_tender_results_by_bidder(...)`

Orkestrasyon. Akış:

1. **Kapsam doğrula** — `authority_ids`, `provinces`, `okas_codes` alanlarından en az biri
   dolu olmalı. Değilse hata döner (tarama yapılmaz).
2. **Sonuçlanmış ihaleleri listele** — `tender_statuses=[15]` + verilen kapsam filtreleri.
3. **Tavan kontrolü** — kapsamdaki toplam ihale `max_tenders`'ı aşarsa hata döner.
   Sessiz kesme yapılmaz.
4. **Sonuç ilanlarını çek** — 8 eşzamanlı istek (ölçülen: 0.81 sn/ihale).
5. **Parse et ve eşleştir** — her sonuç ilanı için `parse_result_announcement`, ardından
   `normalize_company_name` ile içerme kontrolü.

Parametreler:

```
bidder_name: str            # zorunlu
authority_ids: List[int]    # kapsam \
provinces: List[int]        # kapsam  } en az biri zorunlu
okas_codes: List[str]       # kapsam /
date_start: str             # opsiyonel, kapsamı daraltır
date_end: str               # opsiyonel
tender_types: List[int]     # opsiyonel
max_tenders: int = 500      # tavan
```

Dönüş:

```python
{
  "matches": [
    {
      "ikn", "tender_id", "title", "authority", "province", "tender_date",
      "winner", "contract_amount", "estimated_cost",
      "bid_count", "valid_bid_count", "contract_date",
      "announcement_index"
    }
  ],
  "match_count": int,
  "scanned_tenders": int,
  "scope": {...},           # uygulanan filtreler
  "note": "Bu bir taramadır, tam indeks değildir. Yalnızca belirtilen kapsam tarandı."
}
```

**Kısmi teklif:** Bir ihalede birden fazla sonuç ilanı olabilir (her kısma ayrı yüklenici;
2026/729693'te 3 sonuç ilanı görüldü). Her ilan ayrı `match` olarak döner ve
`announcement_index` ile ayrışır. Bu nedenle `match_count` eşleşen ihale sayısından büyük
olabilir.

### 4. `get_tender_announcements` düzeltmesi

`bidder_name` alanı EKAP'ın `istekliAdi` alanından geliyor ve **her zaman `None`**
(2026-07-27'de doğrulandı). Bu alan artık sonuç ilanları için `parse_result_announcement`
çıktısından doldurulur; ayrıca ayrıştırılan diğer alanlar `result_info` altında döner.

Bu, tarama aracı hiç kullanılmasa bile "yapılandırılmış kazanan/bedel alanı" ihtiyacını
karşılar ve istemcilerin sonuç ilanı markdown'ını regex ile ayıklamasını gereksiz kılar.

## Bağımsız düzeltilen hatalar

1. `ihale_mcp.py` — `announcement_types` docstring'i "3=Sonuç İlanı" diyor. Gerçek eşleme
   `ihale_client.py`'de: 3=İptal İlanı, **4=Sonuç İlanı**. LLM istemcileri bu yüzden iptal
   ilanlarını sonuç sanıyor.
2. `README.md` — `get_tender_announcements` için `include_html` parametresi belgelenmiş ama
   kodda yok. Belgeden çıkarılır.

## Test stratejisi

Parser ve normalize saf fonksiyon olduğu için ağ olmadan test edilir. Fixture'lar gerçek
sonuç ilanlarından alınır:

- Mal, Hizmet, Yapım ihalelerinden birer sonuç ilanı
- Kısmi teklifli, çok sonuç ilanlı ihale
- Eksik alanlı ilan (örn. `Süresi` boş)
- `Yüklenici` ve `Yüklenicisi` etiket varyasyonlarının ikisi de

Orkestrasyon katmanı için: kapsam filtresi verilmediğinde hata, tavan aşıldığında hata.

## Kapsam dışı

- Tam ters indeks / kalıcı veritabanı
- Doğrudan Temin sonuç bilgisi (EKAP DT tarafında yayımlanmıyor)
- Sonuç ilanındaki tüm katılımcı/istekli listesi — sonuç ilanı yalnızca kazananı
  içeriyor, diğer istekliler yayımlanmıyor
