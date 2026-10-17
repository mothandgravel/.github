"""Follow the desktop's light or dark setting where it can be read, without blocking.

Each probe is read-only, bounded by a short timeout and returns ``None`` when the
platform gives no answer. Studio then keeps its light (Paper) identity. A reader's
explicit choice in the menu always wins over the system setting.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path

CHOICES = ("system", "light", "night")
_PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"


def _run(command: list[str], timeout: float = 1.5) -> str | None:
    if shutil.which(command[0]) is None:
        return None
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return None
    return completed.stdout if completed.returncode == 0 else None


def _windows() -> bool | None:
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _PERSONALIZE) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
    except OSError:
        return None
    return value == 0


def _wsl_host() -> bool | None:
    """Under WSLg the Windows app setting is the one the reader actually chose."""
    try:
        release = Path("/proc/sys/kernel/osrelease").read_text(encoding="utf-8").lower()
    except OSError:
        return None
    if "microsoft" not in release:
        return None
    output = _run(["reg.exe", "query", "HKCU\\" + _PERSONALIZE, "/v", "AppsUseLightTheme"], 3)
    if not output:
        return None
    for line in output.splitlines():
        if "AppsUseLightTheme" in line:
            value = line.split()[-1]
            try:
                return int(value, 16) == 0
            except ValueError:
                return None
    return None


def _macos() -> bool | None:
    output = _run(["defaults", "read", "-g", "AppleInterfaceStyle"])
    if output is None:
        # The key is absent in light mode, which makes `defaults` fail.
        return False if shutil.which("defaults") else None
    return "dark" in output.lower()


def _portal() -> bool | None:
    """freedesktop appearance portal, used by GNOME and KDE Plasma alike."""
    output = _run(
        [
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.freedesktop.portal.Desktop",
            "--object-path",
            "/org/freedesktop/portal/desktop",
            "--method",
            "org.freedesktop.portal.Settings.Read",
            "org.freedesktop.appearance",
            "color-scheme",
        ]
    )
    if not output:
        return None
    # "(<<uint32 1>>,)": 1 prefers dark, 2 prefers light, 0 has no preference.
    digits = [part for part in output.replace(">", " ").split() if part.rstrip(",)").isdigit()]
    if not digits:
        return None
    value = int(digits[-1].rstrip(",)"))
    return {1: True, 2: False}.get(value)


def _gsettings() -> bool | None:
    scheme = _run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"])
    if scheme and "prefer-dark" in scheme:
        return True
    if scheme and "prefer-light" in scheme:
        return False
    theme = _run(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"])
    if theme:
        return "dark" in theme.lower()
    return None


def _kde() -> bool | None:
    for command in ("kreadconfig6", "kreadconfig5"):
        output = _run([command, "--group", "General", "--key", "ColorScheme"])
        if output and output.strip():
            return "dark" in output.lower()
    path = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "kdeglobals"
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("ColorScheme="):
                return "dark" in line.lower()
    except OSError:
        return None
    return None


def system_prefers_dark() -> bool | None:
    """True for a dark desktop, False for light, None when the setting is unreadable."""
    system = platform.system()
    if system == "Windows":
        probes = (_windows,)
    elif system == "Darwin":
        probes = (_macos,)
    else:
        probes = (_wsl_host, _portal, _gsettings, _kde)
    for probe in probes:
        try:
            answer = probe()
        except Exception:
            answer = None
        if answer is not None:
            return answer
    return None


def resolve(choice: str, system_dark: bool | None) -> str:
    """The palette to show for a stored choice and what the system reported."""
    if choice == "night":
        return "night"
    if choice == "light":
        return "light"
    return "night" if system_dark else "light"
