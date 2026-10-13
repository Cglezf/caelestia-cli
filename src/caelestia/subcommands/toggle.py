import json
import shlex
import shutil
from argparse import Namespace
from collections import ChainMap
from typing import Any

from caelestia.utils import mango
from caelestia.utils.io import warn
from caelestia.utils.paths import get_config

# Hyprland client key -> mango client key, so matches written for upstream keep
# working. Keys mango has no equivalent for (workspace...) are dropped.
MATCH_KEYS = {"class": "appid", "initialClass": "appid", "appid": "appid", "title": "title", "initialTitle": "title"}


def to_mango_match(match: dict[str, Any]) -> dict[str, Any]:
    return {MATCH_KEYS[key]: value for key, value in match.items() if key in MATCH_KEYS}


def is_subset(superset, subset):
    for key, value in subset.items():
        if key not in superset:
            return False

        if isinstance(value, dict):
            if not is_subset(superset[key], value):
                return False

        elif isinstance(value, str):
            if value not in superset[key]:
                return False

        elif isinstance(value, list):
            if not set(value) <= set(superset[key]):
                return False
        elif isinstance(value, set):
            if not value <= superset[key]:
                return False

        else:
            if not value == superset[key]:
                return False

    return True


class DeepChainMap(ChainMap):
    def __getitem__(self, key):
        values = (mapping[key] for mapping in self.maps if key in mapping)
        try:
            first = next(values)
        except StopIteration:
            return self.__missing__(key)
        if isinstance(first, dict):
            return self.__class__(first, *values)
        return first

    def __repr__(self):
        return repr(dict(self))


class Command:
    args: Namespace
    cfg: dict[str, dict[str, dict[str, Any]]] | DeepChainMap
    clients: list[dict[str, Any]] | None = None

    def __init__(self, args: Namespace) -> None:
        self.args = args

        self.cfg = {
            "communication": {
                "discord": {
                    "enable": True,
                    "match": [{"class": "discord"}],
                    "command": ["discord"],
                    "move": True,
                },
                "whatsapp": {
                    "enable": True,
                    "match": [{"class": "whatsapp"}],
                    "move": True,
                },
            },
            "music": {
                "spotify": {
                    "enable": True,
                    "match": [{"class": "Spotify"}, {"initialTitle": "Spotify"}, {"initialTitle": "Spotify Free"}],
                    "command": ["spicetify", "watch", "-s"],
                    "move": True,
                },
                "feishin": {
                    "enable": True,
                    "match": [{"class": "feishin"}],
                    "move": True,
                },
            },
            "sysmon": {
                "btop": {
                    "enable": True,
                    "match": [{"class": "btop", "title": "btop", "workspace": {"name": "special:sysmon"}}],
                    "command": ["kitty", "--class", "btop", "-T", "btop", "btop"],
                },
            },
            "todo": {
                "todoist": {
                    "enable": True,
                    "match": [{"class": "Todoist"}],
                    "command": ["todoist"],
                    "move": True,
                },
            },
        }
        try:
            self.cfg = DeepChainMap(get_config()["toggles"], self.cfg)
        except KeyError:
            pass

    def run(self) -> None:
        if self.args.workspace == "specialws":
            self.specialws()
            return

        # Mango has no named special workspaces: each client becomes a named
        # scratchpad, and with nothing to toggle the single special tag stands in.
        toggled = False
        if self.args.workspace in self.cfg:
            for client in self.cfg[self.args.workspace].values():
                if "enable" in client and client["enable"] and self.handle_client_config(client):
                    toggled = True

        if not toggled:
            mango.dispatch("toggle_special_tag")

    def get_clients(self) -> list[dict[str, Any]]:
        if self.clients is None:
            self.clients = mango.clients()
        return self.clients or []

    def spawn_command(self, spawn: list[str]) -> list[str] | None:
        if spawn and spawn[0].endswith(".desktop"):
            return ["app2unit", "--", *spawn]
        if spawn and shutil.which(spawn[0]):
            return spawn
        return None

    def handle_client_config(self, client: dict[str, Any]) -> bool:
        matches = [m for m in map(to_mango_match, client["match"]) if m]

        def selector(c: dict[str, Any]) -> bool:
            # Each match is or, inside matches is and
            return any(is_subset(c, match) for match in matches)

        existing = next((c for c in self.get_clients() if selector(c)), None)
        command = self.spawn_command(client.get("command") or [])
        if existing is None and command is None:
            return False

        # toggle_named_scratchpad finds the window by appid (or by title when
        # there is no appid) and runs the command only when none matches.
        appid = existing["appid"] if existing else next((m["appid"] for m in matches if "appid" in m), "")
        title = (
            "" if appid else (existing or {}).get("title") or next((m["title"] for m in matches if "title" in m), "")
        )
        try:
            return mango.dispatch("toggle_named_scratchpad", appid, title, shlex.join(command or []))
        except ValueError as e:
            warn(f"cannot toggle {appid or title}: {e}")
            return False

    def specialws(self) -> None:
        mango.dispatch("toggle_special_tag")
