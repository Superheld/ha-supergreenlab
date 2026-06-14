/*
 * SuperGreenLab Fan Card — a mode-aware Lovelace card for one fan/blower.
 *
 * Bundles the mode select with its dependent settings and shows only the
 * relevant ones for the chosen mode (something native cards can't do).
 *
 * Easy config: you only provide the `mode` entity (or pick it in the editor);
 * the reference/speed entities are derived from its entity id. Explicit entity
 * ids in the config override the derived ones.
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

// Derive the sibling entity ids + a title from the mode entity id, e.g.
// "select.<base>_intake_fan_mode" -> base "<base>_intake_fan".
function deriveConfig(config) {
  const base = config.mode.replace(/^select\./, "").replace(/_mode$/, "");
  let title = config.title;
  if (!title) {
    if (base.endsWith("intake_fan")) title = "Intake fan";
    else if (base.endsWith("exhaust_fan")) title = "Exhaust fan";
    else title = "Fan";
  }
  return {
    reference_from: `number.${base}_reference_from`,
    reference_to: `number.${base}_reference_to`,
    speed_min: `number.${base}_speed_min`,
    speed_max: `number.${base}_speed_max`,
    current: `sensor.${base}`,
    ...config,
    title,
  };
}

class SglFanCard extends HTMLElement {
  setConfig(config) {
    if (!config.mode) {
      throw new Error("sgl-fan-card: 'mode' entity is required");
    }
    this._config = deriveConfig(config);
    this._root = null;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._root) this._build();
    this._update();
  }

  getCardSize() {
    return 3;
  }

  static getStubConfig(hass) {
    const mode = Object.keys(hass.states).find(
      (e) => e.startsWith("select.") && e.endsWith("_fan_mode")
    );
    return { mode: mode || "select.REPLACE_intake_fan_mode" };
  }

  static getConfigElement() {
    return document.createElement("sgl-fan-card-editor");
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

// Minimal visual editor: pick the fan's Mode entity, the rest is derived.
class SglFanCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass) return;
    if (!this._picker) {
      this.innerHTML = "";
      const picker = document.createElement("ha-entity-picker");
      picker.label = "Fan mode entity";
      picker.includeDomains = ["select"];
      picker.entityFilter = (s) => s.entity_id.endsWith("_fan_mode");
      picker.addEventListener("value-changed", (e) => {
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: { ...this._config, mode: e.detail.value } },
            bubbles: true,
            composed: true,
          })
        );
      });
      this._picker = picker;
      this.appendChild(picker);
    }
    this._picker.hass = this._hass;
    this._picker.value = this._config.mode || "";
  }
}

customElements.define("sgl-fan-card", SglFanCard);
customElements.define("sgl-fan-card-editor", SglFanCardEditor);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "sgl-fan-card",
  name: "SuperGreenLab Fan Card",
  description: "Mode-aware control for a SuperGreenLab fan/blower.",
  preview: false,
  documentationURL: "https://github.com/Superheld/ha-supergreenlab",
});
