"""Pure-logic tests for the decoded enum maps."""

from __future__ import annotations

from custom_components.supergreenlab.sources import (
    LED_TYPE_MAP,
    SOURCE_MAPS,
    TIMER_TYPE_MAP,
)


def test_temp_source_decode():
    assert SOURCE_MAPS["temp_sensor"][0] == "Off / Manual"
    assert SOURCE_MAPS["temp_sensor"][1] == "SHT21 temperature on port #1"
    assert SOURCE_MAPS["temp_sensor"][16] == "SCD30 temperature on port #1"


def test_fan_ref_offers_timer_option():
    # Switching a fan from temperature to time relies on a timer option here.
    assert any("timer output" in label for label in SOURCE_MAPS["fan_ref"].values())


def test_led_type_map():
    assert LED_TYPE_MAP[0] == "Full spectrum"
    assert LED_TYPE_MAP[4] == "Far red"


def test_timer_type_map():
    assert TIMER_TYPE_MAP == {0: "Manual", 1: "On/Off schedule", 2: "Season"}
