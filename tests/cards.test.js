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

const { resolveConfig, resolveLightConfig, resolveBoxConfig, SglDashboardStrategy } =
  await import("../custom_components/supergreenlab/sgl-cards.js");

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

test("dashboard strategy generates a sections view per box", async () => {
  const states = {};
  const entities = {};
  const add = (id) => {
    states[id] = { state: "x" };
    entities[id] = { device_id: "boxdev0" };
  };
  add("select.box_0_timer_mode");
  add("select.box_0_fan_mode");
  add("time.box_0_on_time");
  add("sensor.box_0_temperature");
  add("number.box_0_fan_reference_from");
  const hass = {
    states,
    entities,
    devices: {
      boxdev0: { id: "boxdev0", identifiers: [["supergreenlab", "abc123_box_0"]] },
      ctrl: { id: "ctrl", identifiers: [["supergreenlab", "abc123"]] },
    },
  };
  const dash = await SglDashboardStrategy.generate({}, hass);
  assert.equal(dash.views.length, 1);
  const view = dash.views[0];
  assert.equal(view.title, "Box 0");
  assert.equal(view.type, "sections");
  // The fan reference field is gated on the fan mode being a sensor mode.
  const flat = JSON.stringify(view);
  assert.ok(flat.includes("number.box_0_fan_reference_from"));
  assert.ok(flat.includes("select.box_0_fan_mode"));
});

test("dashboard strategy reports when no boxes exist", async () => {
  const dash = await SglDashboardStrategy.generate(
    {},
    { states: {}, entities: {}, devices: {} },
  );
  assert.equal(dash.views.length, 1);
  assert.ok(JSON.stringify(dash.views[0]).includes("No SuperGreenLab boxes"));
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
