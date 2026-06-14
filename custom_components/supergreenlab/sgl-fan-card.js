/*
 * SuperGreenLab Fan Card — a mode-aware Lovelace card for one fan/blower.
 *
 * Shows the mode select plus only the settings relevant to the chosen mode
 * (something native cards can't do).
 *
 * Config: provide the `mode` entity; the reference/speed/current entities and a
 * title are derived from its entity id. Explicit ids in the config override the
 * derived ones.
 */

const MODE_FIELDS = {
  Manual: ["speed_min"],
  Timer: ["speed_min", "speed_max"],
  Temperature: ["reference_from", "reference_to", "speed_min", "speed_max"],
  Humidity: ["reference_from", "reference_to", "speed_min", "speed_max"],
  VPD: ["reference_from", "reference_to", "speed_min", "speed_max"],
  CO2: ["reference_from", "reference_to", "speed_min", "speed_max"],
};

const FIELD_LABELS = {
  reference_from: "Reference from",
  reference_to: "Reference to",
  speed_min: "Speed min",
  speed_max: "Speed max",
};

// Resolve sibling entities from the mode entity. Matches by entity-id prefix +
// role suffix, accepting both current and legacy names (entity ids don't change
// when an entity is renamed, so upgraded installs keep old-style ids).
function resolveConfig(hass, config) {
  const m = config.mode.match(/^select\.(.+)_(intake|exhaust)_fan_mode$/);
  if (!m) {
    return { title: config.title || "Fan", ...config };
  }
  const [, prefix, kind] = m;
  const start = `${prefix}_${kind}`; // e.g. "growbox_box_0_intake"
  const find = (domain, suffixes) => {
    const head = `${domain}.${start}`;
    for (const id of Object.keys(hass.states)) {
      if (id.startsWith(head) && suffixes.some((s) => id.endsWith(s))) return id;
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
    ...config, // explicit ids/title win
  };
}

class SglFanCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.mode) {
      throw new Error("sgl-fan-card: 'mode' entity is required");
    }
    this._rawConfig = config;
    this._config = null;
    this._root = null;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) this._config = resolveConfig(hass, this._rawConfig);
    if (!this._root) this._build();
    this._update();
  }

  getCardSize() {
    return 3;
  }

  _build() {
    const card = document.createElement("ha-card");
    card.header = this._config.title || "Fan";
    const body = document.createElement("div");
    body.style.padding = "0 16px 16px";
    card.appendChild(body);
    this.innerHTML = "";
    this.appendChild(card);
    this._body = body;
    this._root = card;
  }

  _row(label, inner) {
    const row = document.createElement("div");
    row.style.cssText =
      "display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:12px;";
    const l = document.createElement("span");
    l.textContent = label;
    row.appendChild(l);
    row.appendChild(inner);
    return row;
  }

  _update() {
    const hass = this._hass;
    const c = this._config;
    if (!hass || !c) return;
    const modeState = hass.states[c.mode];
    if (!modeState) {
      this._body.innerHTML = `<p>Unknown entity: ${c.mode}</p>`;
      return;
    }
    const mode = modeState.state;
    this._body.innerHTML = "";

    if (c.current && hass.states[c.current]) {
      const s = hass.states[c.current];
      const cur = document.createElement("div");
      cur.style.cssText = "font-size:2em;font-weight:500;";
      cur.textContent = `${s.state}${s.attributes.unit_of_measurement || "%"}`;
      this._body.appendChild(cur);
    }

    const sel = document.createElement("select");
    sel.style.cssText = "padding:6px;border-radius:8px;";
    (modeState.attributes.options || []).forEach((opt) => {
      const o = document.createElement("option");
      o.value = o.textContent = opt;
      if (opt === mode) o.selected = true;
      sel.appendChild(o);
    });
    sel.addEventListener("change", () =>
      hass.callService("select", "select_option", {
        entity_id: c.mode,
        option: sel.value,
      })
    );
    this._body.appendChild(this._row("Mode", sel));

    const fields = MODE_FIELDS[mode] || ["speed_min", "speed_max"];
    fields.forEach((f) => {
      const ent = c[f];
      const st = ent && hass.states[ent];
      if (!st) return;
      const wrap = document.createElement("div");
      wrap.style.cssText = "display:flex;align-items:center;gap:8px;";
      const slider = document.createElement("input");
      slider.type = "range";
      slider.min = st.attributes.min ?? 0;
      slider.max = st.attributes.max ?? 100;
      slider.step = st.attributes.step ?? 1;
      slider.value = st.state;
      const val = document.createElement("span");
      val.style.minWidth = "3ch";
      val.textContent = st.state;
      slider.addEventListener("input", () => (val.textContent = slider.value));
      slider.addEventListener("change", () =>
        hass.callService("number", "set_value", {
          entity_id: ent,
          value: Number(slider.value),
        })
      );
      wrap.appendChild(slider);
      wrap.appendChild(val);
      this._body.appendChild(this._row(FIELD_LABELS[f], wrap));
    });
  }
}

customElements.define("sgl-fan-card", SglFanCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "sgl-fan-card",
  name: "SuperGreenLab Fan Card",
  description: "Mode-aware control for a SuperGreenLab fan/blower.",
});
