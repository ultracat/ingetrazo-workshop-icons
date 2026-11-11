#!/usr/bin/env python3
"""Install the «Workshop Color» icon theme for IngeTrazo in one step.

    python3 install.py              # install the theme and switch to it
    python3 install.py --uninstall  # remove it and go back to IngeTrazo's icons

Without a copy of this repository, straight from GitHub:

    curl -fsSL https://raw.githubusercontent.com/ultracat/ingetrazo-workshop-icons/main/install.py | python3 -

(Windows: download install.py and run ``py install.py``.)

What it does:

1. Finds IngeTrazo's per-user folder, as IngeTrazo does:
   ``%APPDATA%\\ingetrazo`` on Windows, ``$XDG_DATA_HOME/ingetrazo`` or
   ``~/.local/share/ingetrazo`` elsewhere (macOS included).
2. If the Custom Icons extension is missing, offers to install it: version
   1.1 from its author's repository, checked against the SHA-256 listed in
   IngeTrazo's extension catalogue.
3. Copies ``Workshop Color`` into ``custom_icons/Icônes custom/``. An older
   copy of it is replaced; other themes are left alone.
4. Makes it the theme in use (``custom_icons/settings.json``).

Restart IngeTrazo afterwards. Only the Python standard library is used.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unicodedata
import urllib.request
import zipfile
from pathlib import Path

THEME = "Workshop Color"
REPO_ZIP = "https://github.com/ultracat/ingetrazo-workshop-icons/archive/refs/heads/main.zip"
EXT_ZIP = ("https://raw.githubusercontent.com/APBureauEtude/ingetrazo-custom-icons/"
           "v1.1/dist/custom_icons-1.1.zip")
EXT_SHA256 = "a1e64734ac8797ebbfe3b6a1fc3d8755cffa9e8a2047ee4ffda26d22a3847e42"
CUSTOM = "Icônes custom"           # the extension's own folder names
ORIGINALS = "Icônes originales"
SETTINGS = "settings.json"


def say(msg: str) -> None:
    print(msg, flush=True)


def ingetrazo_dir() -> Path:
    """IngeTrazo's per-user data folder (as core.extensions.user_plugins_dir)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "ingetrazo"


def child(folder: Path, name: str) -> Path:
    """``folder/name``, matching an existing entry whatever its Unicode form
    (macOS may store «Icônes» decomposed)."""
    want = unicodedata.normalize("NFC", name)
    try:
        for entry in folder.iterdir():
            if unicodedata.normalize("NFC", entry.name) == want:
                return entry
    except OSError:
        pass
    return folder / name


def ask(question: str, default_yes: bool, assume_yes: bool) -> bool:
    """A yes/no answer. With no one to answer (no terminal), «no»: run
    again with --yes to agree in advance."""
    if assume_yes:
        return True
    prompt = question + (" [Y/n] " if default_yes else " [y/N] ")
    try:
        if sys.stdin is not None and sys.stdin.isatty():
            line = input(prompt)
        else:
            # Piped from curl: stdin is this script, so ask the terminal.
            with open("/dev/tty") as tty:
                print(prompt, end="", flush=True)
                line = tty.readline()
                if not line:                # end of input: nobody there
                    raise EOFError
    except (OSError, EOFError):
        say("  (no answer possible here: run again with --yes to agree)")
        return False
    answer = line.strip().lower()
    return default_yes if not answer else answer.startswith("y")


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "workshop-icons-installer"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def theme_source(tmp: Path) -> Path:
    """The ``Workshop Color`` folder: beside this script, else downloaded."""
    here = Path(__file__).resolve().parent if "__file__" in globals() and Path(__file__).is_file() else None
    if here and (here / THEME / "mapping.json").is_file():
        return here / THEME
    say("Downloading the theme from GitHub…")
    with zipfile.ZipFile(io.BytesIO(download(REPO_ZIP))) as z:
        z.extractall(tmp)
    for found in tmp.glob(f"*/{THEME}/mapping.json"):
        return found.parent
    sys.exit("The downloaded archive has no «%s» folder." % THEME)


def install_extension(plugins: Path) -> None:
    say("Downloading the Custom Icons extension 1.1…")
    data = download(EXT_ZIP)
    digest = hashlib.sha256(data).hexdigest()
    if digest != EXT_SHA256:
        sys.exit(f"Custom Icons: unexpected SHA-256 {digest}; nothing installed.")
    plugins.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        if not names or any(not n.startswith("custom_icons/") or ".." in n for n in names):
            sys.exit("Custom Icons: unexpected archive layout; nothing installed.")
        z.extractall(plugins)
    say(f"  installed in {plugins / 'custom_icons'}")


def write_settings(root: Path, theme: str | None) -> None:
    path = root / SETTINGS
    if path.is_file():
        shutil.copy2(path, path.with_suffix(".json.bak"))
    path.write_text(json.dumps({"theme": theme}, indent=1) + "\n", encoding="utf-8")


def install(args) -> None:
    base = ingetrazo_dir()
    plugins = base / "plugins"
    root = base / "custom_icons"
    if not (plugins / "custom_icons" / "__init__.py").is_file():
        say("The Custom Icons extension is not installed (it switches IngeTrazo's icons).")
        if ask("Install it now?", True, args.yes):
            install_extension(plugins)
        else:
            sys.exit("Install Custom Icons first: "
                     "https://github.com/APBureauEtude/ingetrazo-custom-icons")
    with tempfile.TemporaryDirectory() as tmp:
        src = theme_source(Path(tmp))
        custom = child(root, CUSTOM)
        dest = custom / THEME
        custom.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            say(f"Replacing the older copy in {dest}")
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
    mapping = json.loads((dest / "mapping.json").read_text(encoding="utf-8"))
    say(f"Theme copied: {len(mapping.get('icons', {}))} icons, "
        f"{len(mapping.get('cursors', {}))} cursors → {dest}")
    write_settings(root, THEME)
    say(f"«{THEME}» is now the theme in use.")
    if not child(root, ORIGINALS).is_dir():
        say("Start IngeTrazo once so the extension finishes setting itself up.")
    say("Restart IngeTrazo to see it. To switch back: "
        "Extensions ▸ Custom icons ▸ Choose icons… ▸ None.")


def uninstall(args) -> None:
    root = ingetrazo_dir() / "custom_icons"
    dest = child(root, CUSTOM) / THEME
    if dest.exists():
        shutil.rmtree(dest)
        say(f"Removed {dest}")
    else:
        say("The theme is not installed.")
    settings = root / SETTINGS
    try:
        current = json.loads(settings.read_text(encoding="utf-8")).get("theme")
    except (OSError, ValueError, AttributeError):
        current = None
    if current == THEME:
        write_settings(root, None)
        say("Back to IngeTrazo's own icons. Restart IngeTrazo.")


def main() -> None:
    p = argparse.ArgumentParser(description=f"Install the «{THEME}» icon theme for IngeTrazo.")
    p.add_argument("--uninstall", action="store_true", help="remove the theme")
    p.add_argument("-y", "--yes", action="store_true", help="answer yes to every question")
    args = p.parse_args()
    (uninstall if args.uninstall else install)(args)


if __name__ == "__main__":
    main()
