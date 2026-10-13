"""Fake `mmsg` and `wlr-randr` on PATH, fed by mango output captured on a real session.

The fixtures come from `mmsg get all-monitors|all-clients` on a T14 under mango
0.17.5 (2026-10-06), trimmed and with a second monitor added. Every call is
appended to calls.log so tests can assert what was dispatched.
"""

import importlib.util
import os
import stat
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(ROOT / "src"))

# `import caelestia` loads the whole CLI. The mango tests use none of the image
# code, so where pillow or materialyoucolor are not installed empty stand-ins
# let the package import; where they are installed the real ones are used.
STUBS = {
    "PIL": ["Image", "UnidentifiedImageError"],
    "PIL.Image": ["Image", "Resampling", "open"],
    "materialyoucolor": [],
    "materialyoucolor.hct": ["Hct"],
    "materialyoucolor.utils": [],
    "materialyoucolor.utils.color_utils": ["argb_from_rgb", "rgba_from_argb", "rgb_from_argb"],
    "materialyoucolor.dynamiccolor": [],
    "materialyoucolor.dynamiccolor.material_dynamic_colors": ["MaterialDynamicColors"],
    "materialyoucolor.quantize": ["QuantizeCelebi"],
    "materialyoucolor.score": [],
    "materialyoucolor.score.score": ["Score"],
    "materialyoucolor.scheme": [],
}


def _stub_missing() -> None:
    for root in ("PIL", "materialyoucolor"):
        if importlib.util.find_spec(root) is not None:
            continue
        for name, attrs in STUBS.items():
            if name == root or name.startswith(root + "."):
                module = types.ModuleType(name)
                module.__path__ = []
                module.__getattr__ = lambda attr: type(attr, (), {})
                for attr in attrs:
                    setattr(module, attr, type(attr, (), {}))
                sys.modules[name] = module


_stub_missing()

MMSG = """#!/bin/sh
printf '%s\\n' "$*" >> "$FAKE_DIR/calls.log"
case "$1 $2" in
    "get all-monitors") cat "$FIXTURES/all-monitors.json" ;;
    "get all-clients") cat "$FIXTURES/all-clients.json" ;;
    dispatch*) printf '{"success": %s}\\n' "${FAKE_SUCCESS:-true}" ;;
    *) exit 1 ;;
esac
"""

WLR_RANDR = """#!/bin/sh
cat <<'EOF'
[{"name": "eDP-1", "modes": [{"width": 1920, "height": 1080, "refresh": 60.0, "current": false},
                             {"width": 1920, "height": 1080, "refresh": 144.0, "current": true}]}]
EOF
"""


def _install(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def fake_bin(tmp_path, monkeypatch):
    """PATH holding only the fakes plus the system dirs `sh` and `cat` need."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _install(bin_dir, "mmsg", MMSG)
    _install(bin_dir, "wlr-randr", WLR_RANDR)
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    monkeypatch.setenv("FAKE_DIR", str(tmp_path))
    monkeypatch.setenv("FIXTURES", str(FIXTURES))
    monkeypatch.setenv("MANGO_INSTANCE_SIGNATURE", "test")
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    return bin_dir


@pytest.fixture
def calls(tmp_path):
    """Lines passed to the fake mmsg, read after the code under test ran."""

    def read() -> list[str]:
        log = tmp_path / "calls.log"
        return log.read_text().splitlines() if log.exists() else []

    return read


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    os.environ.pop("CAELESTIA_WALLPAPERS_DIR", None)
