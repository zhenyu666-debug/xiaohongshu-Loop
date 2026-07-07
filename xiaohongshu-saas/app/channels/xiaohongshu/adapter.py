"""Xiaohongshu (Little Red Book) channel adapter.

Implementation notes
--------------------
- Uses Playwright (Chromium) to drive the creator web UI.
- Cookies are persisted per-account as JSON files under ``data/cookies/<account_id>.json``.
- Anti-detection: human-like random delays + optional proxy + rotate context every N posts.
- This adapter is intentionally written to be *robust to UI changes*:
  selectors are isolated in ``selectors.py`` so they can be tweaked in one place.
- DO NOT use this to spam or violate Xiaohongshu's platform rules.
"""
from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path
from typing import Optional

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from app.channels.base import ChannelAdapter
from app.core.config import settings
from app.core.errors import AccountError, PublishError
from app.core.logging import logger
from app.core.types import AccountHealth, ContentItem, PublishResult
from app.models import Account

from .selectors import Selectors


_COOKIE_DIR = Path("data/cookies")
_COOKIE_DIR.mkdir(parents=True, exist_ok=True)

_LOGIN_URL = "https://creator.xiaohongshu.com/"
_PUBLISH_URL = "https://creator.xiaohongshu.com/publish"


class XiaohongshuAdapter(ChannelAdapter):
    name = "xiaohongshu"

    def __init__(self) -> None:
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._contexts: dict[str, BrowserContext] = {}
        self._rotate_counter: dict[str, int] = {}

    # ---------- lifecycle ----------

    async def _get_browser(self) -> Browser:
        if self._browser is None:
            self._pw = await async_playwright().start()
            launch_kwargs: dict = {"headless": True}
            if settings.app_env == "dev":
                launch_kwargs["headless"] = False  # easier debugging
            self._browser = await self._pw.chromium.launch(**launch_kwargs)
        return self._browser

    async def shutdown(self) -> None:
        for ctx in list(self._contexts.values()):
            try:
                await ctx.close()
            except Exception:
                pass
        self._contexts.clear()
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        self._browser = None
        self._pw = None

    # ---------- cookie ----------

    def cookie_path_for(self, account_id: str) -> Path:
        path = _COOKIE_DIR / f"{account_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    async def login(self, account: Account) -> None:
        """Open a (typically headed) browser, let the user scan the QR code,
        then persist cookies. After first login, subsequent calls reuse cookies."""
        browser = await self._get_browser()
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()
        await page.goto(_LOGIN_URL, wait_until="domcontentloaded")
        # Wait up to 10 minutes for the user to scan the QR code.
        try:
            await page.wait_for_url("**/creator.xiaohongshu.com/new/home**", timeout=600_000)
        except Exception as exc:
            await page.close()
            await context.close()
            raise AccountError(f"login timeout: {exc}") from exc

        # Give the SPA time to finish setting all session cookies (auth round-trips,
        # customer-sso handshake, fingerprint cookies, etc.).
        try:
            await page.wait_for_load_state("networkidle", timeout=20_000)
        except Exception:
            pass
        # And a small settle delay before capturing the cookie jar.
        await asyncio.sleep(3)

        cookies = await context.cookies()
        cookie_path = self.cookie_path_for(account.id)
        cookie_path.write_text(json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8")
        account.cookie_path = str(cookie_path)
        account.stage = "warmup"
        logger.success("Account {} logged in; cookies saved to {}", account.id, cookie_path)

        await page.close()
        await context.close()

    async def _load_context(self, account: Account) -> BrowserContext:
        if account.id in self._contexts:
            return self._contexts[account.id]
        browser = await self._get_browser()
        cookie_path = Path(account.cookie_path) if account.cookie_path else self.cookie_path_for(account.id)
        if not cookie_path.exists():
            raise AccountError(f"no cookies for account {account.id}; call login() first")

        proxy = None
        if account.proxy:
            proxy = {"server": account.proxy}

        context = await browser.new_context(viewport={"width": 1440, "height": 900}, proxy=proxy)
        cookies = json.loads(cookie_path.read_text(encoding="utf-8"))
        await context.add_cookies(cookies)
        self._contexts[account.id] = context
        return context

    async def _maybe_rotate(self, account: Account) -> BrowserContext:
        self._rotate_counter[account.id] = self._rotate_counter.get(account.id, 0) + 1
        if self._rotate_counter[account.id] >= settings.proxy_rotate_every:
            ctx = self._contexts.pop(account.id, None)
            if ctx:
                await ctx.close()
            self._rotate_counter[account.id] = 0
            return await self._load_context(account)
        return self._contexts[account.id]

    # ---------- publish ----------

    async def publish(self, account: Account, content: ContentItem) -> PublishResult:
        try:
            context = await self._load_context(account)
            context = await self._maybe_rotate(account)
            page = await context.new_page()
            try:
                return await self._do_publish(page, content)
            finally:
                await page.close()
        except AccountError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("publish failed for {}", account.id)
            return PublishResult(success=False, error=str(exc))

    async def _do_publish(self, page: Page, content: ContentItem) -> PublishResult:
        # /publish directly bounces to /login (cookie not yet proven), so go to
        # the creator dashboard first; once we're on /new/home, click the
        # "发布图文笔记" tile to land on the real /publish/publish page.
        await page.goto("https://creator.xiaohongshu.com/new/home", wait_until="domcontentloaded")
        await self._human_delay()

        # The SPA does an async auth check that may bounce us to /login then
        # back to /new/home, then we need to click "发布图文笔记" to reach the
        # actual publish form. Loop with a longer budget while the URL settles.
        try:
            await self._navigate_to_publish_form(page, total_timeout=180_000)
        except Exception as exc:
            try:
                body = await page.content()
                logger.error("publish form wait timeout. url={} title={}", page.url, await page.title())
                logger.error("body bytes={} excerpt={}", len(body), body[:600])
            except Exception:  # noqa: BLE001
                pass
            raise PublishError(f"publisher page not ready: {exc}") from exc

        # 1) upload images (or video)
        if content.images:
            await self._upload_images(page, content.images)
        elif content.video:
            await self._upload_video(page, content.video)

        # 2) title + body
        await self._fill_title(page, content.title)
        if content.body:
            await self._fill_body(page, content.body)
        await self._human_delay()

        # 3) topics
        for topic in content.topics:
            await self._add_topic(page, topic)
            await self._human_delay(300, 900)

        # 4) submit
        await page.click(Selectors.SUBMIT_BUTTON)
        # wait for success indicator
        try:
            await page.wait_for_selector(Selectors.SUCCESS_TOAST, timeout=20_000)
        except Exception as exc:
            raise PublishError(f"submit did not succeed: {exc}") from exc

        return PublishResult(
            success=True,
            url=page.url,
            published_at=__import__("datetime").datetime.utcnow(),
            raw={"title": content.title},
        )

    async def _navigate_to_publish_form(self, page: Page, total_timeout: int = 120_000) -> None:
        """Bring the page to a state where the publish form is rendered and active.

        The Xiaohongshu creator SPA does an async auth check that may bounce us
        from /publish → /login → /new/home. We force the navigation ourselves
        (the auto-redirect can take ~60s and is unreliable) and click into the
        publisher via "发布图文笔记". Once on /publish/publish?target=image the
        form renders with title/body/submit controls.
        """
        import asyncio as _asyncio
        deadline = _asyncio.get_event_loop().time() + total_timeout / 1000.0
        # If we land on /login or just /publish with no auth, force the
        # creator-dashboard route to trigger the auth check ourselves.
        for _ in range(8):
            url = page.url
            if "/login" in url:
                logger.info("auth-check landing on /login; navigating to /new/home")
                await page.goto("https://creator.xiaohongshu.com/new/home", wait_until="domcontentloaded")
                await _asyncio.sleep(2)
                break
            await _asyncio.sleep(2)

        last_url = page.url
        while _asyncio.get_event_loop().time() < deadline:
            url = page.url
            # The publisher URL pattern we care about
            if "/publish/publish" in url:
                # Wait for the title input (more reliable than hidden file input)
                try:
                    await page.wait_for_selector(
                        'input[placeholder^="填写标题"], input[placeholder*="标题"]',
                        state="visible", timeout=10_000,
                    )
                    logger.info("publish form ready at {}", url)
                    return
                except Exception:
                    pass
            # On dashboard, click the publish note button
            try:
                btn = page.locator("text=发布图文笔记").first
                if await btn.count() > 0 and await btn.is_visible():
                    logger.info("clicking 发布图文笔记 from {}", url)
                    await btn.click(timeout=5_000)
                    await _asyncio.sleep(3)
                    continue
            except Exception:
                pass
            if url != last_url:
                logger.info("page navigated {} -> {}", last_url, url)
                last_url = url
            await _asyncio.sleep(1.0)
        raise TimeoutError(f"publish form did not appear within {total_timeout}ms; last url={page.url}")

    async def _upload_images(self, page: Page, images: list[str]) -> None:
        # The file input is hidden but always present in the DOM.
        file_input = page.locator(Selectors.FILE_INPUT).first
        await file_input.set_input_files(images)
        await page.wait_for_selector(Selectors.UPLOAD_PROGRESS_DONE, timeout=60_000)

    async def _upload_video(self, page: Page, video: str) -> None:
        file_input = page.locator(Selectors.VIDEO_FILE_INPUT).first
        await file_input.set_input_video(video) if hasattr(file_input, "set_input_video") else await file_input.set_input_files(video)
        await page.wait_for_selector(Selectors.UPLOAD_PROGRESS_DONE, timeout=180_000)

    async def _fill_title(self, page: Page, title: str) -> None:
        loc = page.locator(Selectors.TITLE_INPUT)
        await loc.click()
        await loc.fill(title[:30])  # XHS title limit

    async def _fill_body(self, page: Page, body: str) -> None:
        loc = page.locator(Selectors.BODY_EDITOR)
        await loc.click()
        # Insert plain text (avoid paste-detect by typing in chunks)
        chunk_size = 30
        for i in range(0, len(body), chunk_size):
            await loc.type(body[i : i + chunk_size], delay=random.randint(20, 60))

    async def _add_topic(self, page: Page, topic: str) -> None:
        # Topic input is optional; if not present in this UI variant, skip silently.
        if not getattr(self, "_topics_enabled", True):
            return
        try:
            loc = page.locator(Selectors.TOPIC_INPUT)
            if await loc.count() == 0:
                logger.info("topic input not present; skipping topic {}", topic)
                # Fall back: append topic to body or disable for the run
                self._topics_enabled = False
                return
            await loc.fill(topic)
            await loc.press("Enter")
            await self._human_delay(300, 900)
        except Exception as exc:
            logger.warning("failed to add topic {}: {}", topic, exc)
            self._topics_enabled = False

    # ---------- heartbeat ----------

    async def heartbeat(self, account: Account) -> AccountHealth:
        try:
            context = await self._load_context(account)
            page = await context.new_page()
            try:
                resp = await page.goto(_LOGIN_URL, wait_until="domcontentloaded")
                ok = bool(resp and resp.ok)
                # If we were redirected back to login, cookies are invalid
                if "login" in page.url:
                    return AccountHealth(ok=False, cookies_valid=False, message="redirected to login")
                return AccountHealth(ok=ok, cookies_valid=True, message="ok")
            finally:
                await page.close()
        except Exception as exc:  # noqa: BLE001
            return AccountHealth(ok=False, cookies_valid=False, message=str(exc))

    # ---------- helpers ----------

    async def _human_delay(self, lo: Optional[int] = None, hi: Optional[int] = None) -> None:
        lo = lo or settings.human_delay_min_ms
        hi = hi or settings.human_delay_max_ms
        ms = random.randint(lo, hi)
        await asyncio.sleep(ms / 1000.0)