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
export function resolveConfig(hass, config) {
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
  "On/Off schedule": ["phase", "on_time", "off_time"],
  Season: ["start_month", "start_day", "duration", "sim_duration", "start_season"],
};

export function resolveLightConfig(hass, config) {
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

  const boxNum = boxToken ? boxToken.replace("box_", "") : null;
  return {
    title: boxNum !== null ? `Box ${boxNum} light` : "Light",
    phase: find("select", ["light_phase"]),
    on_time: find("time", ["on_time"]),
    off_time: find("time", ["off_time"]),
    start_month: find("number", ["start_month"]),
    start_day: find("number", ["start_day"]),
    duration: find("number", ["season_duration", "duration"]),
    sim_duration: find("number", ["sim_days"]),
    start_season: find("button", ["start_season"]),
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

    // Scheduler only: timer mode + the inputs relevant to it (phase/times or
    // season). Per-channel brightness and "light on" live elsewhere.
    const entities = [c.mode];
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

// ---------------------------------------------------------------------------
// Box card — the per-box HARDWARE setup: which sensor source feeds each metric
// and what spectrum each LED channel is. Just the one-time wiring choices, not
// live values / fan modes / schedule (those have their own cards). Anchor:
// `entity:` = any entity of the box (e.g. its timer mode select). `mode:` is
// accepted as an alias for consistency with the other cards.
// ---------------------------------------------------------------------------

export function resolveBoxConfig(hass, config) {
  const anchorId = config.entity || config.mode;
  const boxToken = (anchorId.match(/box_\d+/) || [])[0];
  const boxNum = boxToken ? boxToken.replace("box_", "") : null;
  const deviceId = hass.entities?.[anchorId]?.device_id;
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

  // The box's lights (they carry the box token); fall back to all on the
  // device for installs whose ids are inconsistent.
  const onBoxLights = Object.keys(hass.states).filter(
    (id) => id.startsWith("light.") && onDevice(id) && inBox(id),
  );
  const lights = (onBoxLights.length
    ? onBoxLights
    : Object.keys(hass.states).filter(
        (id) => id.startsWith("light.") && onDevice(id),
      )
  ).sort();

  // Spectrum selects are named per-LED (no box token); correlate to this box
  // via the LED index embedded in the box's light entity ids.
  const spectrum = [];
  for (const lid of lights) {
    const n = (lid.match(/light_(\d+)$/) || [])[1];
    if (n === undefined) continue;
    const sid = Object.keys(hass.states).find(
      (id) =>
        id.startsWith("select.") &&
        onDevice(id) &&
        id.endsWith(`light_${n}_spectrum`),
    );
    if (sid) spectrum.push(sid);
  }

  return {
    title: boxNum !== null ? `Box ${boxNum} setup` : "Box setup",
    temp_source: find("select", ["_temperature_source"]),
    humi_source: find("select", ["_humidity_source"]),
    vpd_source: find("select", ["_vpd_source"]),
    co2_source: find("select", ["_co2_source"]),
    weight_source: find("select", ["_weight_source"]),
    spectrum,
    ...config,
  };
}

class SglBoxCard extends HTMLElement {
  setConfig(config) {
    if (!config || !(config.entity || config.mode)) {
      throw new Error("sgl-box-card: 'entity' (any entity of the box) is required");
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
    const c = resolveBoxConfig(hass, this._rawConfig);
    const has = (id) => id && hass.states[id];

    const entities = [];
    const section = (label, ids) => {
      const present = ids.filter(has);
      if (!present.length) return;
      entities.push({ type: "section", label });
      for (const id of present) entities.push(id);
    };
    section("Climate sensors", [
      c.temp_source, c.humi_source, c.vpd_source, c.co2_source, c.weight_source,
    ]);
    section("Light spectrum", c.spectrum);

    const key = entities.map((e) => (typeof e === "string" ? e : e.label)).join(",");
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
customElements.define("sgl-box-card", SglBoxCard);
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
window.customCards.push({
  type: "sgl-box-card",
  name: "SuperGreenLab Box Card",
  description: "Per-box hardware setup: sensor sources + light spectrum.",
});
