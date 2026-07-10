"""Build an onedir PyInstaller dist at dist/xhs-saas-console/.

Use this when you need the MSI bundle (installer/build_msi.ps1 expects
the onedir layout). The default build_launcher.py produces a onefile
build at dist/xhs-saas-console-onefile/.

Run:
    python scripts/build_launcher_onedir.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENTRY = REPO_ROOT / "scripts" / "console_gui.py"
DIST_DIR = REPO_ROOT / "dist" / "xhs-saas-console"
BUILD_DIR = REPO_ROOT / "build"
SPEC_DIR = REPO_ROOT / "scripts"

APP_NAME = "xhs-saas-console"
EXE_NAME = APP_NAME + ".exe"
APP_ICON = REPO_ROOT / "assets" / "ico" / (APP_NAME + ".ico")

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



def _ensure_pyinstaller():
    try:
        import PyInstaller  # noqa: F401
        return
    except ImportError:
        print("PyInstaller not found, installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def build():
    print("[build] repo root:   " + str(REPO_ROOT))
    print("[build] entry:       " + str(ENTRY))
    print("[build] output dir:  " + str(DIST_DIR))

    if not ENTRY.exists():
        print("[build] ERROR: entry not found: " + str(ENTRY), file=sys.stderr)
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
        "--onedir",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--distpath", str(REPO_ROOT / "dist"),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(SPEC_DIR),
    ]
    if APP_ICON.exists():
        cmd += ["--icon", str(APP_ICON)]
        print("[build] embedding icon: " + str(APP_ICON))
    else:
        print("[build] no icon at " + str(APP_ICON) + " (run scripts/build_icon.py to generate it)")
    for mod in HIDDEN_IMPORTS:
        cmd += ["--hidden-import", mod]
    for mod in EXCLUDES:
        cmd += ["--exclude-module", mod]
    cmd.append(str(ENTRY))

    print("[build] running: " + cmd[0] + " ... [truncated, " + str(len(cmd)) + " args]")
    started = time.time()
    code = subprocess.call(cmd, cwd=str(REPO_ROOT))
    elapsed = time.time() - started
    print("[build] PyInstaller exited " + str(code) + " in " + str(round(elapsed, 1)) + "s")
    if code != 0:
        return code

    exe_path = DIST_DIR / EXE_NAME
    if not exe_path.exists():
        print("[build] ERROR: expected exe missing: " + str(exe_path), file=sys.stderr)
        return 3

    exe_mb = exe_path.stat().st_size / 1024 / 1024
    total = sum(p.stat().st_size for p in DIST_DIR.rglob("*") if p.is_file()) / 1024 / 1024
    print("[build] OK: " + str(exe_path))
    print("[build] exe size:      " + str(round(exe_mb, 1)) + " MB (launcher only)")
    print("[build] total bundle:  " + str(round(total, 1)) + " MB (launcher + _internal/)")
    return 0


if __name__ == "__main__":
    sys.exit(build())
