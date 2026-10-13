from argparse import Namespace

import pytest

from caelestia.subcommands import toggle
from caelestia.utils import mango


def test_monitors_and_clients_come_from_mmsg(fake_bin):
    assert [m["name"] for m in mango.monitors()] == ["HDMI-A-1", "eDP-1"]
    assert [c["appid"] for c in mango.clients()] == ["kitty", "btop"]


def test_focused_monitor_is_the_active_one_not_the_first(fake_bin):
    assert mango.focused_monitor()["name"] == "eDP-1"


def test_without_mmsg_queries_are_empty_not_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    assert mango.monitors() == []
    assert mango.focused_monitor() is None
    assert mango.dispatch("view", 1) is False


def test_dispatch_joins_with_commas_and_reads_success(fake_bin, calls, monkeypatch):
    assert mango.dispatch("toggle_named_scratchpad", "btop", "", "kitty --class btop btop") is True
    assert calls() == ["dispatch toggle_named_scratchpad,btop,,kitty --class btop btop"]
    monkeypatch.setenv("FAKE_SUCCESS", "false")
    assert mango.dispatch("view", 3) is False


def test_dispatch_refuses_an_argument_with_a_comma(fake_bin, calls):
    with pytest.raises(ValueError):
        mango.dispatch("spawn", "sh -c 'a,b'")
    assert calls() == []


def test_refresh_rate_is_the_current_mode(fake_bin):
    assert mango.refresh_rate("eDP-1") == 144.0
    assert mango.refresh_rate("DP-9") is None


def test_colour_options_use_current_mango_names():
    conf = mango.gen_colours({"outline": "918f9a", "primary": "c2c1ff"})
    assert "border_color=0x918f9aff" in conf
    assert "focus_color=0xc2c1ffff" in conf
    # mango no longer reads the unseparated spelling the old port wrote.
    assert "bordercolor" not in conf and "focuscolor" not in conf


def test_apply_colours_writes_once_and_reloads_only_on_change(fake_bin, calls, tmp_path, monkeypatch):
    monkeypatch.setattr(mango, "colours_path", tmp_path / "mango/caelestia-colours.conf")
    colours = {"outline": "918f9a"}
    mango.apply_colours(colours)
    mango.apply_colours(colours)
    assert calls() == ["dispatch reload_config"]
    mango.apply_colours({"outline": "000000"})
    assert calls() == ["dispatch reload_config", "dispatch reload_config"]


def test_apply_colours_outside_mango_writes_without_dispatch(fake_bin, calls, tmp_path, monkeypatch):
    monkeypatch.delenv("MANGO_INSTANCE_SIGNATURE")
    monkeypatch.setattr(mango, "colours_path", tmp_path / "colours.conf")
    mango.apply_colours({"outline": "918f9a"})
    assert (tmp_path / "colours.conf").is_file()
    assert calls() == []


def test_hyprland_matches_translate_to_mango_keys():
    match = {"class": "btop", "title": "btop", "workspace": {"name": "special:sysmon"}}
    assert toggle.to_mango_match(match) == {"appid": "btop", "title": "btop"}
    assert toggle.to_mango_match({"initialTitle": "Spotify"}) == {"title": "Spotify"}


def make_toggle(workspace: str) -> toggle.Command:
    return toggle.Command(Namespace(workspace=workspace))


def test_existing_window_toggles_as_named_scratchpad(fake_bin, calls):
    make_toggle("sysmon").run()
    # The command after the empty title depends on which terminal the host has.
    assert calls()[0] == "get all-clients"
    assert calls()[1].startswith("dispatch toggle_named_scratchpad,btop,,")
    assert len(calls()) == 2


def test_missing_app_without_command_falls_back_to_special_tag(fake_bin, calls):
    make_toggle("todo").run()
    assert calls()[-1] == "dispatch toggle_special_tag"


def test_unknown_workspace_and_specialws_use_the_special_tag(fake_bin, calls):
    make_toggle("nothing").run()
    make_toggle("specialws").run()
    assert calls() == ["dispatch toggle_special_tag", "dispatch toggle_special_tag"]
