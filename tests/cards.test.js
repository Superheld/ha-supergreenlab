// Tests for the bundled Lovelace cards' entity resolution (the pure functions).
// Run with: node --test tests/
//
// The card module touches browser globals at import time (it defines custom
// elements); stub them before importing so it loads under node.
import { test } from "node:test";
import assert from "node:assert/strict";

globalThis.HTMLElement = class {};
globalThis.customElements = { define() {} };
globalThis.window = { customCards: [] };

const { resolveConfig, resolveLightConfig, resolveBoxConfig } = await import(
  "../custom_components/supergreenlab/sgl-cards.js"
);

// Build a fake `hass` where every state id maps to the same device by default.
function mkHass(stateIds, devices = {}) {
  const states = {};
  const entities = {};
  for (const id of stateIds) {
    states[id] = { state: "x" };
    entities[id] = { device_id: devices[id] ?? "d1" };
  }
  return { states, entities };
}

test("fan card resolves siblings by device + kind + box", () => {
  const hass = mkHass([
    "select.box_0_fan_mode",
    "number.box_0_fan_speed_min",
    "number.box_0_fan_speed_max",
    "number.box_0_fan_reference_from",
    "number.box_0_fan_reference_to",
    "sensor.box_0_fan",
  ]);
  const c = resolveConfig(hass, { mode: "select.box_0_fan_mode" });
  assert.equal(c.title, "Fan");
  assert.equal(c.speed_min, "number.box_0_fan_speed_min");
  assert.equal(c.speed_max, "number.box_0_fan_speed_max");
  assert.equal(c.reference_from, "number.box_0_fan_reference_from");
  assert.equal(c.current, "sensor.box_0_fan");
});

test("fan card recognises a blower mode", () => {
  const hass = mkHass(["select.box_0_blower_mode", "sensor.box_0_blower"]);
  const c = resolveConfig(hass, { mode: "select.box_0_blower_mode" });
  assert.equal(c.title, "Blower");
  assert.equal(c.current, "sensor.box_0_blower");
});

test("fan card ignores entities on a different device", () => {
  const hass = mkHass(
    ["select.box_0_fan_mode", "number.box_0_fan_speed_min"],
    { "number.box_0_fan_speed_min": "other-device" },
  );
  const c = resolveConfig(hass, { mode: "select.box_0_fan_mode" });
  assert.equal(c.speed_min, undefined);
});

test("light card resolves schedule times + season date", () => {
  const hass = mkHass([
    "select.box_0_timer_mode",
    "time.box_0_on_time",
    "time.box_0_off_time",
    "sensor.box_0_season_date",
  ]);
  const c = resolveLightConfig(hass, { mode: "select.box_0_timer_mode" });
  assert.equal(c.title, "Box 0 light");
  assert.equal(c.on_time, "time.box_0_on_time");
  assert.equal(c.off_time, "time.box_0_off_time");
  assert.equal(c.season_date, "sensor.box_0_season_date");
});

test("box card resolves sources + correlates spectrum by LED index", () => {
  const hass = mkHass([
    "select.box_0_timer_mode",
    "select.box_0_temperature_source",
    "select.box_0_humidity_source",
    "light.box_0_light_0",
    "select.light_0_spectrum",
  ]);
  const c = resolveBoxConfig(hass, { entity: "select.box_0_timer_mode" });
  assert.equal(c.title, "Box 0 setup");
  assert.equal(c.temp_source, "select.box_0_temperature_source");
  assert.equal(c.humi_source, "select.box_0_humidity_source");
  assert.deepEqual(c.spectrum, ["select.light_0_spectrum"]);
});

test("box card does not mix entities from other boxes", () => {
  const hass = mkHass([
    "select.box_1_temperature_source", // listed first on purpose
    "select.box_0_timer_mode",
    "select.box_0_temperature_source",
  ]);
  const c = resolveBoxConfig(hass, { entity: "select.box_0_timer_mode" });
  assert.equal(c.temp_source, "select.box_0_temperature_source");
});
