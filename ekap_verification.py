#!/usr/bin/env python3
"""
EKAP v2 insan doğrulaması (Cloudflare Turnstile) için çerez sağlayıcı.

EKAP v2 API'si Eylül 2026'dan beri "ekap.human-verification" çerezi olmadan
gelen isteklere 428 {"code": "HUMAN_VERIFICATION_REQUIRED"} dönüyor. Çerez,
frontend'in Turnstile token'ını
  POST /b_han/api/human-verification/verify  (X-Turnstile-Token başlığı)
ile doğrulatmasıyla verilir ve 5 dakika geçerlidir (max-age=300).

Turnstile token'ı gerçek bir tarayıcı gerektirdiği için sayfa Scrapling'in
stealth tarayıcısında açılır; doğrulamayı SPA'nın kendisi yapar, biz yalnızca
oluşan çerezi alıp httpx isteklerinde kullanırız.
"""

import asyncio
import time
from typing import Awaitable, Callable, Optional, Tuple

COOKIE_NAME = "ekap.human-verification"
VERIFICATION_PAGE_URL = "https://ekapv2.kik.gov.tr/ekap/search"

# Sunucu çerezi 300 sn veriyor ve 120 sn kala yenilemeyi öneriyor
# (refreshAtUtc). Süresi dolmak üzere olan çerezi kullanmamak için pay bırak.
REFRESH_MARGIN_SECONDS = 60
DEFAULT_TTL_SECONDS = 300

# (çerez değeri, bitiş zamanı epoch saniye)
CookieFetcher = Callable[[], Awaitable[Tuple[str, float]]]


class HumanVerificationError(RuntimeError):
    """Turnstile doğrulaması tamamlanamadı."""


class HumanVerificationProvider:
    """Doğrulama çerezini önbellekler ve gerektiğinde tarayıcıyla yeniler."""

    def __init__(
        self,
        page_url: str = VERIFICATION_PAGE_URL,
        timeout_seconds: float = 60.0,
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
        async with self._lock:
            current = f"{COOKIE_NAME}={self._value}" if self._value else None
            if not self._is_fresh() or (stale is not None and stale == current):
                self._value, self._expires_at = await self._fetch_cookie()
            return f"{COOKIE_NAME}={self._value}"

    async def _fetch_with_browser(self) -> Tuple[str, float]:
        # Scrapling tarayıcı bağımlılıkları ağır; yalnızca gerçekten
        # doğrulama gerektiğinde yükle.
        try:
            from scrapling.fetchers import AsyncStealthySession
        except ImportError as e:
            raise HumanVerificationError(
                "EKAP insan doğrulaması için Scrapling gerekli: "
                "pip install 'scrapling[fetchers]' && scrapling install"
            ) from e

        found = {}

        async def wait_for_cookie(page):
            deadline = time.monotonic() + self.timeout_seconds
            while time.monotonic() < deadline:
                for cookie in await page.context.cookies(self.page_url):
                    if cookie["name"] == COOKIE_NAME and cookie.get("value"):
                        found["cookie"] = cookie
                        return page
                await page.wait_for_timeout(250)
            return page

        try:
            async with AsyncStealthySession(headless=True, disable_resources=True) as session:
                await session.fetch(
                    self.page_url,
                    page_action=wait_for_cookie,
                    load_dom=False,
                    timeout=int(self.timeout_seconds * 1000),
                )
        except Exception as e:
            raise HumanVerificationError(
                f"EKAP doğrulama sayfası açılamadı ({type(e).__name__}: {e}). "
                "Tarayıcı kurulu değilse 'scrapling install' çalıştırın."
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
