# Quality scale status

An honest, self-assessed mapping of this integration against Home Assistant's
[Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/).
It is kept as Markdown rather than `quality_scale.yaml` because hassfest's
`quality_scale.yaml` validation is coupled to core's rule registry and would
fail CI for a custom component; the rule names and intent below are identical.

Legend: ✅ done · ⚠️ partial · ❌ not yet · — not applicable

## Bronze

| Rule | Status | Note |
|------|--------|------|
| config-flow | ✅ | UI setup with host + optional auth |
| test-before-configure | ✅ | Setup probes the device before creating the entry |
| test-before-setup | ✅ | Raises `ConfigEntryNotReady` / `ConfigEntryAuthFailed` |
| unique-config-entry | ✅ | unique_id = controller client id; duplicates aborted |
| config-flow-test-coverage | ✅ | config_flow.py at 99% |
| has-entity-name | ✅ | All entities; box context via sub-device |
| entity-unique-id | ✅ | `<client_id>_<key>` |
| entity-event-setup | ✅ | `CoordinatorEntity` subscription lifecycle |
| appropriate-polling | ✅ | Fast (live) + slow (config) coordinators, interval configurable |
| runtime-data | ✅ | Typed `entry.runtime_data` |
| common-modules | ✅ | `coordinator.py`, `entity.py` |
| dependency-transparency | ✅ | No third-party requirements |
| action-setup | — | No custom service actions |
| docs-actions | — | No custom service actions |
| docs-high-level-description | ✅ | README |
| docs-installation-instructions | ✅ | README → Installation |
| docs-removal-instructions | ✅ | README → Removing |
| **brands** | ❌ | **Logo/icon must be submitted to `home-assistant/brands` — external PR, see below** |

## Silver

| Rule | Status | Note |
|------|--------|------|
| config-entry-unloading | ✅ | `async_unload_entry` |
| reauthentication-flow | ✅ | Reauth on HTTP 401 |
| entity-unavailable | ✅ | Coordinator marks entities unavailable on failure |
| log-when-unavailable | ✅ | Coordinator logs once, recovers quietly |
| parallel-updates | ✅ | Declared per write platform |
| integration-owner | ✅ | `codeowners` in manifest |
| test-coverage | ✅ | 94% overall, 99% config flow |
| docs-installation-parameters | ✅ | README → Setup |
| docs-configuration-parameters | ✅ | README → options / entities |
| action-exceptions | — | No custom actions (entity write errors are translated) |

## Gold

| Rule | Status | Note |
|------|--------|------|
| devices | ✅ | Controller + per-box sub-devices via `via_device` |
| diagnostics | ✅ | Redacted config-entry diagnostics |
| discovery | ✅ | zeroconf / mDNS (default-named controllers) |
| discovery-update-info | ✅ | Host updated from discovery |
| entity-category | ✅ | config / diagnostic categories |
| entity-device-class | ✅ | temperature, humidity, pressure, CO2, weight, timestamp… |
| entity-disabled-by-default | ✅ | Advanced/rare entities disabled by default |
| entity-translations | ✅ | Names from `translation_key` (generated from the catalog) |
| icon-translations | ✅ | `icons.json` |
| exception-translations | ✅ | `write_failed` translated error |
| reconfiguration-flow | ✅ | Change host/IP without re-adding |
| stale-devices | ✅ | Prune disabled-box devices + manual removal |
| docs-supported-devices | ✅ | README |
| docs-supported-functions | ✅ | README → What the entities do |
| docs-data-update | ✅ | README → sync section |
| docs-known-limitations | ✅ | README → no live sync, discovery scope |
| docs-troubleshooting | ✅ | README → Troubleshooting |
| docs-use-cases | ✅ | README + dashboards |
| docs-examples | ✅ | `dashboards/`, bundled cards |
| dynamic-devices | — | Box set is fixed in firmware; layout changes go through options + reload |
| repair-issues | — | No runtime conditions currently warrant a repair issue |

## Platinum

| Rule | Status | Note |
|------|--------|------|
| inject-websession | ✅ | `async_get_clientsession` |
| async-dependency | — | No dependency library; talks HTTP directly via HA's aiohttp |
| strict-typing | ⚠️ | `py.typed` present and fully type-hinted; not yet verified under mypy strict |

## The one external blocker: brands

`brands` is a **Bronze** rule, so until it is satisfied the integration cannot
claim any official tier — even though the code is at Gold level. It requires a
logo and icon in the [`home-assistant/brands`](https://github.com/home-assistant/brands)
repository under `custom_integrations/supergreenlab/`. That is a separate PR to
an Anthropic-external repo and needs the project owner to submit the actual
SuperGreenLab brand assets (`icon.png` 256×256, `logo.png`), so it is tracked
here rather than done automatically.

Installing this as a **custom HACS repository** works today without brands; only
inclusion in the HACS **default store** and an official quality badge need it.
