"""The mango branch targets a zsh system without fish or foot: no default may need them.

A guard of the class, not of one line: it walks every default toggle command and
the shipped templates, so a new upstream default that calls fish or foot shows
up here on the next rebase.
"""

from argparse import Namespace

from caelestia.subcommands import toggle
from caelestia.utils.paths import templates_dir

ABSENT = ("fish", "foot")


def test_default_toggle_commands_need_neither_fish_nor_foot(isolated_home):
    cfg = toggle.Command(Namespace(workspace="none")).cfg
    for workspace in cfg.values():
        for client in workspace.values():
            command = client.get("command") or []
            assert not set(command) & set(ABSENT), f"{command} needs fish or foot"


def test_templates_do_not_launch_foot():
    for template in templates_dir.iterdir():
        for line in template.read_text(errors="ignore").splitlines():
            if line.startswith("terminal="):
                assert line.split("=", 1)[1].split()[0] not in ABSENT, f"{template.name}: {line}"
