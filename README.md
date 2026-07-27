# İhale MCP: Türkiye Kamu İhaleleri için MCP Sunucusu

Bu proje, Türkiye'deki kamu ihalelerine (`ekap.kik.gov.tr`) erişimi kolaylaştıran bir [FastMCP](https://gofastmcp.com/) sunucusu oluşturur. Bu sayede, EKAP v2 portalından ihale arama, ihale detaylarını getirme ve ihale duyurularını Markdown formatında alma işlemleri, Model Context Protocol (MCP) destekleyen LLM (Büyük Dil Modeli) uygulamaları (örneğin Claude Desktop veya [5ire](https://5ire.app)) ve diğer istemciler tarafından araç (tool) olarak kullanılabilir hale gelir.

---

## 🚀 5 Dakikada Başla (Remote MCP)

**✅ Kurulum Gerektirmez! Hemen Kullan!**

🔗 **Remote MCP Adresi:** `https://ihalemcp.fastmcp.app/mcp`

### Claude Desktop ile Kullanım

1. Claude Desktop'ı açın
2. **Settings → Connectors → Add Custom Connector**
3. Bilgileri girin:
   - **Name:** `İhale MCP`
   - **URL:** `https://ihalemcp.fastmcp.app/mcp`
4. **Add** butonuna tıklayın
5. Hemen kullanmaya başlayın! 🎉

---

🎯 **Temel Özellikler**

* EKAP v2 portalına programatik erişim için standart bir MCP arayüzü.
* Aşağıdaki yetenekler:
    * **Detaylı İhale Arama:** İhale adı/içeriği, IKN numarası, ihale türü, il, tarih aralıkları ve 17+ boolean filtre ile kapsamlı arama.
    * **İhale Detayları:** Belirli bir ihalenin tam detaylarını (özellikler, OKAS kodları, idare bilgileri, işlem kuralları) getirme.
    * **İhale Duyuruları:** İhale ile ilgili tüm duyuruları (Ön İlan, İhale İlanı, Sonuç İlanı vb.) otomatik HTML-to-Markdown dönüşümü ile getirme.
    * **OKAS Kod Arama:** Türk kamu alım sınıflandırma kodlarında arama yapma.
    * **İdare Arama:** Bakanlık, belediye, üniversite gibi kamu kurumlarını arama.
    * **İlan.gov.tr Entegrasyonu:** Resmi devlet ilanları, UYAP e-satış, icra/mahkeme satışları, kamu personel duyuruları ve tebligat aramalar.
* İhale metinlerinin LLM'ler tarafından daha kolay işlenebilmesi için HTML'den Markdown formatına çevrilmesi.
* Claude Desktop uygulaması ile kolay entegrasyon.
* İhale MCP, [5ire](https://5ire.app) gibi Claude Desktop haricindeki MCP istemcilerini de destekler.

---
🚀 **Claude Haricindeki Modellerle Kullanmak İçin Çok Kolay Kurulum (Örnek: 5ire için)**

Bu bölüm, İhale MCP aracını 5ire gibi Claude Desktop dışındaki MCP istemcileriyle kullanmak isteyenler içindir.

* **Python Kurulumu:** Sisteminizde Python 3.11 veya üzeri kurulu olmalıdır. Kurulum sırasında "**Add Python to PATH**" (Python'ı PATH'e ekle) seçeneğini işaretlemeyi unutmayın. [Buradan](https://www.python.org/downloads/) indirebilirsiniz.
* **Git Kurulumu (Windows):** Bilgisayarınıza [git](https://git-scm.com/downloads/win) yazılımını indirip kurun. "Git for Windows/x64 Setup" seçeneğini indirmelisiniz.
* **`uv` Kurulumu:**
    * **Windows Kullanıcıları (PowerShell):** Bir CMD ekranı açın ve bu kodu çalıştırın: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
    * **Mac/Linux Kullanıcıları (Terminal):** Bir Terminal ekranı açın ve bu kodu çalıştırın: `curl -LsSf https://astral.sh/uv/install.sh | sh`
* **Microsoft Visual C++ Redistributable (Windows):** Bazı Python paketlerinin doğru çalışması için gereklidir. [Buradan](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170) indirip kurun.
* İşletim sisteminize uygun [5ire](https://5ire.app) MCP istemcisini indirip kurun.
* 5ire'ı açın. **Workspace -> Providers** menüsünden kullanmak istediğiniz LLM servisinin API anahtarını girin.
* **Tools** menüsüne girin. **+Local** veya **New** yazan butona basın.
    * **Tool Key:** `ihalemcp`
    * **Name:** `İhale MCP`
    * **Command:**
        ```
        uvx --from git+https://github.com/saidsurucu/ihale-mcp ihale-mcp
        ```
    * **Save** butonuna basarak kaydedin.
* Şimdi **Tools** altında **İhale MCP**'yi görüyor olmalısınız. Üstüne geldiğinizde sağda çıkan butona tıklayıp etkinleştirin (yeşil ışık yanmalı).
* Artık İhale MCP ile konuşabilirsiniz.

---
⚙️ **Claude Desktop Manuel Kurulumu**

1.  **Ön Gereksinimler:** Python, `uv`, (Windows için) Microsoft Visual C++ Redistributable'ın sisteminizde kurulu olduğundan emin olun. Detaylı bilgi için yukarıdaki "5ire için Kurulum" bölümündeki ilgili adımlara bakabilirsiniz.
2.  Claude Desktop **Settings -> Developer -> Edit Config**.
3.  Açılan `claude_desktop_config.json` dosyasına `mcpServers` altına ekleyin:

    ```json
    {
      "mcpServers": {
        "İhale MCP": {
          "command": "uvx",
          "args": [
           "--from", "git+https://github.com/saidsurucu/ihale-mcp",
           "ihale-mcp"
          ]
        }
      }
    }
    ```
4.  Claude Desktop'ı kapatıp yeniden başlatın.

🛠️ **Kullanılabilir Araçlar (MCP Tools)**

Bu FastMCP sunucusu LLM modelleri için aşağıdaki araçları sunar:

* **`search_tenders`**: EKAP v2 portalında kapsamlı ihale arama yapar.
    * **Ana Parametreler**: `search_text`, `ikn_year`, `ikn_number`, `tender_types`, `tender_date_start/end`, `announcement_date_start/end`
    * **Boolean Filtreler**: `e_ihale`, `ortak_alim_mi`, `kismi_teklif_mi`, `yabanci_isteklilere_izin_veriliyor_mu` ve 13+ daha fazla filtre
    * **Liste Filtreleri**: `provinces`, `tender_statuses`, `tender_methods`, `okas_codes`, `authority_ids`, `proposal_types`, `announcement_types`
    * **Arama Kapsamı**: `search_in_title`, `search_in_announcement`, `search_in_tech_spec` vb. 11 farklı alan
    * **Döndürdüğü Değer**: Sayfalanmış ihale listesi, toplam sonuç sayısı

* **`search_okas_codes`**: OKAS (kamu alım sınıflandırma) kodlarında arama yapar.
    * **Parametreler**: `search_term`, `kalem_turu` (1=Mal, 2=Hizmet, 3=Yapım), `limit`
    * **Döndürdüğü Değer**: OKAS kodları, açıklamaları ve kategorileri

* **`search_authorities`**: Türk kamu kurumlarında arama yapar.
    * **Parametreler**: `search_term`, `limit`
    * **Döndürdüğü Değer**: Kurum ID'leri, isimleri ve hiyerarşik bilgileri

* **`get_recent_tenders`**: Son N gündeki ihaleleri getirir.
    * **Parametreler**: `days` (1-30), `tender_types`, `limit`
    * **Döndürdüğü Değer**: Yakın tarihli ihale listesi

* **`get_tender_announcements`**: Belirli bir ihalenin tüm duyurularını getirir.
    * **Parametreler**: `tender_id`
    * **Döndürdüğü Değer**: Otomatik HTML-to-Markdown dönüştürülmüş ihale duyuruları
    * **Sonuç İlanları için ek**: Sonuç İlanı (tip 4) duyuruları ayrıca ayrıştırılmış bir `result_info` nesnesi taşır: `winner` (yüklenici), `contract_amount` (sözleşme bedeli), `estimated_cost` (yaklaşık maliyet), `bid_count`, `valid_bid_count`, `contract_date`. Böylece istemcinin markdown'ı regex ile ayıklaması gerekmez.

* **`search_tender_results_by_bidder`**: Bir firmanın **kazandığı** ihaleleri, daraltılmış bir kapsamdaki sonuç ilanlarını tarayarak bulur.
    * **Parametreler**: `bidder_name` (zorunlu), `authority_ids` / `provinces` / `okas_codes` (en az biri zorunlu), `date_start`, `date_end`, `tender_types`, `max_tenders`
    * **Döndürdüğü Değer**: `matches` (İKN, yüklenici, sözleşme bedeli, yaklaşık maliyet, teklif sayısı), `match_count`, `scanned_tenders`
    * ⚠️ **Bu bir taramadır, tam indeks değildir.** EKAP'ın metin arama indeksi sonuç ilanlarını kapsamaz; kazanan adı orada aranamaz. Bu nedenle bir firmanın kazandığı **tüm** ihaleleri listelemek mümkün değildir. Kapsam daraltılmadan (idare/il/OKAS) araç çalışmaz; kapsam `max_tenders`'ı aşarsa sessizce kesmek yerine gerçek kapsam büyüklüğüyle hata döner.
    * Kısmi teklifli ihalelerde her kısım ayrı kayıt olarak döner (`announcement_index`).

* **`get_tender_details`**: Belirli bir ihalenin kapsamlı detaylarını getirir.
    * **Parametreler**: `tender_id`
    * **Döndürdüğü Değer**: İhale özellikleri, OKAS kodları, idare bilgileri, işlem kuralları ve otomatik markdown'a çevrilmiş duyuru özetleri

* **`search_ilan_ads`**: İlan.gov.tr'de resmi devlet ilanlarında arama yapar.
    * **Parametreler**: `search_text`, `city_plate`, `ad_type_filter`, `ad_source_filter`, `publish_date_min/max`, `price_min/max`
    * **İlan Türleri**: İCRA, İHALE, TEBLİGAT, PERSONEL
    * **İlan Kaynakları**: UYAP (E-SATIŞ icra/mahkeme satışları), BIK (Basın İlan Kurumu)
    * **Döndürdüğü Değer**: Resmi devlet ilanları, kategori bilgileri, şehir sayıları

* **`get_ilan_ad_detail`**: Belirli bir ilan için detaylı bilgileri getirir.
    * **Parametreler**: `ad_id`
    * **Döndürdüğü Değer**: İlan başlığı, otomatik HTML-to-Markdown çevrilmiş içerik, ilan veren kurum bilgileri, lokasyon, kategoriler

---
🧩 **Doğrudan Temin (Direct Procurement – Doğrudan Temin) Araçları**

Doğrudan Temin ekranındaki filtrelerle uyumlu ek MCP araçları:

* **`search_direct_procurements`**: Doğrudan Temin listesi (Direct Procurement list).
    * **Önemli Parametreler (English with Türkçe)**:
        - `year (Yıl)`, `dt_no / dt_number (DT No / DT Sayı)`
        - `dt_type (Tür)`: 1=Goods (Mal), 2=Construction (Yapım), 3=Service (Hizmet), 4=Consultancy (Danışmanlık)
        - `e_price_offer (E‑Fiyat Teklifi)` → `eihale=true/false`
        - `status_id/status_text (Durum)`: 202=Doğrudan Temin Duyurusu Yayımlanmış, 3=Teklifler Değerlendiriliyor, 4=Doğrudan Temin Sonuçlandırıldı, 5=Sonuç Bilgileri Gönderildi, 15=Sonuç Duyurusu Yayımlanmış
        - `date_start/date_end (Teklif tarihi)` → `dtTarihiBaslangic/Bitis`
        - `province_plate/province_name (İl)`
        - `scope_id/scope_text (Kapsam)`: 101=4734, 102=İstisna, 103=Kapsam Dışı
        - `authority_id (İdare ID token)` (idareAra’dan), `parent_authority_code (Bağlı Olduğu Üst İdare / ustIdareKod)`
    * **Not**: Bazı filtreler (Durum/Kapsam/İdare) oturum gerektirebilir. Gerekirse `cookies` (Çerez) header değeri verilebilir; istemci ayrıca otomatik ısınma (warm‑up) yapar.

* **`get_direct_procurement_details`**: DT detayları (Details) – `dogrudanTeminId (E10)` + `idareId (E11)` ile.

* **`search_direct_procurement_authorities`**: İdare (Authority) araması; dönen `token`, `search_direct_procurements` içinde `authority_id` olarak kullanılır.

* **`search_direct_procurement_parent_authorities`**: Üst İdare (Parent Authority) araması; dönen `token`, `parent_authority_code (ustIdareKod)` olarak kullanılır.

Örnek (Examples)

```text
search_direct_procurements(
  dt_type=1,                  # Goods (Mal)
  province_name="Antalya",   # İl adı
  status_text="Doğrudan Temin Duyurusu Yayımlanmış",
  date_start="2025-09-01",
  date_end="2025-09-11"
)

# İdare ara → token’ı listede kullan
search_direct_procurement_authorities("antalya")
# => take authorities[0].token as authority_id

search_direct_procurements(
  authority_id="<EIdareToken>",
  parent_authority_code="44|07",  # Bağlı Olduğu Üst İdare (ustIdareKod)
  year=2025, dt_number=1493227
)
```

## İhale Türleri

- **1 - Mal**: Malzeme ve ekipman alımları
- **2 - Yapım**: İnşaat ve altyapı projeleri  
- **3 - Hizmet**: Hizmet sözleşmeleri
- **4 - Danışmanlık**: Danışmanlık hizmetleri

## Örnek Kullanımlar

### EKAP v2 İhaleleri
1. **Pazar Araştırması**: Belirli sektör veya bölgelerdeki fırsatları takip etme
2. **Uygunluk İzleme**: Mevzuata uygunluk için ihale duyurularını takip etme
3. **İş Zekası**: Kamu harcama modellerini ve trendlerini analiz etme
4. **Bildirim Sistemleri**: Belirli ihale türleri için uyarı sistemleri kurma
5. **Veri Analizi**: Araştırma ve analiz için ihale verilerini çıkarma

### İlan.gov.tr Resmi İlanları
6. **UYAP E-SATIŞ Takibi**: İcra dairesi ve mahkeme satışlarını izleme
7. **Personel Duyuruları**: Kamu personel alım ilanlarını takip etme
8. **Tebligat İzleme**: Resmi tebligat ve duyuruları takip etme
9. **Belediye İhaleleri**: Yerel yönetim ihale ilanlarını izleme
10. **Emlak Satışları**: Kamu kurumlarının emlak satış ilanları

## Yeni Özellikler

✅ **17+ Boolean Filtre**: e-İhale, ortak alım, kısmi teklif, yabancı katılım vb.
✅ **Liste Filtreleri**: İller, ihale durumları, usulleri, OKAS kodları, idare ID'leri
✅ **Arama Kapsamı Kontrolü**: IKN, başlık, duyuru, teknik şartname vb. alanlarda arama
✅ **İdare Arama**: 72,000+ kamu kurumunda arama (bakanlık, belediye, üniversite)
✅ **İhale Duyuruları**: Otomatik HTML-to-Markdown dönüşümü ile tam duyuru metinleri
✅ **Kapsamlı İhale Detayları**: Tüm ihale metadata'sı, özellikler, kurallar bir arada
✅ **İlan.gov.tr Entegrasyonu**: 20,000+ resmi devlet ilanı aramalar
✅ **UYAP E-SATIŞ**: 46,000+ icra/mahkeme satış ilanlarına özel erişim
✅ **İlan Detayları**: Otomatik HTML-to-Markdown dönüşümü ile tam ilan içerikleri
✅ **Çoklu İlan Türü**: İCRA, İHALE, TEBLİGAT, PERSONEL kategorileri

## API Hız Limitleri

Bu sunucu EKAP portalının hız limitlerini gözetir. Üretim kullanımı için aşağıdakileri göz önünde bulundurun:
- API çağrılarını azaltmak için istek önbellekleme
- Üstel geri çekilme ile yeniden deneme mantığı
- Yüksek hacimli kullanım için istek sırası

📜 **Lisans**

Bu proje MIT Lisansı altında lisanslanmıştır. Detaylar için `LICENSE` dosyasına bakınız.

## Sorumluluk Reddi

Bu, Türk hükümetinin EKAP portalı ile resmi olmayan bir entegrasyondır. Kullanıcılar portalın hizmet şartlarına ve geçerli düzenlemelere uymakla yükümlüdür. Yazarlar Türk hükümeti veya EKAP portalı ile bağlantılı değildir.
