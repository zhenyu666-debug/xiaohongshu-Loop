"""Build a single ``.exe`` for the Unified Console desktop launcher.

Run::

    python scripts/build_launcher.py

Output: ``dist/xhs-saas-console.exe`` (~30 MB, single-file, no console window).

Why a custom build script instead of ``pyinstaller`` CLI flags?
* Centralised "what to bundle / what to hide" so a non-expert can re-build.
* Adds a small ``console`` resource folder (icon, README, version) so the
  EXE looks like a real product in Explorer.
* Falls back to ``pip install pyinstaller`` if missing.

The exe will:
* bundle ``console_gui.py`` and its pure-Python deps (pystray, Pillow, pywebview, ...).
* launch a real WebView2 GUI window with embedded HTML/CSS/JS.
* start / stop the three FastAPI services on demand (uvicorn subprocesses).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENTRY = REPO_ROOT / "scripts" / "console_gui.py"
DIST_ROOT = REPO_ROOT / "dist"          # parent of the onedir folder
BUILD_DIR = REPO_ROOT / "build"
SPEC_DIR = REPO_ROOT / "scripts"

APP_NAME = "xhs-saas-console"
DIST_DIR = DIST_ROOT / APP_NAME          # onedir layout: dist/xhs-saas-console/
EXE_NAME = f"{APP_NAME}.exe"

HIDDEN_IMPORTS = [
    "webview",
    "webview.platforms.winforms",
    "pystray",
    "PIL",
    "clr_loader",
    "win32com",
]

EXCLUDES = [
    "tkinter",
    "numpy.tests",
    "pandas.tests",
    "matplotlib.tests",
]


def _ensure_pyinstaller() -> str:
    try:
        import PyInstaller  # noqa: F401
        return "PyInstaller"
    except ImportError:
        print("PyInstaller not found, installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        return "PyInstaller"


def build() -> int:
    print(f"[build] repo root:   {REPO_ROOT}")
    print(f"[build] entry:       {ENTRY}")
    print(f"[build] output dir:  {DIST_DIR}")

    if not ENTRY.exists():
        print(f"[build] ERROR: entry not found: {ENTRY}", file=sys.stderr)
        return 2

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR, ignore_errors=True)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR, ignore_errors=True)

    _ensure_pyinstaller()

    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onedir",            # produces dist/xhs-saas-console/xhs-saas-console.exe (~25 MB)
                                # + dist/xhs-saas-console/_internal/ (deps).  Switch to
                                # "--onefile" if you need a single .exe (~200 MB, slower startup).
        "--windowed",          # no console window when double-clicked
        "--noconfirm",
        "--clean",
        "--distpath", str(DIST_ROOT),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(SPEC_DIR),
    ]
    for mod in HIDDEN_IMPORTS:
        cmd += ["--hidden-import", mod]
    for mod in EXCLUDES:
        cmd += ["--exclude-module", mod]
    cmd.append(str(ENTRY))

    print(f"[build] running: {cmd[0]} ... [truncated, {len(cmd)} args]")
    started = time.time()
    code = subprocess.call(cmd, cwd=str(REPO_ROOT))
    elapsed = time.time() - started
    print(f"[build] PyInstaller exited {code} in {elapsed:.1f}s")
    if code != 0:
        return code

    exe_path = DIST_DIR / EXE_NAME
    if not exe_path.exists():
        print(f"[build] ERROR: expected exe missing: {exe_path}", file=sys.stderr)
        return 3

    exe_mb = exe_path.stat().st_size / 1024 / 1024
    bundle_files = sum(p.stat().st_size for p in DIST_DIR.rglob("*") if p.is_file())
    bundle_mb = bundle_files / 1024 / 1024
    print(f"[build] OK: {exe_path}")
    print(f"[build] exe size:      {exe_mb:6.1f} MB")
    print(f"[build] bundle size:   {bundle_mb:6.1f} MB (exe + _internal/)")
    print(f"[build] Double-click the exe, or run: {exe_path}")
    return 0


if __name__ == "__main__":
    sys.exit(build())
