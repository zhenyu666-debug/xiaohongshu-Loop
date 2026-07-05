"""Rebuild dist/xhs-saas-console/ as onedir with the application .ico embedded.

Mirrors scripts/build_launcher.py but in onedir mode (no --onefile) and points
the output at dist/xhs-saas-console/ so installer\\build_msi.ps1 can stage it.

Run::

    python scripts\\_rebuild_onedir_once.py

Output:
    dist/xhs-saas-console/xhs-saas-console.exe        (~5-15 MB launcher)
    dist/xhs-saas-console/_internal/PyInstaller archive with the bundled deps

Why this script exists separately:
  * scripts/build_launcher.py is onefile-only and writes to dist/xhs-saas-console-onefile/.
  * installer/build_msi.ps1 hard-codes $DistDir = dist\\xhs-saas-console (onedir).
  * We want a single source of truth for "what to bundle" so the onedir build
    matches the onefile build in deps / icon / runtime-tmpdir.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENTRY = REPO_ROOT / "scripts" / "console_gui.py"
APP_ICON = REPO_ROOT / "assets" / "ico" / "xhs-saas-console.ico"

APP_NAME = "xhs-saas-console"
# IMPORTANT: --distpath=dist/ (the repo root's dist/) + --name=xhs-saas-console
# yields dist/xhs-saas-console/ — i.e. one level above --distpath. We then set
# DIST_DIR (the variable the rest of the script compares against) to the SAME
# path so the verification step at the end is correct.
DIST_DIR = REPO_ROOT / "dist" / APP_NAME       # dist/xhs-saas-console/  (onedir)
DIST_ARG = REPO_ROOT / "dist"                 # --distpath = dist/
BUILD_DIR = REPO_ROOT / "build"
SPEC_DIR = REPO_ROOT / "scripts"
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


def _ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller not found, installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def build() -> int:
    print(f"[onedir] repo root:   {REPO_ROOT}")
    print(f"[onedir] entry:       {ENTRY}")
    print(f"[onedir] output dir:  {DIST_DIR}")

    if not ENTRY.exists():
        print(f"[onedir] ERROR: entry not found: {ENTRY}", file=sys.stderr)
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
        "--onedir",            # dir layout, not single file
        "--windowed",          # no console window when double-clicked
        "--noconfirm",
        "--clean",
        "--runtime-tmpdir", f"%LOCALAPPDATA%\\{APP_NAME}\\runtime",
        "--distpath", str(DIST_ARG),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(SPEC_DIR),
    ]

    if APP_ICON.exists():
        cmd += ["--icon", str(APP_ICON)]
        print(f"[onedir] embedding icon: {APP_ICON}")
    else:
        print(f"[onedir] no icon at {APP_ICON} (run scripts/build_icon.py to generate it)")

    for mod in HIDDEN_IMPORTS:
        cmd += ["--hidden-import", mod]
    for mod in EXCLUDES:
        cmd += ["--exclude-module", mod]

    cmd.append(str(ENTRY))

    print(f"[onedir] running: {cmd[0]} ... [{len(cmd)} args]")
    started = time.time()
    code = subprocess.call(cmd, cwd=str(REPO_ROOT))
    elapsed = time.time() - started
    print(f"PYI_EXIT={code} ELAPSED={elapsed:.1f}")
    if code != 0:
        return code

    exe_path = DIST_DIR / EXE_NAME
    if not exe_path.exists():
        print(f"[onedir] ERROR: expected exe missing: {exe_path}", file=sys.stderr)
        return 3

    exe_bytes = exe_path.stat().st_size
    print(f"EXE= {exe_path} EXISTS= {exe_path.exists()} BYTES= {exe_bytes}")
    print(f"[onedir] size:  {exe_bytes / 1024 / 1024:6.2f} MB (onedir launcher only; _internal/ holds the rest)")
    return 0


if __name__ == "__main__":
    sys.exit(build())