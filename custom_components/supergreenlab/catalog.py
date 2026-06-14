"""Declarative entity catalog for SuperGreenLab controllers.

This is the single place that holds the domain knowledge: every controllable or
observable key, which HA platform represents it, how to scale it, which option
map a select uses, and how often it needs polling. The platform modules
(sensor/number/select/switch/binary_sensor) read this catalog and build their
entities from it; nothing device-specific is hand-wired per entity elsewhere.

Scopes describe how a templated key (``BOX_{box}_TEMP``) is expanded into
concrete instances at setup time:

* ``box``       - one per *enabled* box
* ``box_all``   - one per possible box (0..2), regardless of enabled state
                  (used for the enable switch itself)
* ``led``       - one per LED channel (0..5)
* ``led_box``   - one per LED channel assigned to an enabled box
* ``motor``     - one per motor channel (0..2)
* ``sht`` / ``scd`` / ``hx`` - one per i2c port (0..2) of that sensor type
* ``valve`` / ``device`` - a single instance, no index
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .const import MAX_BOXES, MAX_LED_CHANNELS, VPD_DIVISOR
from .sources import (
    LED_BOX_MAP,
    SOURCE_MAPS,
    STATE_MAP,
    TIMER_TYPE_MAP,
    VALVE_MODE_MAP,
)

# Structural keys: changing them adds/removes other entities, so the config
# entry is reloaded after a write to re-run discovery.
STRUCTURAL_KEYS = {"LED_{led}_BOX", "BOX_{box}_ENABLED"}


@dataclass(frozen=True, kw_only=True)
class EntityDef:
    """One catalogued key and how to surface it in Home Assistant."""

    platform: str
    key: str
    name: str
    scope: str
    # Polling speed: live readings poll fast, config polls slow.
    fast: bool = False
    category: str | None = None  # None | "config" | "diagnostic"
    enabled_default: bool = True
    icon: str | None = None
    # sensor
    device_class: str | None = None
    unit: str | None = None
    state_class: str | None = None
    scale: float = 1.0
    precision: int | None = None
    value_map: dict[int, str] | None = None  # int -> label (text sensors)
    # number
    min: float = 0
    max: float = 100
    step: float = 1
    # select
    options_map: dict[int, str] | None = None


def is_structural(key_template: str) -> bool:
    """Return True if writing this key requires a config-entry reload."""
    return key_template in STRUCTURAL_KEYS


# --- sensors (live values) -------------------------------------------------

_TEMP = dict(device_class="temperature", unit="°C", state_class="measurement", fast=True)
_PCT = dict(unit="%", state_class="measurement", fast=True)

SENSORS: tuple[EntityDef, ...] = (
    EntityDef(platform="sensor", key="BOX_{box}_TEMP", name="Box {box} Temperature",
              scope="box", **_TEMP),
    EntityDef(platform="sensor", key="BOX_{box}_HUMI", name="Box {box} Humidity",
              scope="box", device_class="humidity", **_PCT),
    EntityDef(platform="sensor", key="BOX_{box}_VPD", name="Box {box} VPD", scope="box",
              device_class="pressure", unit="kPa", state_class="measurement",
              scale=1 / VPD_DIVISOR, precision=2, fast=True),
    EntityDef(platform="sensor", key="BOX_{box}_CO2", name="Box {box} CO2", scope="box",
              device_class="carbon_dioxide", unit="ppm", state_class="measurement",
              fast=True),
    EntityDef(platform="sensor", key="BOX_{box}_WEIGHT", name="Box {box} Weight",
              scope="box", device_class="weight", unit="g", state_class="measurement",
              fast=True, enabled_default=False),
    EntityDef(platform="sensor", key="BOX_{box}_BLOWER_DUTY", name="Box {box} Exhaust fan",
              scope="box", icon="mdi:fan", **_PCT),
    EntityDef(platform="sensor", key="BOX_{box}_FAN_DUTY", name="Box {box} Intake fan",
              scope="box", icon="mdi:fan", **_PCT),
    EntityDef(platform="sensor", key="BOX_{box}_TIMER_OUTPUT", name="Box {box} Light output",
              scope="box", icon="mdi:brightness-percent", **_PCT),
    # diagnostics
    EntityDef(platform="sensor", key="STATE", name="State", scope="device",
              category="diagnostic", value_map=STATE_MAP),
    EntityDef(platform="sensor", key="N_RESTARTS", name="Restarts", scope="device",
              category="diagnostic", state_class="total_increasing"),
    EntityDef(platform="sensor", key="VALVE_REF", name="Valve reference", scope="valve",
              category="diagnostic", fast=True, enabled_default=False),
    EntityDef(platform="sensor", key="VALVE_REF_ON", name="Valve on-reference", scope="valve",
              category="diagnostic", fast=True, enabled_default=False),
)

# --- binary sensors --------------------------------------------------------

BINARY_SENSORS: tuple[EntityDef, ...] = (
    EntityDef(platform="binary_sensor", key="BOX_{box}_TIMER_OUTPUT",
              name="Box {box} Light on", scope="box", device_class="light", fast=True),
    EntityDef(platform="binary_sensor", key="VALVE_OPEN", name="Valve open", scope="valve",
              device_class="opening", fast=True, enabled_default=False),
    EntityDef(platform="binary_sensor", key="SHT21_{n}_PRESENT", name="SHT21 #{n} present",
              scope="sht", category="diagnostic", enabled_default=False),
    EntityDef(platform="binary_sensor", key="SCD30_{n}_PRESENT", name="SCD30 #{n} present",
              scope="scd", category="diagnostic", enabled_default=False),
    EntityDef(platform="binary_sensor", key="HX711_{n}_PRESENT", name="HX711 #{n} present",
              scope="hx", category="diagnostic", enabled_default=False),
)

# --- numbers (writable config) ---------------------------------------------

_CFG = dict(category="config")

NUMBERS: tuple[EntityDef, ...] = (
    # schedule
    EntityDef(platform="number", key="BOX_{box}_ON_HOUR", name="Box {box} On hour",
              scope="box", max=23, icon="mdi:weather-sunset-up", **_CFG),
    EntityDef(platform="number", key="BOX_{box}_ON_MIN", name="Box {box} On minute",
              scope="box", max=59, **_CFG),
    EntityDef(platform="number", key="BOX_{box}_OFF_HOUR", name="Box {box} Off hour",
              scope="box", max=23, icon="mdi:weather-sunset-down", **_CFG),
    EntityDef(platform="number", key="BOX_{box}_OFF_MIN", name="Box {box} Off minute",
              scope="box", max=59, **_CFG),
    # ventilation curve
    EntityDef(platform="number", key="BOX_{box}_BLOWER_MIN", name="Box {box} Exhaust fan min",
              scope="box", unit="%", icon="mdi:fan-chevron-down", **_CFG),
    EntityDef(platform="number", key="BOX_{box}_BLOWER_MAX", name="Box {box} Exhaust fan max",
              scope="box", unit="%", icon="mdi:fan-chevron-up", **_CFG),
    EntityDef(platform="number", key="BOX_{box}_BLOWER_REF_MIN", name="Box {box} Exhaust ref min",
              scope="box", max=2000, enabled_default=False, **_CFG),
    EntityDef(platform="number", key="BOX_{box}_BLOWER_REF_MAX", name="Box {box} Exhaust ref max",
              scope="box", max=2000, enabled_default=False, **_CFG),
    EntityDef(platform="number", key="BOX_{box}_FAN_MIN", name="Box {box} Intake fan min",
              scope="box", unit="%", icon="mdi:fan-chevron-down", **_CFG),
    EntityDef(platform="number", key="BOX_{box}_FAN_MAX", name="Box {box} Intake fan max",
              scope="box", unit="%", icon="mdi:fan-chevron-up", **_CFG),
    EntityDef(platform="number", key="BOX_{box}_FAN_REF_MIN", name="Box {box} Intake ref min",
              scope="box", max=2000, enabled_default=False, **_CFG),
    EntityDef(platform="number", key="BOX_{box}_FAN_REF_MAX", name="Box {box} Intake ref max",
              scope="box", max=2000, enabled_default=False, **_CFG),
    # watering
    EntityDef(platform="number", key="BOX_{box}_WATERING_PERIOD", name="Box {box} Watering period",
              scope="box", max=10080, unit="min", icon="mdi:water-outline",
              enabled_default=False, **_CFG),
    EntityDef(platform="number", key="BOX_{box}_WATERING_DURATION", name="Box {box} Watering duration",
              scope="box", max=3600, unit="s", icon="mdi:water",
              enabled_default=False, **_CFG),
    EntityDef(platform="number", key="BOX_{box}_WATERING_POWER", name="Box {box} Watering power",
              scope="box", unit="%", enabled_default=False, **_CFG),
    # season
    EntityDef(platform="number", key="BOX_{box}_START_MONTH", name="Box {box} Season start month",
              scope="box", min=1, max=12, enabled_default=False, **_CFG),
    EntityDef(platform="number", key="BOX_{box}_START_DAY", name="Box {box} Season start day",
              scope="box", min=1, max=31, enabled_default=False, **_CFG),
    EntityDef(platform="number", key="BOX_{box}_DURATION_DAYS", name="Box {box} Season duration",
              scope="box", max=365, unit="d", enabled_default=False, **_CFG),
    # leaf offset (stored in tenths of a degree)
    EntityDef(platform="number", key="SHT21_{n}_VPD_LEAF_OFFSET", name="SHT21 #{n} leaf offset",
              scope="sht", min=-100, max=100, enabled_default=False, **_CFG),
    EntityDef(platform="number", key="SCD30_{n}_VPD_LEAF_OFFSET", name="SCD30 #{n} leaf offset",
              scope="scd", min=-100, max=100, enabled_default=False, **_CFG),
    # load cell calibration
    EntityDef(platform="number", key="HX711_{n}_WEIGHT_CALIBRATION", name="HX711 #{n} calibration",
              scope="hx", max=255, enabled_default=False, **_CFG),
    # motors
    EntityDef(platform="number", key="MOTOR_{motor}_MIN", name="Motor {motor} min",
              scope="motor", unit="%", enabled_default=False, **_CFG),
    EntityDef(platform="number", key="MOTOR_{motor}_MAX", name="Motor {motor} max",
              scope="motor", unit="%", enabled_default=False, **_CFG),
    EntityDef(platform="number", key="MOTOR_{motor}_DUTY_TESTING", name="Motor {motor} test duty",
              scope="motor", unit="%", enabled_default=False, **_CFG),
    # valve
    EntityDef(platform="number", key="VALVE_CYCLE_DIV", name="Valve cycle divisions",
              scope="valve", max=100, enabled_default=False, **_CFG),
    EntityDef(platform="number", key="VALVE_CYCLE_DIV_DURATION", name="Valve cycle duration",
              scope="valve", max=10000, unit="ms", enabled_default=False, **_CFG),
    EntityDef(platform="number", key="VALVE_REF_MIN", name="Valve ref min", scope="valve",
              max=5000, enabled_default=False, **_CFG),
    EntityDef(platform="number", key="VALVE_REF_MAX", name="Valve ref max", scope="valve",
              max=5000, enabled_default=False, **_CFG),
)

# --- selects (config, enum-backed) -----------------------------------------

SELECTS: tuple[EntityDef, ...] = (
    EntityDef(platform="select", key="BOX_{box}_TIMER_TYPE", name="Box {box} Timer mode",
              scope="box", options_map=TIMER_TYPE_MAP, icon="mdi:timer-cog", **_CFG),
    EntityDef(platform="select", key="BOX_{box}_TEMP_SOURCE", name="Box {box} Temperature source",
              scope="box", options_map=SOURCE_MAPS["temp_sensor"], **_CFG),
    EntityDef(platform="select", key="BOX_{box}_HUMI_SOURCE", name="Box {box} Humidity source",
              scope="box", options_map=SOURCE_MAPS["humi_sensor"], **_CFG),
    EntityDef(platform="select", key="BOX_{box}_VPD_SOURCE", name="Box {box} VPD source",
              scope="box", options_map=SOURCE_MAPS["vpd_sensor"], **_CFG),
    EntityDef(platform="select", key="BOX_{box}_CO2_SOURCE", name="Box {box} CO2 source",
              scope="box", options_map=SOURCE_MAPS["co2_sensor"], enabled_default=False, **_CFG),
    EntityDef(platform="select", key="BOX_{box}_WEIGHT_SOURCE", name="Box {box} Weight source",
              scope="box", options_map=SOURCE_MAPS["weight_sensor"], enabled_default=False, **_CFG),
    EntityDef(platform="select", key="BOX_{box}_FAN_REF_SOURCE", name="Box {box} Intake fan source",
              scope="box", options_map=SOURCE_MAPS["fan_ref"], **_CFG),
    EntityDef(platform="select", key="BOX_{box}_BLOWER_REF_SOURCE", name="Box {box} Exhaust fan source",
              scope="box", options_map=SOURCE_MAPS["blower_ref"], **_CFG),
    EntityDef(platform="select", key="LED_{led}_BOX", name="Light {led} assignment",
              scope="led", options_map=LED_BOX_MAP, icon="mdi:led-strip-variant", **_CFG),
    EntityDef(platform="select", key="MOTOR_{motor}_SOURCE", name="Motor {motor} source",
              scope="motor", options_map=SOURCE_MAPS["motor_input"], enabled_default=False, **_CFG),
    EntityDef(platform="select", key="VALVE_MODE", name="Valve mode", scope="valve",
              options_map=VALVE_MODE_MAP, enabled_default=False, **_CFG),
    EntityDef(platform="select", key="VALVE_REF_SOURCE", name="Valve ref source", scope="valve",
              options_map=SOURCE_MAPS["valve_ref"], enabled_default=False, **_CFG),
    EntityDef(platform="select", key="VALVE_REF_ON_SOURCE", name="Valve on-ref source", scope="valve",
              options_map=SOURCE_MAPS["valve_ref_on"], enabled_default=False, **_CFG),
)

# --- switches (config) -----------------------------------------------------

SWITCHES: tuple[EntityDef, ...] = (
    EntityDef(platform="switch", key="BOX_{box}_ENABLED", name="Box {box} enabled",
              scope="box_all", icon="mdi:grid", **_CFG),
    EntityDef(platform="switch", key="LEDS_FASTMODE", name="LED fast PWM", scope="device",
              enabled_default=False, **_CFG),
    EntityDef(platform="switch", key="MOTORS_CURVE", name="Motor soft curve", scope="device",
              enabled_default=False, **_CFG),
)

ALL_DEFS: tuple[EntityDef, ...] = (
    *SENSORS,
    *BINARY_SENSORS,
    *NUMBERS,
    *SELECTS,
    *SWITCHES,
)


def expand(defs: tuple[EntityDef, ...], device) -> list[tuple[EntityDef, dict]]:
    """Expand templated defs into concrete (def, placeholders) instances."""
    out: list[tuple[EntityDef, dict]] = []
    for d in defs:
        for placeholders in _scope_instances(d.scope, device):
            out.append((d, placeholders))
    return out


def _scope_instances(scope: str, device) -> list[dict]:
    if scope == "box":
        return [{"box": b} for b in device.boxes]
    if scope == "box_all":
        return [{"box": b} for b in range(MAX_BOXES)]
    if scope == "led":
        return [{"led": i} for i in range(MAX_LED_CHANNELS)]
    if scope == "led_box":
        return [{"led": i} for i in device.led_to_box]
    if scope == "motor":
        return [{"motor": i} for i in range(3)]
    if scope in ("sht", "scd", "hx"):
        return [{"n": i} for i in range(3)]
    if scope in ("valve", "device"):
        return [{}]
    return []
