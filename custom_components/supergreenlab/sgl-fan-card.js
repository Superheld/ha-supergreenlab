/*
 * SuperGreenLab Fan Card — a mode-aware Lovelace card for one fan/blower.
 *
 * Renders a native Home Assistant `entities` card and decides which rows to
 * show based on the selected mode (Manual → speed; Timer → speed range;
 * Temperature/Humidity/VPD/CO2 → reference range + speed range). Using the
 * built-in card means the dropdown/sliders look and behave natively.
 *
 * Config: just the `mode` entity; the reference/speed/current entities and a
 * title are resolved automatically (legacy entity ids supported). Explicit ids
 * in the config win.
 */

const MODE_FIELDS = {
  Manual: ["speed_min"],
  Timer: ["speed_min", "speed_max"],
  Temperature: ["reference_from", "reference_to", "speed_min", "speed_max"],
  Humidity: ["reference_from", "reference_to", "speed_min", "speed_max"],
  VPD: ["reference_from", "reference_to", "speed_min", "speed_max"],
  CO2: ["reference_from", "reference_to", "speed_min", "speed_max"],
};

// Resolve sibling entities from the mode entity. Siblings are matched by the
// same *device* (robust against mismatched entity-id prefixes, e.g. a renamed
// mode entity), plus the fan kind, box index and a role suffix. Falls back to
// id-substring matching if the entity registry isn't available. Accepts both
// current and legacy role suffixes (entity ids don't change on rename).
function resolveConfig(hass, config) {
  const modeId = config.mode;
  // Disambiguate fan (in-box) vs blower (exhaust). New ids use fan/blower;
  // upgraded installs may still use the old intake/exhaust wording.
  let kind = "fan";
  let title = "Fan";
  if (modeId.includes("blower")) [kind, title] = ["blower", "Blower"];
  else if (modeId.includes("exhaust")) [kind, title] = ["exhaust", "Blower"];
  else if (modeId.includes("intake")) [kind, title] = ["intake", "Fan"];
  const boxToken = (modeId.match(/box_\d+/) || [])[0];
  const deviceId = hass.entities?.[modeId]?.device_id;

  const scan = (domain, suffixes, useBox) => {
    for (const id of Object.keys(hass.states)) {
      if (!id.startsWith(`${domain}.`)) continue;
      if (deviceId && hass.entities?.[id]?.device_id !== deviceId) continue;
      if (!id.includes(kind)) continue;
      if (useBox && boxToken && !id.includes(boxToken)) continue;
      if (suffixes.some((s) => id.endsWith(s))) return id;
    }
    return undefined;
  };
  // Prefer the matching box (multi-box safe); fall back to ignoring the box
  // token for installs whose entity ids are inconsistent (e.g. renamed).
  const find = (domain, suffixes) =>
    scan(domain, suffixes, true) ?? scan(domain, suffixes, false);

  return {
    title,
    reference_from: find("number", ["reference_from", "ref_min"]),
    reference_to: find("number", ["reference_to", "ref_max"]),
    speed_min: find("number", ["speed_min", "fan_min", "blower_min"]),
    speed_max: find("number", ["speed_max", "fan_max", "blower_max"]),
    current: find("sensor", ["_fan", "_blower"]),
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

    const entities = [];
    if (c.current && hass.states[c.current]) entities.push(c.current);
    entities.push(c.mode);
    for (const f of fields) {
      if (c[f] && hass.states[c[f]]) entities.push(c[f]);
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
window.customCards = window.customCards || [];
window.customCards.push({
  type: "sgl-fan-card",
  name: "SuperGreenLab Fan Card",
  description: "Mode-aware control for a SuperGreenLab fan/blower.",
});
