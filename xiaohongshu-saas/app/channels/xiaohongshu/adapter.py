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
_PUBLISH_URL = "https://creator.xiaohongshu.com/publish/publisher?source=official"


class XiaohongshuAdapter(ChannelAdapter):
    name = "xiaohongshu"

    def __init__(self) -> None:
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._contexts: dict[str, BrowserContext] = {}
        self._rotate_counter: dict[str, int] = {}

    # ---------- lifecycle ----------

    async def _browser(self) -> Browser:
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
        browser = await self._browser()
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()
        await page.goto(_LOGIN_URL, wait_until="domcontentloaded")
        # Wait up to 2 minutes for the user to scan the QR code.
        try:
            await page.wait_for_url("**/creator.xiaohongshu.com/new/home**", timeout=120_000)
        except Exception as exc:
            await page.close()
            await context.close()
            raise AccountError(f"login timeout: {exc}") from exc

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
        browser = await self._browser()
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
        await page.goto(_PUBLISH_URL, wait_until="domcontentloaded")
        await self._human_delay()

        # Wait for creator center
        try:
            await page.wait_for_selector(Selectors.PUBLISH_TAB, timeout=15_000)
        except Exception as exc:
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
        loc = page.locator(Selectors.TOPIC_INPUT)
        await loc.fill(topic)
        await loc.press("Enter")

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