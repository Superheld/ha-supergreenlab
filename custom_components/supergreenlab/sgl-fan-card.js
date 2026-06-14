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

// Resolve sibling entities from the mode entity by id prefix + role suffix,
// accepting both current and legacy names (entity ids don't change on rename).
function resolveConfig(hass, config) {
  const m = config.mode.match(/^select\.(.+)_(intake|exhaust)_fan_mode$/);
  if (!m) {
    return { title: config.title || "Fan", ...config };
  }
  const [, prefix, kind] = m;
  const head = `${prefix}_${kind}`;
  const find = (domain, suffixes) => {
    const start = `${domain}.${head}`;
    for (const id of Object.keys(hass.states)) {
      if (id.startsWith(start) && suffixes.some((s) => id.endsWith(s))) return id;
    }
    return undefined;
  };
  return {
    title: kind === "intake" ? "Intake fan" : "Exhaust fan",
    reference_from: find("number", ["reference_from", "ref_min"]),
    reference_to: find("number", ["reference_to", "ref_max"]),
    speed_min: find("number", ["speed_min", "fan_min"]),
    speed_max: find("number", ["speed_max", "fan_max"]),
    current: find("sensor", ["_fan"]),
    ...config,
  };
}

class SglFanCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.mode) {
      throw new Error("sgl-fan-card: 'mode' entity is required");
    }
    this._rawConfig = config;
    this._config = null;
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
    if (!this._config) this._config = resolveConfig(hass, this._rawConfig);
    const c = this._config;
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
