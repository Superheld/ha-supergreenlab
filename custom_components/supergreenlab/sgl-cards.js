/*
 * SuperGreenLab Fan Card — a mode-aware Lovelace card for one fan/blower.
 *
 * Renders a native Home Assistant `entities` card and decides which rows to
 * show based on the selected mode:
 *   Manual      -> speed
 *   Timer       -> schedule on/off times + speed range
 *   Temperature -> current temperature + reference range + speed range
 *   Humidity / VPD / CO2 -> like Temperature with the matching metric
 *
 * Config: just the `mode` entity; the other entities and a title are resolved
 * automatically (legacy entity ids supported). Explicit ids in the config win.
 */

const MODE_FIELDS = {
  Manual: ["speed_min"],
  Timer: ["on_time", "off_time", "speed_min", "speed_max"],
  Temperature: ["reference_from", "reference_to", "speed_min", "speed_max"],
  Humidity: ["reference_from", "reference_to", "speed_min", "speed_max"],
  VPD: ["reference_from", "reference_to", "speed_min", "speed_max"],
  CO2: ["reference_from", "reference_to", "speed_min", "speed_max"],
};

// The live reference reading to show (read-only) for each mode.
const MODE_REF_SENSOR = {
  Temperature: "ref_temp",
  Humidity: "ref_humi",
  VPD: "ref_vpd",
  CO2: "ref_co2",
};

// Resolve sibling entities from the mode entity. Siblings are matched by the
// same *device* (robust against mismatched entity-id prefixes, e.g. a renamed
// mode entity), plus — for fan-specific entities — the fan kind, the box index
// and a role suffix. Box/time/climate entities skip the kind filter. Accepts
// both current and legacy names (entity ids don't change on rename).
function resolveConfig(hass, config) {
  const modeId = config.mode;
  let kind = "fan";
  let title = "Fan";
  if (modeId.includes("blower")) [kind, title] = ["blower", "Blower"];
  else if (modeId.includes("exhaust")) [kind, title] = ["exhaust", "Blower"];
  else if (modeId.includes("intake")) [kind, title] = ["intake", "Fan"];
  const boxToken = (modeId.match(/box_\d+/) || [])[0];
  const deviceId = hass.entities?.[modeId]?.device_id;

  const scan = (domain, suffixes, useBox, requireKind) => {
    for (const id of Object.keys(hass.states)) {
      if (!id.startsWith(`${domain}.`)) continue;
      if (deviceId && hass.entities?.[id]?.device_id !== deviceId) continue;
      if (requireKind && !id.includes(kind)) continue;
      if (useBox && boxToken && !id.includes(boxToken)) continue;
      if (suffixes.some((s) => id.endsWith(s))) return id;
    }
    return undefined;
  };
  // Prefer the matching box (multi-box safe); fall back to ignoring the box
  // token for installs whose entity ids are inconsistent (e.g. renamed).
  const find = (domain, suffixes, requireKind = true) =>
    scan(domain, suffixes, true, requireKind) ??
    scan(domain, suffixes, false, requireKind);

  return {
    title,
    reference_from: find("number", ["reference_from", "ref_min"]),
    reference_to: find("number", ["reference_to", "ref_max"]),
    speed_min: find("number", ["speed_min", "fan_min", "blower_min"]),
    speed_max: find("number", ["speed_max", "fan_max", "blower_max"]),
    current: find("sensor", ["_fan", "_blower"]),
    // box-level entities (not fan/blower specific)
    on_time: find("time", ["on_time"], false),
    off_time: find("time", ["off_time"], false),
    ref_temp: find("sensor", ["_temperature"], false),
    ref_humi: find("sensor", ["_humidity"], false),
    ref_vpd: find("sensor", ["_vpd"], false),
    ref_co2: find("sensor", ["_co2"], false),
    ...config,
  };
}

class SglFanCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.mode) {
      throw new Error("sgl-fan-card: 'mode' entity is required");
    }
    this._rawConfig = config;
    this._key = null;
    this._inner = null;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._helpers) this._helpers = window.loadCardHelpers();
    this._helpers.then((helpers) => this._render(helpers));
  }

  getCardSize() {
    return this._inner?.getCardSize?.() ?? 3;
  }

  _render(helpers) {
    const hass = this._hass;
    // Resolve every render: entities can appear later (e.g. after enabling a
    // previously-disabled one), so we must not cache an incomplete result.
    const c = resolveConfig(hass, this._rawConfig);
    const modeState = hass.states[c.mode];
    const mode = modeState ? modeState.state : undefined;
    const fields = MODE_FIELDS[mode] || ["speed_min", "speed_max"];

    const has = (id) => id && hass.states[id];
    const entities = [];
    if (has(c.current)) entities.push(c.current);
    entities.push(c.mode);
    const refSensor = MODE_REF_SENSOR[mode];
    if (refSensor && has(c[refSensor])) entities.push(c[refSensor]);
    for (const f of fields) {
      if (has(c[f])) entities.push(c[f]);
    }

    const key = entities.join(",");
    if (key !== this._key) {
      this._key = key;
      const card = helpers.createCardElement({
        type: "entities",
        title: c.title,
        entities,
      });
      card.hass = hass;
      this.innerHTML = "";
      this.appendChild(card);
      this._inner = card;
    } else if (this._inner) {
      this._inner.hass = hass;
    }
  }
}

// ---------------------------------------------------------------------------
// Light card — mode-aware on the box timer type.
//   Manual            -> lights only
//   On/Off schedule   -> lights + on/off times
//   Season            -> lights + season start month/day + duration
// Anchor entity is the box "Timer mode" select; the rest is resolved per box.
// ---------------------------------------------------------------------------

const LIGHT_MODE_FIELDS = {
  Manual: [],
  "On/Off schedule": ["on_time", "off_time"],
  Season: ["start_month", "start_day", "duration"],
};

function resolveLightConfig(hass, config) {
  const modeId = config.mode;
  const boxToken = (modeId.match(/box_\d+/) || [])[0];
  const deviceId = hass.entities?.[modeId]?.device_id;
  const onDevice = (id) => !deviceId || hass.entities?.[id]?.device_id === deviceId;
  const inBox = (id) => !boxToken || id.includes(boxToken);

  const scan = (domain, suffixes, useBox) => {
    for (const id of Object.keys(hass.states)) {
      if (!id.startsWith(`${domain}.`)) continue;
      if (!onDevice(id)) continue;
      if (useBox && !inBox(id)) continue;
      if (suffixes.some((s) => id.endsWith(s))) return id;
    }
    return undefined;
  };
  const find = (domain, suffixes) =>
    scan(domain, suffixes, true) ?? scan(domain, suffixes, false);

  const lights = Object.keys(hass.states)
    .filter((id) => id.startsWith("light.") && onDevice(id) && inBox(id))
    .sort();

  const boxNum = boxToken ? boxToken.replace("box_", "") : null;
  return {
    title: boxNum !== null ? `Box ${boxNum} light` : "Light",
    lights,
    light_on: find("binary_sensor", ["light_on"]),
    on_time: find("time", ["on_time"]),
    off_time: find("time", ["off_time"]),
    start_month: find("number", ["start_month"]),
    start_day: find("number", ["start_day"]),
    duration: find("number", ["season_duration", "duration"]),
    ...config,
  };
}

class SglLightCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.mode) {
      throw new Error("sgl-light-card: 'mode' (timer mode select) is required");
    }
    this._rawConfig = config;
    this._key = null;
    this._inner = null;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._helpers) this._helpers = window.loadCardHelpers();
    this._helpers.then((helpers) => this._render(helpers));
  }

  getCardSize() {
    return this._inner?.getCardSize?.() ?? 3;
  }

  _render(helpers) {
    const hass = this._hass;
    const c = resolveLightConfig(hass, this._rawConfig);
    const mode = hass.states[c.mode]?.state;
    const has = (id) => id && hass.states[id];

    const entities = [];
    if (has(c.light_on)) entities.push(c.light_on);
    entities.push(c.mode);
    for (const l of c.lights) entities.push(l);
    for (const f of LIGHT_MODE_FIELDS[mode] || []) {
      if (has(c[f])) entities.push(c[f]);
    }

    const key = entities.join(",");
    if (key !== this._key) {
      this._key = key;
      const card = helpers.createCardElement({
        type: "entities",
        title: c.title,
        entities,
      });
      card.hass = hass;
      this.innerHTML = "";
      this.appendChild(card);
      this._inner = card;
    } else if (this._inner) {
      this._inner.hass = hass;
    }
  }
}

customElements.define("sgl-fan-card", SglFanCard);
customElements.define("sgl-light-card", SglLightCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "sgl-light-card",
  name: "SuperGreenLab Light Card",
  description: "Box lights + schedule, mode-aware on the timer type.",
});
window.customCards.push({
  type: "sgl-fan-card",
  name: "SuperGreenLab Fan Card",
  description: "Mode-aware control for a SuperGreenLab fan/blower.",
});
