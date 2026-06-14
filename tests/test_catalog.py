"""Invariants of the declarative entity catalog."""

from __future__ import annotations

from custom_components.supergreenlab import catalog


class _Dev:
    boxes = [0]
    led_to_box = {0: 0, 1: 0, 2: 0}


def test_no_unformatted_placeholders():
    for d, ph in catalog.expand(catalog.ALL_DEFS + catalog.BUTTONS, _Dev()):
        key = d.key.format(**ph)
        assert "{" not in key and "}" not in key
        assert "{" not in d.name.format(**ph)
        if d.key2:
            assert "{" not in d.key2.format(**ph)


def test_selects_have_options():
    for d in catalog.SELECTS:
        assert d.options_map, d.key


def test_times_have_second_key():
    for d in catalog.TIMES:
        assert d.key2 is not None


def test_known_entity_counts_for_single_box():
    by_platform: dict[str, int] = {}
    for d, _ph in catalog.expand(catalog.ALL_DEFS + catalog.BUTTONS, _Dev()):
        by_platform[d.platform] = by_platform.get(d.platform, 0) + 1
    # three assigned LED channels -> three spectrum selects
    assert by_platform["select"] >= 3
    # two schedule time entities for the one box
    assert by_platform["time"] == 2
