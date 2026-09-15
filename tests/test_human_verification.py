"""EKAP insan doğrulaması (Turnstile çerezi) testleri.

Tarayıcı ve ağ erişimi gerektirmez: çerez alma işlevi sahteyle, HTTP katmanı
httpx.MockTransport ile değiştirilir.
"""

import asyncio
import sys
import time
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ekap_verification import COOKIE_NAME, HumanVerificationProvider
from ihale_client import EKAPClient


def counting_fetcher(values, ttl=300):
    """Her çağrıda sıradaki çerez değerini döndüren sahte fetcher."""
    calls = {"count": 0}

    async def fetch():
        value = values[min(calls["count"], len(values) - 1)]
        calls["count"] += 1
        await asyncio.sleep(0)
        return value, time.time() + ttl

    return fetch, calls


async def test_cookie_is_cached_while_fresh():
    fetch, calls = counting_fetcher(["v1"])
    provider = HumanVerificationProvider(fetch_cookie=fetch)

    assert await provider.get_cookie() == f"{COOKIE_NAME}=v1"
    assert await provider.get_cookie() == f"{COOKIE_NAME}=v1"
    assert calls["count"] == 1


async def test_cookie_near_expiry_is_refreshed():
    fetch, calls = counting_fetcher(["v1", "v2"], ttl=30)  # pay (60 sn) içinde
    provider = HumanVerificationProvider(fetch_cookie=fetch)

    await provider.get_cookie()
    assert await provider.get_cookie() == f"{COOKIE_NAME}=v2"
    assert calls["count"] == 2


async def test_concurrent_requests_fetch_once():
    fetch, calls = counting_fetcher(["v1"])
    provider = HumanVerificationProvider(fetch_cookie=fetch)

    results = await asyncio.gather(*[provider.get_cookie() for _ in range(10)])

    assert set(results) == {f"{COOKIE_NAME}=v1"}
    assert calls["count"] == 1


async def test_stale_cookie_refreshes_only_once():
    fetch, calls = counting_fetcher(["v1", "v2"])
    provider = HumanVerificationProvider(fetch_cookie=fetch)
    rejected = await provider.get_cookie()

    results = await asyncio.gather(*[provider.get_cookie(stale=rejected) for _ in range(5)])

    assert set(results) == {f"{COOKIE_NAME}=v2"}
    assert calls["count"] == 2


def make_client(handler, values):
    client = EKAPClient()
    fetch, calls = counting_fetcher(values)
    client.human_verification = HumanVerificationProvider(fetch_cookie=fetch)
    client._transport = httpx.MockTransport(handler)
    return client, calls


async def test_request_sends_verification_cookie():
    seen = []

    def handler(request):
        seen.append(request.headers.get("cookie"))
        return httpx.Response(200, json={"list": []})

    client, _ = make_client(handler, ["v1"])
    assert await client._make_request("/x", {}) == {"list": []}
    assert seen == [f"{COOKIE_NAME}=v1"]


async def test_428_triggers_reverification_and_retry():
    seen = []

    def handler(request):
        cookie = request.headers.get("cookie")
        seen.append(cookie)
        if cookie == f"{COOKIE_NAME}=v1":
            return httpx.Response(428, json={"code": "HUMAN_VERIFICATION_REQUIRED"})
        return httpx.Response(200, json={"ok": True})

    client, calls = make_client(handler, ["v1", "v2"])
    assert await client._make_request("/x", {}) == {"ok": True}
    assert seen == [f"{COOKIE_NAME}=v1", f"{COOKIE_NAME}=v2"]
    assert calls["count"] == 2


async def test_persistent_428_raises():
    def handler(request):
        return httpx.Response(428, json={"code": "HUMAN_VERIFICATION_REQUIRED"})

    client, calls = make_client(handler, ["v1", "v2"])
    with pytest.raises(httpx.HTTPStatusError):
        await client._make_request("/x", {})
    assert calls["count"] == 2
