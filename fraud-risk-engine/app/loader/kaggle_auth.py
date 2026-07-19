"""Kaggle dataset downloader with QR-code authentication.

Supports two auth flows:
1. Username + Password (interactive)
2. QR-code scan via Kaggle Android/iOS app (no password needed)

Usage
-----
    python -m app.loader.kaggle_auth login          # interactive
    python -m app.loader.kaggle_auth download -d varshithkumaranand/banking-fruad-detection-dataset-with-99-accuracy -f Fraud.csv -o data/
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

try:
    from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PlaywrightTimeout
except ImportError as e:
    raise SystemExit(f"playwright not installed: pip install playwright && playwright install chromium\n{e}")

KAGGLE_CONFIG_DIR = Path.home() / ".kaggle"
TOKEN_PATH = KAGGLE_CONFIG_DIR / "access_token.json"
COOKIES_PATH = KAGGLE_CONFIG_DIR / "kaggle_cookies.json"


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _ensure_kaggle_config_dir() -> None:
    KAGGLE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _load_token() -> Optional[dict]:
    if TOKEN_PATH.exists():
        return json.loads(TOKEN_PATH.read_text())
    return None


def _load_cookies() -> Optional[list]:
    if COOKIES_PATH.exists():
        return json.loads(COOKIES_PATH.read_text())
    return None


def _save_token(token: dict) -> None:
    _ensure_kaggle_config_dir()
    TOKEN_PATH.write_text(json.dumps(token, indent=2))
    print(f"[auth] Token saved → {TOKEN_PATH}")


def _save_cookies(browser: Browser) -> None:
    _ensure_kaggle_config_dir()
    cookies = browser.contexts[0].add_cookies.__self__.storage_state() \
        if hasattr(browser.contexts[0], 'storage_state') else None
    if cookies is None:
        storage = {}
        for ctx in browser.contexts:
            storage['cookies'] = ctx.cookies()
        COOKIES_PATH.write_text(json.dumps(storage, indent=2))
    else:
        COOKIES_PATH.write_text(json.dumps(cookies, indent=2))
    print(f"[auth] Cookies saved → {COOKIES_PATH}")


# ---------------------------------------------------------------------------
# QR-code auth flow
# ---------------------------------------------------------------------------

def login_with_qr() -> bool:
    """Open Kaggle in browser, show QR code for Kaggle app scan, then capture session."""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--disable-web-security"])
        ctx = browser.new_context()
        page = ctx.new_page()

        # Go to Kaggle login
        page.goto("https://kaggle.com/account", timeout=30000)
        page.wait_for_load_state("networkidle")

        print("[auth] Waiting for you to scan the QR code with Kaggle app…")
        print("[auth] If QR code is not visible, look for the QR login option on the page.")

        # Wait for successful login — check for username element
        try:
            page.wait_for_selector(
                '[data-testid="user-name"], [href="/notifications"], .kaggle-avatar, [aria-label="Profile"]',
                timeout=120_000   # 2 minutes to scan
            )
            print("[auth] ✓ Login confirmed!")
        except PlaywrightTimeout:
            print("[auth] ✗ Timeout waiting for login. Please try again.")
            browser.close()
            return False

        # Save session cookies so kaggle CLI can use them
        _save_cookies(browser)
        _dump_auth_info(ctx, page)
        browser.close()
        return True


def login_with_credentials(username: str, key: str) -> bool:
    """Save kaggle credentials file (same format as the web token)."""
    _ensure_kaggle_config_dir()
    token = {"username": username, "key": key, "source": "cli"}
    _save_token(token)
    print(f"[auth] Credentials saved for user '{username}'")
    return True


# ---------------------------------------------------------------------------
# Auth info dumper
# ---------------------------------------------------------------------------

def _dump_auth_info(ctx, page: Page) -> None:
    try:
        title = page.title()
        url = page.url
        print(f"[auth] Page title : {title}")
        print(f"[auth] Page URL   : {url}")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def _kaggle_api_url(dataset: str, file: Optional[str] = None) -> str:
    parts = dataset.split("/")
    if len(parts) != 2:
        raise ValueError(f"Expected 'owner/dataset', got '{dataset}'")
    owner, name = parts
    if file:
        return f"https://www.kaggle.com/api/v1/datasets/download/{owner}/{name}?file={file}"
    return f"https://www.kaggle.com/api/v1/datasets/download/{owner}/{name}"


def download_dataset(
    dataset: str,
    file: Optional[str] = None,
    output_dir: str | Path = ".",
    token: Optional[dict] = None,
) -> Path:
    """Download a Kaggle dataset using stored or provided credentials."""

    token = token or _load_token()
    if not token:
        raise SystemExit(
            "No Kaggle credentials found.\n"
            "  Run: python -m app.loader.kaggle_auth login\n"
            "  Or: python -m app.loader.kaggle_auth credentials <username> <key>"
        )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[download] Dataset : {dataset}")
    print(f"[download] File    : {file or 'all'}")
    print(f"[download] Output  : {output_dir}")

    # Build request with token
    token_str = json.dumps(token).encode()
    req = urllib.request.Request(
        _kaggle_api_url(dataset, file),
        headers={
            "Authorization": f"Token {token_str.decode()}",
            "Content-Type": "application/json",
        },
        data=token_str,
    )

    tmp_zip = output_dir / "tmp_download.zip"
    print("[download] Downloading (this may take a while for large files)…")

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 1024 * 64
            with open(tmp_zip, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded * 100 // total
                        print(f"\r[download] {pct}% ({downloaded//1024}KB/{total//1024}KB)", end="", flush=True)
            print()
    except urllib.error.HTTPError as e:
        print(f"[download] HTTP error {e.code}: {e.reason}")
        print("[download] Make sure your token is valid and you accepted dataset terms.")
        raise SystemExit(1)

    print("[download] Extracting…")
    with zipfile.ZipFile(tmp_zip) as zf:
        zf.extractall(output_dir)
    tmp_zip.unlink()
    print(f"[download] ✓ Done — files in {output_dir}")
    return output_dir


def download_with_browser(
    dataset: str,
    file: Optional[str] = None,
    output_dir: str | Path = ".",
) -> Path:
    """Download using browser session (scan QR or already logged in)."""

    cookies = _load_cookies()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context()

        if cookies:
            try:
                ctx.add_cookies(cookies.get("cookies", cookies))
                print("[browser] Loaded saved cookies")
            except Exception as e:
                print(f"[browser] Could not load cookies: {e}")

        page = ctx.new_page()

        # Navigate to dataset page
        dataset_url = f"https://www.kaggle.com/datasets/{dataset}"
        print(f"[browser] Opening {dataset_url}…")
        page.goto(dataset_url, timeout=30000)
        page.wait_for_load_state("networkidle")

        # Try to click Download button
        try:
            download_btn = page.get_by_role("button", name="Download").first
            download_btn.click(timeout=5000)
            print("[browser] Download button clicked")
        except PlaywrightTimeout:
            print("[browser] Could not find Download button — you may need to log in first.")
            print("[browser] Run: python -m app.loader.kaggle_auth login")
            browser.close()
            raise SystemExit(1)

        # Wait for download to start
        time.sleep(3)
        browser.close()

    # Find downloaded file (browser default download dir)
    downloads = Path.home() / "Downloads"
    candidates = sorted(downloads.glob("*.zip")) + sorted(downloads.glob("*.csv"))
    if candidates:
        latest = candidates[-1]
        dest = output_dir / latest.name
        shutil.copy2(latest, dest)
        print(f"[browser] Copied {latest} → {dest}")
        return dest
    else:
        print("[browser] No file found in ~/Downloads")
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Kaggle auth + download tool")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # login subcommand
    login_p = sub.add_parser("login", help="Login via QR code (opens browser)")
    login_p.add_argument("--headless", action="store_true", help="Run browser headless")

    # credentials subcommand
    cred_p = sub.add_parser("credentials", help="Save username+key credentials")
    cred_p.add_argument("username", help="Kaggle username")
    cred_p.add_argument("key", help="Kaggle API key")

    # download subcommand
    dl_p = sub.add_parser("download", help="Download a dataset")
    dl_p.add_argument("-d", "--dataset", required=True, help="Dataset in owner/name format")
    dl_p.add_argument("-f", "--file", help="Specific file to download")
    dl_p.add_argument("-o", "--output", default="data", help="Output directory")
    dl_p.add_argument("--browser", action="store_true", help="Use browser session instead of API token")

    args = parser.parse_args(argv)

    if args.cmd == "login":
        success = login_with_qr()
        return 0 if success else 1

    elif args.cmd == "credentials":
        login_with_credentials(args.username, args.key)
        return 0

    elif args.cmd == "download":
        if args.browser:
            path = download_with_browser(args.dataset, args.file, args.output)
        else:
            path = download_dataset(args.dataset, args.file, args.output)
        print(f"[done] {path}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
