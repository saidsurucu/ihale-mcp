#!/usr/bin/env python3
"""
EKAP v2 insan doğrulaması (Cloudflare Turnstile) için çerez sağlayıcı.

EKAP v2 API'si Eylül 2026'dan beri "ekap.human-verification" çerezi olmadan
gelen isteklere 428 {"code": "HUMAN_VERIFICATION_REQUIRED"} dönüyor. Çerez,
frontend'in Turnstile token'ını
  POST /b_han/api/human-verification/verify  (X-Turnstile-Token başlığı)
ile doğrulatmasıyla verilir ve 5 dakika geçerlidir (max-age=300).

Turnstile token'ı gerçek bir tarayıcı gerektirdiği için sayfa Camoufox'un
(Firefox tabanlı, BrowserForge parmak izli) tarayıcısında açılır;
doğrulamayı SPA'nın kendisi yapar, biz yalnızca oluşan çerezi alıp httpx
isteklerinde kullanırız.
"""

import asyncio
import os
import time
from typing import Awaitable, Callable, Optional, Tuple

COOKIE_NAME = "ekap.human-verification"
VERIFICATION_PAGE_URL = "https://ekapv2.kik.gov.tr/ekap/search"

# Sunucu çerezi 300 sn veriyor ve 120 sn kala yenilemeyi öneriyor
# (refreshAtUtc). Süresi dolmak üzere olan çerezi kullanmamak için pay bırak.
REFRESH_MARGIN_SECONDS = 60
DEFAULT_TTL_SECONDS = 300

# Turnstile zaman zaman (özellikle GPU'suz Linux container'da) token vermeyip
# zaman aşımına uğruyor. Böyle ortamlar için bu değişken "off" yapılabilir;
# o zaman EKAP v2 araçları tarayıcı açmadan, anında ve yol gösteren bir
# hatayla döner. Varsayılan (ayarlı değil ya da "on") tarayıcıyla dener.
DISABLE_ENV = "EKAP_HUMAN_VERIFICATION"
DISABLED_MESSAGE = (
    "EKAP v2 insan doğrulaması (Cloudflare Turnstile) bu sunucuda geçilemiyor; "
    "ihale arama/detay araçları uzak sunucuda kullanılamaz. Bu araçlar için "
    "İhale MCP'yi kendi bilgisayarınızda çalıştırın: "
    "uvx --from git+https://github.com/saidsurucu/ihale-mcp ihale-mcp "
    "(doğrudan temin ve ilan.gov.tr araçları uzak sunucuda çalışır)."
)

# (çerez değeri, bitiş zamanı epoch saniye)
CookieFetcher = Callable[[], Awaitable[Tuple[str, float]]]


class HumanVerificationError(RuntimeError):
    """Turnstile doğrulaması tamamlanamadı."""


class HumanVerificationProvider:
    """Doğrulama çerezini önbellekler ve gerektiğinde tarayıcıyla yeniler."""

    def __init__(
        self,
        page_url: str = VERIFICATION_PAGE_URL,
        timeout_seconds: float = 30.0,
        fetch_cookie: Optional[CookieFetcher] = None,
    ):
        self.page_url = page_url
        self.timeout_seconds = timeout_seconds
        self._fetch_cookie = fetch_cookie or self._fetch_with_browser
        self._value: Optional[str] = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    def _is_fresh(self) -> bool:
        return (
            self._value is not None
            and time.time() < self._expires_at - REFRESH_MARGIN_SECONDS
        )

    async def get_cookie(self, stale: Optional[str] = None) -> str:
        """`Cookie` başlığına eklenecek "ad=değer" çiftini döndürür.

        stale: sunucunun 428 ile reddettiği çerez. Önbellekteki çerez hâlâ bu
        ise yenilenir; eşzamanlı istekler aynı reddi aldığında tarayıcı yalnızca
        bir kez çalışır.
        """
        if os.environ.get(DISABLE_ENV, "").strip().lower() in ("off", "0", "false", "disabled"):
            raise HumanVerificationError(DISABLED_MESSAGE)

        async with self._lock:
            current = f"{COOKIE_NAME}={self._value}" if self._value else None
            if not self._is_fresh() or (stale is not None and stale == current):
                self._value, self._expires_at = await self._fetch_cookie()
            return f"{COOKIE_NAME}={self._value}"

    # Tarayıcı profili bilerek tutarlı bir gerçek kullanıcıya benzetilir:
    # Windows + Türkçe yer ayarı + İstanbul saat dilimi. Camoufox (BrowserForge)
    # WebGL/canvas/yazıtipleri dahil parmak izini tutarlı üretir; GPU'suz
    # Linux'ta Chromium'un SwiftShader sızıntısı Turnstile'ı geçirmez.
    # Her deneme taze profille yapılır.
    BROWSER_OS = "windows"
    BROWSER_LOCALE = "tr-TR"
    BROWSER_TIMEZONE = "Europe/Istanbul"
    MAX_ATTEMPTS = 2

    async def _fetch_with_browser(self) -> Tuple[str, float]:
        # Camoufox bağımlılığı ağır; yalnızca gerçekten doğrulama
        # gerektiğinde yükle.
        try:
            from camoufox.async_api import AsyncCamoufox
        except ImportError as e:
            raise HumanVerificationError(
                "EKAP insan doğrulaması için Camoufox gerekli: "
                "pip install camoufox && python -m camoufox fetch"
            ) from e

        last_error: Optional[Exception] = None
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            started = time.monotonic()
            print(
                f"[ekap-verify] deneme {attempt}/{self.MAX_ATTEMPTS} "
                f"(tavan {self.timeout_seconds:.0f} sn)",
                flush=True,
            )
            try:
                cookie = await self._fetch_single_attempt(AsyncCamoufox)
            except HumanVerificationError as e:
                last_error = e
                print(
                    f"[ekap-verify] deneme {attempt} başarısız "
                    f"({time.monotonic() - started:.1f} sn): {e}",
                    flush=True,
                )
                continue
            print(
                f"[ekap-verify] çerez alındı "
                f"({time.monotonic() - started:.1f} sn, deneme {attempt})",
                flush=True,
            )
            return cookie
        raise HumanVerificationError(
            "EKAP Turnstile doğrulaması tamamlanamadı "
            f"({self.MAX_ATTEMPTS} deneme). Son hata: {last_error}. "
            "Bu araçlar için İhale MCP'yi kendi bilgisayarınızda çalıştırın: "
            "uvx --from git+https://github.com/saidsurucu/ihale-mcp ihale-mcp."
        )

    async def _fetch_single_attempt(self, browser_cls) -> Tuple[str, float]:
        found: dict = {}
        deadline = time.monotonic() + self.timeout_seconds

        try:
            async with browser_cls(
                headless=True,
                os=self.BROWSER_OS,
                locale=self.BROWSER_LOCALE,
            ) as browser:
                page = await browser.new_page(timezone_id=self.BROWSER_TIMEZONE)
                try:
                    await page.goto(self.page_url, timeout=int(self.timeout_seconds * 1000))
                    while time.monotonic() < deadline:
                        for cookie in await page.context.cookies(self.page_url):
                            if cookie["name"] == COOKIE_NAME and cookie.get("value"):
                                found["cookie"] = cookie
                                break
                        if found:
                            break
                        await page.wait_for_timeout(500)
                finally:
                    await page.close()
        except HumanVerificationError:
            raise
        except Exception as e:
            raise HumanVerificationError(
                f"EKAP doğrulama sayfası açılamadı ({type(e).__name__}: {e}). "
                "Tarayıcı kurulu değilse 'python -m camoufox fetch' çalıştırın."
            ) from e

        cookie = found.get("cookie")
        if not cookie:
            raise HumanVerificationError(
                "EKAP Turnstile doğrulaması zaman aşımına uğradı; "
                f"{COOKIE_NAME} çerezi alınamadı."
            )

        expires = cookie.get("expires") or -1
        if expires <= 0:
            expires = time.time() + DEFAULT_TTL_SECONDS
        return cookie["value"], float(expires)
