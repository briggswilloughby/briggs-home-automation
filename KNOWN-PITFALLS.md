### YAML / Lint
- Indentation is 2 spaces; `yamllint` enforces it. One blank line between sections is OK (`empty-lines: max 1`).
- Duplicate keys silently override; prefer anchors/aliases or split sections clearly.
- `!include_dir_named` treats empty files as `null`; keep placeholder packages as valid mappings (e.g., `homeassistant: {}`) so reloads don't fail.

### HA reloads
- After pushes/pulls, use **Reload packages** (Settings → Developer Tools → YAML).
- If helpers/entities change names, update all references; HA won’t auto-rename.

### Symlinked config
- `~/ha/config/packages` is a symlink to `~/briggs-home-automation/home-assistant/packages`.
- If something breaks, rollback: `rm ~/ha/config/packages && mv ~/ha/config/packages-backup ~/ha/config/packages`.

### Integrations
- **Sonos:** snapshot/restore timing; grouped players can “steal focus”; avoid volume jumps—set defaults.
- **Sonos:** share baseline volumes via a single helper/constant; hardcoded per-script volumes drift and undo ADR-0003.
- **Ring:** cloud throttling; debounce/chime double-ding.
- **Ring:** always play chimes with `media-source://` URIs; direct `http://` links break when auth tokens rotate.
- **Shelly:** devices can drop offline; guard with `availability` / timeouts.
- **Lutron:** cert/keys must be valid; don’t commit keys; network name changes break integrations.

### Automations & Scripts
- Avoid referencing helpers that don’t exist (e.g., `script.sonos_raise_if_below`); add the script first or drop the automation.

### Secrets & noise
- Never commit `secrets.yaml`, DB files, logs; keep `.gitignore` up to date.
