"""Auto-generated source/enum maps for SuperGreenLab controllers.

Generated from SuperGreenOS config.controller.json. These map the integer
values of the indirection ``*_SOURCE`` keys (and a few small enums) to
human-readable option labels. Value 0 always means "off / manual / none".

Do not edit by hand; regenerate from the firmware config if it changes.
"""

from __future__ import annotations

# Integer 0 means the consumer is disabled / driven manually.
OFF_LABEL = "Off / Manual"


SOURCE_MAPS: dict[str, dict[int, str]] = {
    "temp_sensor": {
        0: OFF_LABEL,
        1: 'SHT21 temperature on port #1',
        2: 'SHT21 temperature on port #2',
        3: 'SHT21 temperature on port #3',
        16: 'SCD30 temperature on port #1',
        17: 'SCD30 temperature on port #2',
        18: 'SCD30 temperature on port #3',
    },
    "humi_sensor": {
        0: OFF_LABEL,
        1: 'SHT21 humidity on port #1',
        2: 'SHT21 humidity on port #2',
        3: 'SHT21 humidity on port #3',
        16: 'SCD30 humidity on port #1',
        17: 'SCD30 humidity on port #2',
        18: 'SCD30 humidity on port #3',
    },
    "vpd_sensor": {
        0: OFF_LABEL,
        1: 'SHT21 vpd on port #1',
        2: 'SHT21 vpd on port #2',
        3: 'SHT21 vpd on port #3',
        16: 'SCD30 vpd on port #1',
        17: 'SCD30 vpd on port #2',
        18: 'SCD30 vpd on port #3',
    },
    "co2_sensor": {
        0: OFF_LABEL,
        1: 'SCD30 co2 on port #1',
        2: 'SCD30 co2 on port #2',
        3: 'SCD30 co2 on port #3',
    },
    "weight_sensor": {
        0: OFF_LABEL,
        1: 'HX711 weight on port #1',
        2: 'HX711 weight on port #2',
        3: 'HX711 weight on port #3',
    },
    "fan_ref": {
        0: OFF_LABEL,
        1: 'SHT21 temperature on port #1',
        2: 'SHT21 temperature on port #2',
        3: 'SHT21 temperature on port #3',
        8: 'Box #1 timer output',
        9: 'Box #2 timer output',
        10: 'Box #3 timer output',
        15: 'SHT21 humidity on port #1',
        16: 'SHT21 humidity on port #2',
        17: 'SHT21 humidity on port #3',
        23: 'SHT21 vpd on port #1',
        24: 'SHT21 vpd on port #2',
        25: 'SHT21 vpd on port #3',
        30: 'SCD30 co2 on port #1',
        31: 'SCD30 co2 on port #2',
        32: 'SCD30 co2 on port #3',
        37: 'SCD30 temperature on port #1',
        38: 'SCD30 temperature on port #2',
        39: 'SCD30 temperature on port #3',
        44: 'SCD30 humidity on port #1',
        45: 'SCD30 humidity on port #2',
        46: 'SCD30 humidity on port #3',
        50: 'SCD30 vpd on port #1',
        51: 'SCD30 vpd on port #2',
        52: 'SCD30 vpd on port #3',
    },
    "blower_ref": {
        0: OFF_LABEL,
        1: 'SHT21 temperature on port #1',
        2: 'SHT21 temperature on port #2',
        3: 'SHT21 temperature on port #3',
        8: 'Box #1 timer output',
        9: 'Box #2 timer output',
        10: 'Box #3 timer output',
        15: 'SHT21 humidity on port #1',
        16: 'SHT21 humidity on port #2',
        17: 'SHT21 humidity on port #3',
        23: 'SHT21 vpd on port #1',
        24: 'SHT21 vpd on port #2',
        25: 'SHT21 vpd on port #3',
        30: 'SCD30 co2 on port #1',
        31: 'SCD30 co2 on port #2',
        32: 'SCD30 co2 on port #3',
        37: 'SCD30 temperature on port #1',
        38: 'SCD30 temperature on port #2',
        39: 'SCD30 temperature on port #3',
        44: 'SCD30 humidity on port #1',
        45: 'SCD30 humidity on port #2',
        46: 'SCD30 humidity on port #3',
        50: 'SCD30 vpd on port #1',
        51: 'SCD30 vpd on port #2',
        52: 'SCD30 vpd on port #3',
    },
    "motor_input": {
        0: OFF_LABEL,
        1: 'Blower control for box#1',
        2: 'Blower control for box#2',
        3: 'Blower control for box#3',
        8: 'Watering control for box#1',
        9: 'Watering control for box#2',
        10: 'Watering control for box#3',
        15: 'Fan control for box#1',
        16: 'Fan control for box#2',
        17: 'Fan control for box#3',
    },
    "valve_ref": {
        0: OFF_LABEL,
        1: 'SHT21 temperature on port #1',
        2: 'SHT21 temperature on port #2',
        3: 'SHT21 temperature on port #3',
        7: 'SHT21 humidity on port #1',
        8: 'SHT21 humidity on port #2',
        9: 'SHT21 humidity on port #3',
        15: 'SHT21 vpd on port #1',
        16: 'SHT21 vpd on port #2',
        17: 'SHT21 vpd on port #3',
        22: 'SCD30 co2 on port #1',
        23: 'SCD30 co2 on port #2',
        24: 'SCD30 co2 on port #3',
        28: 'SCD30 temperature on port #1',
        29: 'SCD30 temperature on port #2',
        30: 'SCD30 temperature on port #3',
        34: 'SCD30 humidity on port #1',
        35: 'SCD30 humidity on port #2',
        36: 'SCD30 humidity on port #3',
        40: 'SCD30 vpd on port #1',
        41: 'SCD30 vpd on port #2',
        42: 'SCD30 vpd on port #3',
        46: 'Box #1 timer output',
        47: 'Box #2 timer output',
        48: 'Box #3 timer output',
    },
    "valve_ref_on": {
        0: OFF_LABEL,
        46: 'Box #1 timer output',
        47: 'Box #2 timer output',
        48: 'Box #3 timer output',
    },
}

# Small static enums decoded from firmware headers.
TIMER_TYPE_MAP: dict[int, str] = {0: "Manual", 1: "On/Off schedule", 2: "Season"}
VALVE_MODE_MAP: dict[int, str] = {0: "Disabled", 1: "Keep between", 2: "Keep out"}
STATE_MAP: dict[int, str] = {0: "First run", 1: "Idle", 2: "Running"}
LED_BOX_MAP: dict[int, str] = {-1: "Unassigned", 0: "Box 0", 1: "Box 1", 2: "Box 2"}

