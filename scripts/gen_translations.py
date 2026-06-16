#!/usr/bin/env python3
"""Regenerate the entity name/icon translations from the entity catalog.

The catalog (``catalog.py``) is the single source of truth for every entity.
This script derives the ``entity`` block of ``strings.json`` / ``translations/
en.json`` and the whole of ``icons.json`` from it, so names and icons never
drift from the catalog. Run it after adding or renaming catalog entries:

    python scripts/gen_translations.py

Hand-written (non-catalog) entities are listed in ``_HANDWRITTEN`` below and
must be kept in sync with their entity classes (light, fan/blower mode select,
season-date sensor, sunglasses switch). ``test_every_catalog_key_has_a_
translation`` guards against forgetting to run this for catalogued entities.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "custom_components"))

from supergreenlab.catalog import (  # noqa: E402
    ALL_DEFS,
    BUTTONS,
    entity_translation_key,
    entity_translation_name,
)

COMPONENT = ROOT / "custom_components" / "supergreenlab"

# (platform, translation_key, name, icon) for entities not driven by the catalog.
_HANDWRITTEN = [
    ("light", "light", "Light {led}", "mdi:led-strip-variant"),
    ("select", "fan_mode", "Fan mode", "mdi:fan-auto"),
    ("select", "blower_mode", "Blower mode", "mdi:fan-auto"),
    ("sensor", "season_date", "Season date", "mdi:calendar-clock"),
    ("switch", "sunglasses_mode", "Sunglasses mode", "mdi:sunglasses"),
]


def build() -> tuple[dict, dict]:
    """Return ``(entity_names, entity_icons)`` keyed by platform."""
    names: dict[str, dict] = {}
    icons: dict[str, dict] = {}

    def add(platform: str, key: str, name: str, icon: str | None) -> None:
        bucket = names.setdefault(platform, {})
        if key in bucket and bucket[key]["name"] != name:
            raise SystemExit(
                f"collision {platform}.{key}: {bucket[key]['name']!r} vs {name!r}"
            )
        bucket[key] = {"name": name}
        if icon:
            icons.setdefault(platform, {})[key] = {"default": icon}

    for d in (*ALL_DEFS, *BUTTONS):
        add(d.platform, entity_translation_key(d), entity_translation_name(d), d.icon)
    for platform, key, name, icon in _HANDWRITTEN:
        add(platform, key, name, icon)

    names = {p: dict(sorted(v.items())) for p, v in sorted(names.items())}
    icons = {p: dict(sorted(v.items())) for p, v in sorted(icons.items())}
    return names, icons


def main() -> None:
    names, icons = build()

    for path in (COMPONENT / "strings.json", COMPONENT / "translations" / "en.json"):
        data = json.loads(path.read_text(), object_pairs_hook=OrderedDict)
        merged = OrderedDict()
        for key, value in data.items():
            merged[key] = value
            if key == "config":
                merged["entity"] = names
        if "entity" not in merged:
            merged["entity"] = names
        path.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n")

    (COMPONENT / "icons.json").write_text(
        json.dumps({"entity": icons}, indent=2, ensure_ascii=False) + "\n"
    )
    total = sum(len(v) for v in names.values())
    print(f"wrote {total} entity names and {sum(len(v) for v in icons.values())} icons")


if __name__ == "__main__":
    main()
